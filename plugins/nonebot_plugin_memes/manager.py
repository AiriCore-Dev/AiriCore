import pickle
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Optional

from meme_generator import Meme, get_memes, search_memes
from nonebot import get_driver
from nonebot.log import logger

from .config import memes_config

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nonebot_plugin_memes"
_CONFIG_FILE = _DATA_DIR / "manager.pk"

driver = get_driver()


class MemeMode(IntEnum):
    BLACK = 0
    WHITE = 1


@dataclass
class MemeConfig:
    mode: MemeMode = MemeMode.BLACK
    white_list: list[str] = field(default_factory=list)
    black_list: list[str] = field(default_factory=list)


def _to_raw(config: MemeConfig) -> dict[str, Any]:
    return {
        "mode": int(config.mode),
        "white_list": list(config.white_list),
        "black_list": list(config.black_list),
    }


def _from_raw(raw: Any) -> MemeConfig:
    if not isinstance(raw, dict):
        raise ValueError("表情配置格式错误")
    return MemeConfig(
        mode=MemeMode(int(raw.get("mode", 0))),
        white_list=[str(x) for x in (raw.get("white_list") or [])],
        black_list=[str(x) for x in (raw.get("black_list") or [])],
    )


class MemeManager:
    def __init__(self, path: Path = _CONFIG_FILE):
        self.__path = path
        self.__lock = threading.Lock()
        self.__dirty = False
        self.__meme_config: dict[str, MemeConfig] = {}
        self.__meme_dict = {
            meme.key: meme
            for meme in filter(
                lambda meme: meme.key not in memes_config.memes_disabled_list,
                sorted(get_memes(), key=lambda meme: meme.key),
            )
        }
        self.__meme_names: dict[str, list[Meme]] = {}
        self.__load()
        self.__refresh_names()

    def get_meme(self, meme_key: str) -> Optional[Meme]:
        return self.__meme_dict.get(meme_key, None)

    def get_memes(self) -> list[Meme]:
        return list(self.__meme_dict.values())

    def block(self, user_id: str, meme_key: str):
        config = self.__meme_config[meme_key]
        if config.mode == MemeMode.BLACK and user_id not in config.black_list:
            config.black_list.append(user_id)
        if config.mode == MemeMode.WHITE and user_id in config.white_list:
            config.white_list.remove(user_id)
        self.__mark_dirty()

    def unblock(self, user_id: str, meme_key: str):
        config = self.__meme_config[meme_key]
        if config.mode == MemeMode.WHITE and user_id not in config.white_list:
            config.white_list.append(user_id)
        if config.mode == MemeMode.BLACK and user_id in config.black_list:
            config.black_list.remove(user_id)
        self.__mark_dirty()

    def change_mode(self, mode: MemeMode, meme_key: str):
        config = self.__meme_config[meme_key]
        config.mode = mode
        self.__mark_dirty()

    def find(self, meme_name: str) -> list[Meme]:
        meme_name = meme_name.lower()
        if meme_name in self.__meme_names:
            return self.__meme_names[meme_name]
        return []

    def search(self, meme_name: str, include_tags: bool = False) -> list[Meme]:
        meme_keys = search_memes(meme_name, include_tags=include_tags)
        meme_keys = [key for key in meme_keys if key in self.__meme_dict]
        return [self.__meme_dict[key] for key in meme_keys]

    def check(self, user_id: str, meme_key: str) -> bool:
        if meme_key not in self.__meme_config:
            return False
        config = self.__meme_config[meme_key]
        if config.mode == MemeMode.BLACK:
            if user_id in config.black_list:
                return False
            return True
        elif config.mode == MemeMode.WHITE:
            if user_id in config.white_list:
                return True
            return False
        return False

    def __mark_dirty(self) -> None:
        with self.__lock:
            self.__dirty = True
            self.__dump()

    def flush(self) -> None:
        with self.__lock:
            self.__dump()

    def __load(self) -> None:
        raw_list: dict[str, Any] = {}
        if self.__path.is_file():
            try:
                with self.__path.open("rb") as f:
                    loaded = pickle.load(f)
                if isinstance(loaded, dict):
                    raw_list = loaded
                else:
                    logger.opt(colors=True).warning("<y>表情列表格式错误，将重新生成</y>")
            except Exception as e:
                logger.opt(colors=True).warning(f"<y>表情列表读取失败，将重新生成: {e}</y>")
        meme_list: dict[str, MemeConfig] = {}
        try:
            meme_list = {name: _from_raw(config) for name, config in raw_list.items()}
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>表情列表解析失败，将重新生成: {e}</y>")
        self.__meme_config = {
            meme_key: MemeConfig() for meme_key in self.__meme_dict.keys()
        }
        self.__meme_config.update(meme_list)
        if set(self.__meme_config) != set(meme_list):
            with self.__lock:
                self.__dirty = True
                self.__dump()

    def __dump(self) -> None:
        if not self.__dirty:
            return
        meme_list = {
            name: _to_raw(config) for name, config in self.__meme_config.items()
        }
        try:
            self.__path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.__path.with_suffix(".pk.tmp")
            with tmp.open("wb") as f:
                pickle.dump(meme_list, f)
            tmp.replace(self.__path)
            self.__dirty = False
        except Exception as e:
            logger.opt(colors=True).warning(f"<y>表情列表写入失败: {e}</y>")

    def __refresh_names(self):
        self.__meme_names = {}
        for meme in self.__meme_dict.values():
            names = set()
            names.add(meme.key.lower())
            for keyword in meme.info.keywords:
                names.add(keyword.lower())
            for shortcut in meme.info.shortcuts:
                names.add(shortcut.pattern.lower())
                if shortcut.humanized:
                    names.add(shortcut.humanized.lower())
            for name in names:
                if name not in self.__meme_names:
                    self.__meme_names[name] = []
                self.__meme_names[name].append(meme)


meme_manager = MemeManager()


@driver.on_shutdown
async def _memes_manager_shutdown() -> None:
    meme_manager.flush()
