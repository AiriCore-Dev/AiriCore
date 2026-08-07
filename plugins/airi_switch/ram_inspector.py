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


def _snapshot(mod: Any, attr: str) -> Any:
    lock = getattr(mod, "_lock", None)
    acquired = False
    try:
        if lock is not None and hasattr(lock, "acquire"):
            acquired = lock.acquire(timeout=1) if _supports_timeout(lock) else lock.acquire()
        raw = getattr(mod, attr, None) or {}
        if hasattr(raw, "keys") and hasattr(raw, "get") and not isinstance(raw, dict):
            return {key: raw.get(key) for key in raw.keys()}
        if isinstance(raw, dict):
            return dict(raw)
        return raw
    except Exception:
        return {}
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                pass


def _supports_timeout(lock: Any) -> bool:
    import threading

    return isinstance(lock, (type(threading.Lock()), type(threading.RLock())))


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

        data = _snapshot(mod, "_cache")
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

        stats = _snapshot(mod, "_stats")
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
        persist = _snapshot(mod, "_persist")
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

        persist = _snapshot(mod, "_persist")
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

        decoded = _snapshot(mod, "_decoded")
        if decoded:
            total += len(decoded)
            rb += sys.getsizeof(decoded)
            for k, v in decoded.items():
                rb += sys.getsizeof(k) + sys.getsizeof(v)
            r["details"].append(f"已解码对象: {len(decoded)} 个")

        img_r = _images_bytes(_snapshot(mod, "_images"))
        if img_r[0]:
            total += img_r[0]
            rb += img_r[1]
            r["details"].append(f"图片: {img_r[0]} 张")

        fonts = _snapshot(mod, "_fonts")
        if fonts:
            total += len(fonts)
            rb += sys.getsizeof(fonts)
            r["details"].append(f"字体: {len(fonts)} 个")

        r["ram_items"] = total
        r["ram_bytes"] = rb if total else 0
        _append_policy_stats(r, "daily_check.decoded", "daily_check.images", "daily_check.fonts")
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
        if isinstance(img, tuple) and len(img) == 2:
            img = img[1]
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

        arrays = _snapshot(mod, "_arrays")
        count = len(arrays)
        rb = sys.getsizeof(arrays)
        for k, entry in arrays.items():
            rb += sys.getsizeof(k) + sys.getsizeof(entry)
            arr = entry[1] if isinstance(entry, tuple) and len(entry) > 1 else None
            if arr is not None and hasattr(arr, "nbytes"):
                rb += int(arr.nbytes)
        if count:
            r["details"].append(f"解码图片数组: {count} 个")
        _append_policy_stats(r, "kokomi.arrays")
        r["ram_items"] = count
        r["ram_bytes"] = rb if count else 0
    except Exception as e:
        r["error"] = str(e)
    return r


def _inspect_asset_cache() -> Dict[str, Any]:
    r = _new("asset_cache 共享静态资源", "")
    try:
        from utils import cache as mod

        rb = 0
        total = 0

        img_r = _images_bytes(_snapshot(mod, "_images"))
        if img_r[0]:
            total += img_r[0]
            rb += img_r[1]
            r["details"].append(f"图片: {img_r[0]} 张")

        fonts = _snapshot(mod, "_fonts")
        if fonts:
            total += len(fonts)
            rb += sys.getsizeof(fonts)
            r["details"].append(f"字体: {len(fonts)} 个")

        b64 = _snapshot(mod, "_b64")
        if b64:
            total += len(b64)
            rb += sys.getsizeof(b64)
            btotal = 0
            for k, v in b64.items():
                rb += sys.getsizeof(k)
                if isinstance(v, tuple) and len(v) == 2:
                    v = v[1]
                btotal += _blob_len(v)
            rb += btotal
            r["details"].append(f"base64: {len(b64)} 个")

        r["ram_items"] = total
        r["ram_bytes"] = rb if total else 0
        _append_policy_stats(r, "asset_cache.images", "asset_cache.fonts", "asset_cache.base64")
    except Exception as e:
        r["error"] = str(e)
    return r


def _inspect_preload() -> Dict[str, Any]:
    r = _new("启动预热", "")
    try:
        from utils import cache as cache_preload

        s = cache_preload.get_summary()
        if not s:
            r["details"].append("未执行（非 ram 模式或尚未完成）")
            return r
        if not s.get("enabled"):
            r["details"].append(f"{s.get('mode')} 模式不预热")
            return r
        r["ram_items"] = s.get("items", 0)
        r["ram_bytes"] = s.get("bytes", 0)
        r["details"].append(f"耗时: {s.get('seconds', 0)}s")
        r["details"].append(f"内存上限: {_fmt(s.get('budget_bytes', 0))}")
        r["details"].append(f"估算: {_fmt(s.get('estimated_bytes', 0))}")
        if s.get("skipped"):
            r["details"].append(f"因超上限跳过: {s['skipped']} 项")
        for reason, count in (s.get("skip_reasons") or {}).items():
            r["details"].append(f"跳过原因 {reason}: {count} 项")
        for g in s.get("groups", []):
            if g.get("error"):
                r["details"].append(f"{g['label']}: 失败 {g['error']}")
            elif g.get("items") or g.get("skipped"):
                line = f"{g['label']}: {g['items']} 项"
                if g.get("bytes"):
                    line += f" / {_fmt(g['bytes'])}"
                if g.get("skipped"):
                    line += f"（跳过 {g['skipped']}）"
                if g.get("reason"):
                    line += f"，原因 {g['reason']}"
                r["details"].append(line)
    except Exception as e:
        r["error"] = str(e)
    return r


def _append_policy_stats(result: Dict[str, Any], *names: str) -> None:
    try:
        from utils.cache import get_cache_stats

        stats = get_cache_stats()
    except Exception:
        return
    for name in names:
        stat = stats.get(name)
        if not stat:
            continue
        result["details"].append(
            f"策略: {stat.get('bytes', 0)}B / 命中 {stat.get('hits', 0)} / "
            f"未命中 {stat.get('misses', 0)} / 淘汰 {stat.get('evictions', 0)} / "
            f"跳过 {stat.get('skips', 0)}"
        )


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
    from utils.cache import get_mode

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
        _inspect_preload(),
    ]

    return memory, mode, results
