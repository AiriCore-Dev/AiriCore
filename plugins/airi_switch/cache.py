"""群名/群头像/bot 昵称/bot 头像的本地缓存。

避免每次 ``airianalysis`` 都去 ``get_group_info`` / ``get_stranger_info`` 拉名字,
以及重复下载头像。缓存落盘到 ``data/airi_switch/meta_cache.pk``,带 TTL:名字类
默认 1 天过期、头像类默认 7 天过期(过期后下次用到再刷新)。落盘沿用 counter 的
节流 + 原子 tmp.replace 套路;airianalysis 结束会显式 ``flush()`` 兜底一次。
"""

import copy
import pickle
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from nonebot import logger

# 各 kind 的默认 TTL(秒)。名字变动不频繁但要能刷新,头像更少变。
TTL_NAME = 3 * 24 * 3600
TTL_AVATAR = 7 * 24 * 3600

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "airi_switch"
_CACHE_FILE = _DATA_DIR / "meta_cache.pk"

# 落盘节流:一次 airianalysis 会连续 put 多条(多群/多 bot),攒一下再写
_FLUSH_INTERVAL = 3.0

_lock = threading.Lock()
# {kind: {key: (value, ts)}}  kind ∈ group_name/group_avatar/bot_name/user_avatar
_cache: Dict[str, Dict[str, Any]] = {}
_last_flush = 0.0
_dirty = False


def _load() -> None:
    global _cache
    if _CACHE_FILE.is_file():
        try:
            with open(_CACHE_FILE, "rb") as f:
                _cache = pickle.load(f)
            return
        except Exception as e:  # 损坏就重置,不阻塞启动
            logger.opt(colors=True).warning(f"<y>airi_switch 元信息缓存读取失败,已重置: {e}</y>")
    _cache = {}


def _flush(force: bool = False) -> None:
    """把缓存写盘(节流)。调用方需持有 _lock。"""
    global _last_flush, _dirty
    now = time.time()
    if not force and (not _dirty or now - _last_flush < _FLUSH_INTERVAL):
        return
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_FILE.with_suffix(".pk.tmp")
        with open(tmp, "wb") as f:
            pickle.dump(_cache, f)
        tmp.replace(_CACHE_FILE)  # 原子替换,防写一半崩掉
        _last_flush = now
        _dirty = False
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>airi_switch 元信息缓存写入失败: {e}</y>")


def get(kind: str, key: str, ttl: Optional[float] = None) -> Any:
    """取缓存值;不存在或已过期返回 None。ttl 为 None 表示不判过期。"""
    with _lock:
        entry = _cache.get(kind, {}).get(str(key))
        if entry is None:
            return None
        value, ts = entry
        if ttl is not None and time.time() - ts > ttl:
            return None
        return value


def put(kind: str, key: str, value: Any) -> None:
    """写入/更新一条缓存(带当前时间戳),节流落盘。"""
    global _dirty
    with _lock:
        _cache.setdefault(kind, {})[str(key)] = (value, time.time())
        _dirty = True
        _flush()


def flush() -> None:
    """强制落盘一次(airianalysis 命令末尾兜底调用)。"""
    with _lock:
        _flush(force=True)


_load()
