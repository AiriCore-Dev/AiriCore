import time
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from utils.cache_mode import get_mode, get_preload_budget_bytes, is_ram

_ROOT = Path(__file__).resolve().parents[1]
_PLUGINS = _ROOT / "plugins"


class Budget:

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0
        self.estimated = 0
        self.skipped = 0
        self.reasons = {}

    def ok(self) -> bool:
        return self.limit <= 0 or self.used < self.limit

    def can_fit(self, n: int) -> bool:
        return self.limit <= 0 or self.used + max(0, int(n)) <= self.limit

    def add(self, n: int, estimate: int = None) -> None:
        self.used += max(0, int(n))
        self.estimated += max(0, int(n if estimate is None else estimate))

    def skip(self, n: int = 1, reason: str = "budget") -> None:
        self.skipped += n
        self.reasons[reason] = self.reasons.get(reason, 0) + n


def _iter_files(base: Path, patterns, recursive: bool = True) -> List[Path]:
    if not base.is_dir():
        return []
    out: List[Path] = []
    globber = base.rglob if recursive else base.glob
    for pat in patterns:
        try:
            out.extend(p for p in globber(pat) if p.is_file())
        except Exception:
            continue
    return sorted(set(out))


def _image_bytes(img) -> int:
    try:
        w, h = img.size
        return w * h * len(img.mode)
    except Exception:
        return 0


def _decoded_channels(pil_img) -> int:
    if pil_img.mode == "L":
        return 1
    if pil_img.mode == "P" and "transparency" not in pil_img.info:
        return 3
    return 4


def _estimate_file(path: Path, loader) -> int:
    if loader in (_load_shared_image, _load_dc_image, _load_kokomi_array):
        try:
            with Image.open(path) as image:
                return image.width * image.height * _decoded_channels(image)
        except Exception:
            return 0
    if loader in (_load_shared_b64, _load_dc_b64, _load_whateat_b64):
        try:
            return 9 + ((path.stat().st_size + 2) // 3) * 4
        except OSError:
            return 0
    return 0


def _load_shared_image(path: Path) -> int:
    from utils import asset_cache

    return _image_bytes(asset_cache.get_image(path))


def _load_shared_b64(path: Path) -> int:
    from utils import asset_cache

    data = asset_cache.get_b64(path)
    return len(data) if data else 0


def _load_dc_image(path: Path) -> int:
    from plugins.airi_daily_check.base import cache as dc_cache

    return _image_bytes(dc_cache.get_image(str(path)))


def _load_dc_b64(path: Path) -> int:
    import base64

    from plugins.airi_daily_check.base import cache as dc_cache

    key = str(path)

    def _build():
        with open(key, "rb") as f:
            return "base64://" + base64.b64encode(f.read()).decode()

    return len(dc_cache.get_or_build("localpath_b64", key, _build) or "")


def _load_kokomi_array(path: Path) -> int:
    from plugins.airi_kokomi_wows import cache as kk_cache

    arr = kk_cache.get_array(str(path))
    return int(getattr(arr, "nbytes", 0))


def _load_whateat_b64(path: Path) -> int:
    from plugins.nonebot_plugin_whateat_pic import cache as we_cache

    data = we_cache.get_b64(path)
    return len(data) if data else 0


_IMG = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp")

def _asset_groups() -> List[Dict[str, Any]]:
    kk = _PLUGINS / "airi_kokomi_wows"
    dc = _PLUGINS / "airi_daily_check"
    groups: List[Dict[str, Any]] = [
        {"label": "cchess 棋盘棋子", "dir": _PLUGINS / "nonebot_plugin_cchess" / "resources" / "images",
         "patterns": _IMG, "loader": _load_shared_image},
        {"label": "airi_status 素材", "dir": _PLUGINS / "airi_status" / "resources" / "images",
         "patterns": _IMG, "loader": _load_shared_image},
        {"label": "minesweeper 皮肤", "dir": _PLUGINS / "nonebot_plugin_minesweeper" / "resources" / "skins",
         "patterns": ("*.bmp",), "loader": _load_shared_image},
        {"label": "mcrcon 素材", "dir": _PLUGINS / "airi_mcrcon" / "utils",
         "patterns": _IMG, "loader": _load_shared_image},
        {"label": "mcrcon 道具", "dir": _PLUGINS / "airi_mcrcon" / "item",
         "patterns": _IMG, "loader": _load_shared_image},
        {"label": "airi_reply 语音", "dir": _PLUGINS / "airi_reply",
         "patterns": ("*.wav",), "loader": _load_shared_b64},
        {"label": "airi_help 图片", "dir": _PLUGINS / "airi_help",
         "patterns": _IMG, "loader": _load_shared_b64},
        {"label": "airi_new_group 素材", "dir": _PLUGINS / "airi_new_group",
         "patterns": _IMG + ("*.wav",), "loader": _load_shared_b64},
        {"label": "daily_check 通用素材", "dir": dc / "utils",
         "patterns": _IMG, "loader": _load_dc_image, "recursive": False},
        {"label": "daily_check 数独素材", "dir": dc / "utils" / "sudoku",
         "patterns": ("*.png",), "loader": _load_dc_image},
        {"label": "daily_check 抽卡底图", "dir": dc / "utils" / "gacha",
         "patterns": _IMG, "loader": _load_dc_image},
        {"label": "daily_check 运势图", "dir": dc / "utils" / "jrys",
         "patterns": _IMG, "loader": _load_dc_b64},
        {"label": "daily_check 默认背景", "dir": dc / "info_bg",
         "patterns": _IMG, "loader": _load_dc_image, "recursive": False},
        {"label": "kokomi 舰船图标", "dir": kk / "png" / "ship_icon",
         "patterns": _IMG, "loader": _load_kokomi_array},
        {"label": "kokomi 国家旗帜", "dir": kk / "png" / "nation",
         "patterns": _IMG, "loader": _load_kokomi_array},
        {"label": "kokomi 成就", "dir": kk / "png" / "achievement",
         "patterns": _IMG, "loader": _load_kokomi_array},
        {"label": "kokomi 成就扩展", "dir": kk / "png" / "achievement_plus",
         "patterns": _IMG, "loader": _load_kokomi_array},
        {"label": "kokomi 军团", "dir": kk / "png" / "clan",
         "patterns": _IMG, "loader": _load_kokomi_array},
        {"label": "kokomi 列表素材", "dir": kk / "png" / "list",
         "patterns": _IMG, "loader": _load_kokomi_array},
        {"label": "kokomi 排位素材", "dir": kk / "png" / "cw",
         "patterns": _IMG, "loader": _load_kokomi_array},
        {"label": "kokomi 中文底图", "dir": kk / "png" / "bg_cn",
         "patterns": _IMG, "loader": _load_kokomi_array, "preload": False},
        {"label": "kokomi 英文底图", "dir": kk / "png" / "bg_en",
         "patterns": _IMG, "loader": _load_kokomi_array, "preload": False},
        {"label": "whateat 图片", "dir": _PLUGINS / "nonebot_plugin_whateat_pic" / "eat_pic",
         "patterns": _IMG, "loader": _load_whateat_b64},
        {"label": "whateat 饮品", "dir": _PLUGINS / "nonebot_plugin_whateat_pic" / "drink_pic",
         "patterns": _IMG, "loader": _load_whateat_b64},
    ]
    for name in ("dog_tag_custom", "dog_tag_special", "dog_tag_lesta", "dog_tag_wg", "dog_tag_2"):
        groups.append({
            "label": f"kokomi {name}", "dir": kk / "png" / name,
            "patterns": _IMG, "loader": _load_kokomi_array, "preload": False,
        })
    return groups


def _font_specs() -> List[Dict[str, Any]]:
    dc_utils = _PLUGINS / "airi_daily_check" / "utils"
    ms_fonts = _PLUGINS / "nonebot_plugin_minesweeper" / "resources" / "fonts"
    return [
        {"target": "dc", "path": dc_utils / "sakura.ttf", "sizes": (36, 56)},
        {"target": "dc", "path": dc_utils / "louxing.ttf", "sizes": (48, 60, 100, 120)},
        {"target": "dc", "path": dc_utils / "skc.ttf", "sizes": (48,)},
        {"target": "dc", "path": dc_utils / "font.ttc", "sizes": (48, 60)},
        {"target": "shared", "path": ms_fonts / "00TT.TTF", "sizes": (28,), "encoding": "utf-8"},
        {"target": "shared", "path": _PLUGINS / "airi_mcrcon" / "utils" / "font.ttf", "sizes": (36, 60)},
    ]


def _preload_fonts(budget: Budget) -> Dict[str, Any]:
    from utils import asset_cache
    from plugins.airi_daily_check.base import cache as dc_cache

    items = 0
    used = 0
    for spec in _font_specs():
        path = spec["path"]
        if not path.is_file():
            continue
        for size in spec["sizes"]:
            if not budget.ok():
                budget.skip(reason="budget")
                continue
            try:
                if spec["target"] == "dc":
                    dc_cache.get_font(str(path), size)
                else:
                    asset_cache.get_font(path, size, encoding=spec.get("encoding", ""))
                items += 1
                used += 256 * 1024
                budget.add(256 * 1024, 256 * 1024)
            except Exception:
                continue
    return {"label": "字体", "items": items, "bytes": used}


_PK_CACHES = [
    ("airi_switch 元信息", "plugins.airi_switch.cache"),
    ("airi_switch 收发统计", "plugins.airi_switch.counter"),
    ("today_waifu 头像", "plugins.nonebot_plugin_today_waifu.cache"),
    ("whateat_pic 图片", "plugins.nonebot_plugin_whateat_pic.cache"),
    ("airi_daily_check 产物", "plugins.airi_daily_check.base.cache"),
    ("airi_market 文章", "plugins.airi_market.base.cache"),
]


def _preload_pk_caches(budget: Budget) -> List[Dict[str, Any]]:
    results = []
    for label, mod_path in _PK_CACHES:
        entry = {"label": label, "items": 0, "bytes": 0}
        try:
            mod = __import__(mod_path, fromlist=["preload"])
            fn = getattr(mod, "preload", None)
            if fn is None:
                entry["error"] = "无 preload 接口"
            elif not budget.ok():
                entry["error"] = "预算已用尽, 跳过"
                budget.skip(reason="budget")
            else:
                remain = budget.limit - budget.used if budget.limit > 0 else -1
                items, used = fn(remain)
                entry["items"] = int(items)
                entry["bytes"] = int(used)
                budget.add(used, used)
        except Exception as e:
            entry["error"] = str(e)
        results.append(entry)
    return results


def _preload_assets(budget: Budget) -> List[Dict[str, Any]]:
    results = []
    for group in _asset_groups():
        base = group["dir"]
        files = _iter_files(base, group["patterns"], group.get("recursive", True))
        if not files:
            continue
        entry = {"label": group["label"], "items": 0, "bytes": 0, "skipped": 0}
        loader = group["loader"]
        if not group.get("preload", True):
            entry["skipped"] = len(files)
            entry["reason"] = "cold_group"
            budget.skip(len(files), reason="cold_group")
            results.append(entry)
            continue
        for path in files:
            estimate = _estimate_file(path, loader)
            if not budget.can_fit(estimate):
                entry["skipped"] += 1
                budget.skip(reason="budget")
                continue
            try:
                used = loader(path)
            except Exception:
                continue
            entry["items"] += 1
            entry["bytes"] += used
            budget.add(used, estimate)
        results.append(entry)
    return results


_summary: Dict[str, Any] = {}


def get_summary() -> Dict[str, Any]:
    return _summary


def run() -> Dict[str, Any]:
    global _summary
    started = time.time()
    mode = get_mode()
    if not is_ram():
        _summary = {"mode": mode, "enabled": False, "groups": [], "items": 0,
                    "bytes": 0, "estimated_bytes": 0, "skipped": 0,
                    "skip_reasons": {}, "seconds": 0.0}
        return _summary

    budget = Budget(get_preload_budget_bytes())
    groups: List[Dict[str, Any]] = []
    groups.extend(_preload_pk_caches(budget))
    groups.append(_preload_fonts(budget))
    groups.extend(_preload_assets(budget))

    items = sum(g.get("items", 0) for g in groups)
    _summary = {
        "mode": mode,
        "enabled": True,
        "groups": groups,
        "items": items,
        "bytes": budget.used,
        "estimated_bytes": budget.estimated,
        "skipped": budget.skipped,
        "skip_reasons": dict(budget.reasons),
        "budget_bytes": budget.limit,
        "seconds": round(time.time() - started, 2),
    }
    return _summary


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


def run_and_log() -> Dict[str, Any]:
    from nonebot.log import logger

    try:
        s = run()
    except Exception as e:
        logger.opt(colors=True).warning(f"<y>缓存预热失败: {e}</y>")
        return {}
    if not s.get("enabled"):
        logger.info(f"缓存模式 {s.get('mode')}，跳过启动预热")
        return s
    logger.info(
        f"缓存预热完成: {s['items']} 项 / {_fmt(s['bytes'])} / {s['seconds']}s"
        f"（上限 {_fmt(s['budget_bytes'])}）"
    )
    if s["skipped"]:
        logger.opt(colors=True).warning(
            f"<y>缓存预热达到内存上限，跳过 {s['skipped']} 项；"
            f"可调大 .env.prod 的 cache_preload_budget_mb</y>"
        )
    return s
