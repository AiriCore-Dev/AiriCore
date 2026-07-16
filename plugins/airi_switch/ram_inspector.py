import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def get_process_memory() -> int:
    try:
        import psutil

        return psutil.Process().memory_info().rss
    except Exception:
        pass
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return int(rss)
        return int(rss) * 1024
    except Exception:
        return 0


def _file_size(rel: str) -> int:
    try:
        p = _DATA_DIR / rel
        if p.is_file():
            return p.stat().st_size
    except Exception:
        pass
    return 0


def _blob_len(v: Any) -> int:
    if isinstance(v, (bytes, bytearray)):
        return len(v)
    if isinstance(v, str):
        return len(v)
    return sys.getsizeof(v)


def _new(name: str, disk_file: str) -> Dict[str, Any]:
    return {
        "name": name,
        "disk_bytes": _file_size(disk_file),
        "ram_bytes": 0,
        "ram_items": 0,
        "details": [],
    }


def _inspect_airi_switch_meta() -> Dict[str, Any]:
    r = _new("airi_switch 元信息", "airi_switch/meta_cache.pk")
    try:
        from . import cache as mod

        data = getattr(mod, "_cache", {}) or {}
        kind_label = {
            "group_name": "群名",
            "group_avatar": "群头像",
            "bot_name": "Bot昵称",
            "user_avatar": "用户头像",
        }
        total = 0
        rb = sys.getsizeof(data)
        for kind, entries in data.items():
            if not isinstance(entries, dict):
                continue
            n = len(entries)
            total += n
            rb += sys.getsizeof(entries)
            for k, v in entries.items():
                rb += sys.getsizeof(k)
                val = v[0] if isinstance(v, tuple) and v else v
                rb += _blob_len(val)
            r["details"].append(f"{kind_label.get(kind, kind)}: {n} 条")
        r["ram_items"] = total
        r["ram_bytes"] = rb if total else 0
    except Exception as e:
        r["error"] = str(e)
    return r


def _inspect_airi_switch_counter() -> Dict[str, Any]:
    r = _new("airi_switch 收发统计", "airi_switch/msg_stats.pk")
    try:
        from . import counter as mod

        stats = getattr(mod, "_stats", {}) or {}
        days = len(stats)
        bot_ids = set()
        sessions = 0
        rb = sys.getsizeof(stats)
        for day, bots in stats.items():
            rb += sys.getsizeof(day) + sys.getsizeof(bots)
            if not isinstance(bots, dict):
                continue
            for bid, rec in bots.items():
                bot_ids.add(bid)
                rb += sys.getsizeof(bid) + sys.getsizeof(rec)
                if isinstance(rec, dict):
                    for direction, sess in rec.items():
                        rb += sys.getsizeof(sess)
                        if isinstance(sess, dict):
                            sessions += len(sess)
        if days:
            r["details"].append(f"记录天数: {days} 天")
            r["details"].append(f"涉及 Bot: {len(bot_ids)} 个")
            r["details"].append(f"会话计数项: {sessions} 项")
        r["ram_items"] = days
        r["ram_bytes"] = rb if days else 0
    except Exception as e:
        r["error"] = str(e)
    return r


def _inspect_persist_blob(name, disk_file, import_path, ns, item_label, blob_key):
    r = _new(name, disk_file)
    try:
        mod = __import__(import_path, fromlist=["cache"])
        persist = getattr(mod, "_persist", {}) or {}
        bucket = persist.get(ns, {}) or {}
        n = len(bucket)
        rb = sys.getsizeof(persist) + sys.getsizeof(bucket)
        blob_total = 0
        for k, entry in bucket.items():
            rb += sys.getsizeof(k) + sys.getsizeof(entry)
            if isinstance(entry, dict):
                val = entry.get(blob_key)
                blob_total += _blob_len(val) if val is not None else 0
        rb += blob_total
        if n:
            r["details"].append(f"{item_label}: {n} 个")
            if blob_total:
                r["details"].append(f"内容体积: {_fmt(blob_total)}")
        r["ram_items"] = n
        r["ram_bytes"] = rb if n else 0
    except Exception as e:
        r["error"] = str(e)
    return r


def _inspect_daily_check() -> Dict[str, Any]:
    r = _new("airi_daily_check", "airi_daily_check/cache.pk")
    try:
        from plugins.airi_daily_check.base import cache as mod

        rb = 0
        total = 0

        persist = getattr(mod, "_persist", {}) or {}
        for ns, bucket in persist.items():
            if not isinstance(bucket, dict):
                continue
            n = len(bucket)
            total += n
            rb += sys.getsizeof(bucket)
            blob_total = 0
            for k, entry in bucket.items():
                rb += sys.getsizeof(k) + sys.getsizeof(entry)
                if isinstance(entry, dict):
                    blob_total += _blob_len(entry.get("blob")) if entry.get("blob") is not None else 0
            rb += blob_total
            if n:
                r["details"].append(f"{ns}: {n} 项")

        decoded = getattr(mod, "_decoded", {}) or {}
        if decoded:
            total += len(decoded)
            rb += sys.getsizeof(decoded)
            for k, v in decoded.items():
                rb += sys.getsizeof(k) + sys.getsizeof(v)
            r["details"].append(f"已解码对象: {len(decoded)} 个")

        img_r = _images_bytes(getattr(mod, "_images", {}))
        if img_r[0]:
            total += img_r[0]
            rb += img_r[1]
            r["details"].append(f"图片: {img_r[0]} 张")

        fonts = getattr(mod, "_fonts", {}) or {}
        if fonts:
            total += len(fonts)
            rb += sys.getsizeof(fonts)
            r["details"].append(f"字体: {len(fonts)} 个")

        r["ram_items"] = total
        r["ram_bytes"] = rb if total else 0
    except Exception as e:
        r["error"] = str(e)
    return r


def _images_bytes(images) -> Tuple[int, int]:
    if not images:
        return 0, 0
    count = len(images)
    rb = sys.getsizeof(images)
    for k, img in images.items():
        rb += sys.getsizeof(k)
        try:
            w, h = img.size
            rb += w * h * len(img.mode)
        except Exception:
            rb += sys.getsizeof(img)
    return count, rb


def _inspect_kokomi_wows() -> Dict[str, Any]:
    r = _new("airi_kokomi_wows", "")
    try:
        from plugins.airi_kokomi_wows import cache as mod

        arrays = getattr(mod, "_arrays", {}) or {}
        count = len(arrays)
        rb = sys.getsizeof(arrays)
        for k, entry in arrays.items():
            rb += sys.getsizeof(k) + sys.getsizeof(entry)
            arr = entry[1] if isinstance(entry, tuple) and len(entry) > 1 else None
            if arr is not None and hasattr(arr, "nbytes"):
                rb += int(arr.nbytes)
        if count:
            r["details"].append(f"解码图片数组: {count} 个")
        r["ram_items"] = count
        r["ram_bytes"] = rb if count else 0
    except Exception as e:
        r["error"] = str(e)
    return r


def _inspect_asset_cache() -> Dict[str, Any]:
    r = _new("asset_cache 共享静态资源", "")
    try:
        from utils import asset_cache as mod

        rb = 0
        total = 0

        img_r = _images_bytes(getattr(mod, "_images", {}))
        if img_r[0]:
            total += img_r[0]
            rb += img_r[1]
            r["details"].append(f"图片: {img_r[0]} 张")

        fonts = getattr(mod, "_fonts", {}) or {}
        if fonts:
            total += len(fonts)
            rb += sys.getsizeof(fonts)
            r["details"].append(f"字体: {len(fonts)} 个")

        b64 = getattr(mod, "_b64", {}) or {}
        if b64:
            total += len(b64)
            rb += sys.getsizeof(b64)
            btotal = 0
            for k, v in b64.items():
                rb += sys.getsizeof(k)
                btotal += _blob_len(v)
            rb += btotal
            r["details"].append(f"base64: {len(b64)} 个")

        r["ram_items"] = total
        r["ram_bytes"] = rb if total else 0
    except Exception as e:
        r["error"] = str(e)
    return r


def _fmt(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    kb = n / 1024
    if kb < 1024:
        return f"{kb:.1f}KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f}MB"
    return f"{mb / 1024:.2f}GB"


def inspect_all() -> Tuple[int, str, List[Dict[str, Any]]]:
    from utils.cache_mode import get_mode

    mode = get_mode()
    memory = get_process_memory()

    results = [
        _inspect_airi_switch_meta(),
        _inspect_airi_switch_counter(),
        _inspect_persist_blob(
            "today_waifu", "nonebot_plugin_today_waifu/cache.pk",
            "plugins.nonebot_plugin_today_waifu.cache", "avatar", "缓存头像", "blob",
        ),
        _inspect_persist_blob(
            "whateat_pic", "nonebot_plugin_whateat_pic/cache.pk",
            "plugins.nonebot_plugin_whateat_pic.cache", "img", "缓存图片", "b64",
        ),
        _inspect_persist_blob(
            "tarot", "nonebot_plugin_tarot/cache.pk",
            "plugins.nonebot_plugin_tarot.cache", "card", "缓存塔罗牌", "b64",
        ),
        _inspect_daily_check(),
        _inspect_kokomi_wows(),
        _inspect_asset_cache(),
    ]

    return memory, mode, results
