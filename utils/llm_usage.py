import pickle
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

from nonebot import logger

SOURCE_CHAT = "对话"
SOURCE_MECHANISM = "对话机制"
SOURCE_TURTLE_SOUP = "海龟汤"
SOURCE_WATER_METER = "水表"
SOURCE_WISH_BOTTLE = "心愿瓶审核"
SOURCE_RCON_TRANSLATION = "RCON翻译"
SOURCE_ORDER = (
    SOURCE_CHAT,
    SOURCE_MECHANISM,
    SOURCE_TURTLE_SOUP,
    SOURCE_WATER_METER,
    SOURCE_WISH_BOTTLE,
    SOURCE_RCON_TRANSLATION,
)

UTC_PLUS_8 = timezone(timedelta(hours=8))
_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "airi_llm"
_STATS_FILE = _DATA_DIR / "usage_stats.pk"
_FLUSH_INTERVAL = 15.0
_lock = threading.Lock()
_stats: Dict[str, Dict[str, Dict[str, int]]] = {}
_last_flush = 0.0
_dirty = False


def _today() -> str:
    return datetime.now(UTC_PLUS_8).strftime("%Y-%m-%d")


def _snapshot() -> Dict[str, Dict[str, Dict[str, int]]]:
    return {
        day: {source: dict(models) for source, models in sources.items()}
        for day, sources in _stats.items()
    }


def get_snapshot() -> Dict[str, Dict[str, Dict[str, int]]]:
    with _lock:
        return _snapshot()


def record_success(source: str, model: str) -> None:
    global _dirty
    if not source or not model:
        return
    try:
        with _lock:
            models = _stats.setdefault(_today(), {}).setdefault(str(source), {})
            model_name = str(model)
            models[model_name] = models.get(model_name, 0) + 1
            _dirty = True
    except Exception as e:
        logger.warning(f"LLM 调用统计失败: {e}")


def _corrupt_path() -> Path:
    return _STATS_FILE.with_name(f"{_STATS_FILE.name}.corrupt.{int(time.time())}")


def _load() -> None:
    global _stats
    if not _STATS_FILE.is_file():
        _stats = {}
        return
    try:
        with open(_STATS_FILE, "rb") as f:
            loaded = pickle.load(f)
        if not isinstance(loaded, dict):
            raise ValueError("统计文件结构无效")
        _stats = loaded
    except Exception as e:
        try:
            _STATS_FILE.replace(_corrupt_path())
        except Exception as move_error:
            logger.warning(f"LLM 调用统计损坏文件保留失败: {move_error}")
        logger.warning(f"LLM 调用统计读取失败，已重置: {e}")
        _stats = {}


def _flush(force: bool = False) -> None:
    global _dirty, _last_flush
    now = time.time()
    with _lock:
        if not force and (not _dirty or now - _last_flush < _FLUSH_INTERVAL):
            return
        snapshot = _snapshot()
        _dirty = False
        _last_flush = now
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STATS_FILE.with_suffix(".pk.tmp")
        with open(tmp, "wb") as f:
            pickle.dump(snapshot, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(_STATS_FILE)
    except Exception as e:
        with _lock:
            _dirty = True
        logger.warning(f"LLM 调用统计写入失败: {e}")


def flush() -> None:
    _flush(force=True)


def _writer_loop() -> None:
    while True:
        time.sleep(_FLUSH_INTERVAL)
        try:
            _flush()
        except Exception:
            continue


_load()
threading.Thread(target=_writer_loop, daemon=True, name="llm_usage_writer").start()

try:
    from nonebot import get_driver as _get_driver

    @_get_driver().on_shutdown
    async def _flush_on_shutdown():
        flush()
except Exception:
    pass
