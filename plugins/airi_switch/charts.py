
import math
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from utils.asset_cache import get_font

_FONT_FAMILY = "Noto Sans CJK SC"

_NOTO_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

_LOCAL_CANDIDATES = [
    Path(__file__).resolve().parents[1] / "airi_status" / "resources" / "fonts" / "baotu.ttf",
    Path(__file__).resolve().parents[1] / "airi_kokomi_wows" / "fonts" / "SHSCN.ttf",
    Path(__file__).resolve().parents[1] / "airi_daily_check" / "assets" / "fonts" / "SHSCN.ttf",
]

_MAC_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]

_WIN_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def _first_local_font() -> Optional[Tuple[str, int]]:
    for cand in _LOCAL_CANDIDATES:
        if Path(cand).is_file():
            return str(cand), 0
    return None


def _fc_match() -> Optional[Tuple[str, int]]:
    if not shutil.which("fc-match"):
        return None
    try:
        out = subprocess.check_output(
            ["fc-match", "-f", "%{file}:%{index}", _FONT_FAMILY],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        if ":" in out:
            path, _, idx = out.rpartition(":")
            if path and Path(path).is_file():
                return path, int(idx) if idx.isdigit() else 0
    except Exception:
        pass
    return None


def _resolve_font_source() -> Tuple[str, int]:
    local = _first_local_font()
    if local:
        return local
    for cand in _NOTO_CANDIDATES + _MAC_CANDIDATES + _WIN_CANDIDATES:
        if Path(cand).is_file():
            return cand, 0
    matched = _fc_match()
    if matched:
        return matched
    return "", 0


_FONT_SRC: Optional[str] = None
_FONT_INDEX = 0
_FALLBACK_PATH = _LOCAL_CANDIDATES[0]


def _ensure_font_source() -> Tuple[str, int]:
    global _FONT_SRC, _FONT_INDEX
    if _FONT_SRC is None:
        _FONT_SRC, _FONT_INDEX = _resolve_font_source()
    return _FONT_SRC, _FONT_INDEX

_BG = (245, 247, 250)
_FG = (40, 44, 52)
_SUB = (120, 128, 140)

_PALETTE = [
    (94, 129, 244), (244, 129, 129), (129, 199, 132), (255, 183, 77),
    (149, 117, 205), (77, 208, 225), (240, 98, 146), (161, 136, 127),
    (120, 144, 156), (174, 213, 129), (255, 138, 101), (79, 195, 247),
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    src, index = _ensure_font_source()
    if src:
        try:
            return get_font(src, size, index=index)
        except Exception:
            pass
    for cand in _LOCAL_CANDIDATES:
        try:
            return get_font(cand, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _color(i: int) -> Tuple[int, int, int]:
    return _PALETTE[i % len(_PALETTE)]


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    return int(draw.textlength(text, font=font))


def _encode(img: Image.Image) -> bytes:
    buf = BytesIO()
    rgb = img.convert("RGB")
    if rgb.getcolors(maxcolors=4096) is None:
        rgb.save(buf, format="JPEG", quality=88, optimize=True, subsampling=1)
    else:
        rgb.quantize(colors=256, method=Image.MEDIANCUT).save(
            buf, format="PNG", optimize=True
        )
    return buf.getvalue()


_TOP_N = 20
_OTHERS_KEY = "__others__"
_MAX_GRID_CELLS = 24
_MAX_SUMMARY_ROWS = 40


def _sorted_items(counts: Dict[str, int]) -> List[Tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)


def _capped_items(counts: Dict[str, int], top_n: int = _TOP_N) -> List[Tuple[str, int]]:
    items = _sorted_items({k: v for k, v in counts.items() if v > 0})
    if len(items) <= top_n:
        return items
    head = items[:top_n]
    rest = sum(v for _, v in items[top_n:])
    head.append((_OTHERS_KEY, rest))
    return head


def _stamp_date(img: Image.Image, text: str, margin: int = 24) -> None:
    if not text:
        return
    d = ImageDraw.Draw(img)
    f = _font(26)
    tw = int(d.textlength(text, font=f))
    th = 26
    x = img.width - margin - tw
    y = img.height - margin - th
    d.text((x, y), text, font=f, fill=_SUB)


def _paste_avatar(img: Image.Image, avatar, xy: Tuple[int, int], size: int) -> None:
    if not avatar:
        return
    try:
        av = avatar if isinstance(avatar, Image.Image) else Image.open(BytesIO(avatar))
        av = av.convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        img.paste(av, xy, mask)
    except Exception:
        pass


def draw_pie(title: str, counts: Dict[str, int], label_of=None, avatar_of=None) -> bytes:
    return _encode(_render_pie(title, counts, label_of, avatar_of))


def _stack_pies(top_pie, bottom_pie, label_of=None, avatar_of=None) -> Image.Image:
    a = _render_pie(top_pie[0], top_pie[1], label_of, avatar_of)
    b = _render_pie(bottom_pie[0], bottom_pie[1], label_of, avatar_of)
    gap = 8
    W = max(a.width, b.width)
    H = a.height + gap + b.height
    canvas = Image.new("RGB", (W, H), _BG)
    canvas.paste(a, (0, 0))
    canvas.paste(b, (0, a.height + gap))
    return canvas


def draw_pies_vstack(top_pie: Tuple[str, Dict[str, int]],
                     bottom_pie: Tuple[str, Dict[str, int]],
                     label_of=None, avatar_of=None, date_text: str = "") -> bytes:
    canvas = _stack_pies(top_pie, bottom_pie, label_of, avatar_of)
    _stamp_date(canvas, date_text)
    return _encode(canvas)


def render_bot_cell(header: str, top_pie, bottom_pie, label_of=None, avatar_of=None,
                    header_avatar=None) -> Image.Image:
    pies = _stack_pies(top_pie, bottom_pie, label_of, avatar_of)
    hh = 64
    W = pies.width
    cell = Image.new("RGB", (W, hh + pies.height), _BG)
    d = ImageDraw.Draw(cell)
    f = _font(34)
    av_size = 44
    tx = 30
    if header_avatar:
        _paste_avatar(cell, header_avatar, (30, (hh - av_size) // 2), av_size)
        tx = 30 + av_size + 12
    name = _truncate(header, f, W - tx - 30)
    d.text((tx, hh // 2 - 22), name, font=f, fill=_FG)
    cell.paste(pies, (0, hh))
    return cell


def draw_grid(cells: List[Image.Image], cols: int = 4, date_text: str = "") -> bytes:
    if not cells:
        img = Image.new("RGB", (400, 200), _BG)
        d = ImageDraw.Draw(img)
        msg = "今日暂无数据"
        f = _font(40)
        d.text(((400 - int(f.getlength(msg))) // 2, 80), msg, font=f, fill=_SUB)
        _stamp_date(img, date_text)
        return _encode(img)

    cells = cells[:_MAX_GRID_CELLS]
    gap = 20
    cw = max(c.width for c in cells)
    rows = (len(cells) + cols - 1) // cols
    row_h = []
    for r in range(rows):
        row_cells = cells[r * cols:(r + 1) * cols]
        row_h.append(max(c.height for c in row_cells))
    ncols = min(cols, len(cells))
    W = gap + ncols * (cw + gap)
    H = gap + sum(row_h) + rows * gap

    canvas = Image.new("RGB", (W, H), _BG)
    y = gap
    for r in range(rows):
        x = gap
        for c in cells[r * cols:(r + 1) * cols]:
            canvas.paste(c, (x + (cw - c.width) // 2, y))
            x += cw + gap
        y += row_h[r] + gap
    _stamp_date(canvas, date_text)
    return _encode(canvas)


def _truncate(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    if font.getlength(text) <= max_w:
        return text
    while text and font.getlength(text + "…") > max_w:
        text = text[:-1]
    return text + "…"


def _norm_label(raw) -> Tuple[str, str]:
    if isinstance(raw, (tuple, list)):
        line1 = str(raw[0]) if len(raw) > 0 else ""
        line2 = str(raw[1]) if len(raw) > 1 else ""
        return line1, line2
    return str(raw), ""


def _render_pie(title: str, counts: Dict[str, int], label_of=None, avatar_of=None) -> Image.Image:
    raw_label_of = label_of or (lambda k: k)
    raw_avatar_of = avatar_of or (lambda k: None)
    hidden = max(0, len([1 for v in counts.values() if v > 0]) - _TOP_N)

    def label_of(k):
        if k == _OTHERS_KEY:
            return (f"其余 {hidden} 项合计", "")
        return raw_label_of(k)

    def avatar_of(k):
        return None if k == _OTHERS_KEY else raw_avatar_of(k)

    items = _capped_items(counts)
    total = sum(v for _, v in items)

    W = 1080
    top = 90
    pie_cx, pie_cy, pie_r = 260, top + 230, 180
    legend_x = 500
    av_x = legend_x + 40
    name_x = av_x + 74
    line_h = 32
    row_pad = 12
    right_margin = 40

    f_title = _font(40)
    f_legend = _font(26)
    f_small = _font(22)

    legend = []
    for i, (key, val) in enumerate(items):
        pct = 100.0 * val / total if total else 0.0
        stat = f"{val}  ({pct:.1f}%)"
        stat_w = int(f_small.getlength(stat))
        name_max_w = (W - right_margin - stat_w - 20) - name_x
        name, id_line = _norm_label(label_of(key))
        name = _truncate(name, f_legend, name_max_w)
        legend.append((i, key, val, stat, name, id_line))

    legend_h = sum((2 if idl else 1) * line_h + row_pad for *_, idl in legend) if legend else (line_h + row_pad)
    H = max(pie_cy + pie_r + 60, top + legend_h + 40)

    img = Image.new("RGB", (W, H), _BG)
    d = ImageDraw.Draw(img)

    d.text((40, 28), title, font=f_title, fill=_FG)

    if total == 0 or not items:
        msg = "今日暂无数据"
        d.text(((W - _text_w(d, msg, f_title)) // 2, H // 2 - 20), msg, font=f_title, fill=_SUB)
        return img

    box = [pie_cx - pie_r, pie_cy - pie_r, pie_cx + pie_r, pie_cy + pie_r]
    start = -90.0
    for i, (key, val) in enumerate(items):
        sweep = 360.0 * val / total
        if len(items) == 1:
            d.ellipse(box, fill=_color(i))
        else:
            d.pieslice(box, start, start + sweep, fill=_color(i))
        start += sweep

    inner = pie_r * 0.52
    d.ellipse(
        [pie_cx - inner, pie_cy - inner, pie_cx + inner, pie_cy + inner], fill=_BG
    )
    tot_txt = str(total)
    d.text((pie_cx - _text_w(d, tot_txt, f_title) // 2, pie_cy - 34), tot_txt, font=f_title, fill=_FG)
    d.text((pie_cx - _text_w(d, "总计", f_small) // 2, pie_cy + 8), "总计", font=f_small, fill=_SUB)

    ly = top
    for i, key, val, stat, name, id_line in legend:
        two = bool(id_line)
        d.rounded_rectangle([legend_x, ly, legend_x + 28, ly + 28], radius=6, fill=_color(i))
        av_size = (2 * line_h if two else line_h)
        _paste_avatar(img, avatar_of(key), (av_x, ly), av_size)
        d.text((name_x, ly + 1), name, font=f_legend, fill=_FG)
        if two:
            d.text((name_x, ly + 1 + line_h), id_line, font=f_small, fill=_SUB)
        d.text((W - right_margin - _text_w(d, stat, f_small), ly + 3), stat, font=f_small, fill=_SUB)
        ly += (2 if two else 1) * line_h + row_pad

    return img


def draw_summary(bot_totals: List[Tuple], date_text: str = "") -> bytes:
    bot_totals = sorted(bot_totals, key=lambda r: (r[2] + r[3]), reverse=True)[:_MAX_SUMMARY_ROWS]
    W = 1040
    top = 110
    left = 340
    right_pad = 120
    bar_area = W - left - right_pad
    group_h = 96
    av_size = 64
    text_x = 30 + av_size + 14
    H = max(top + group_h * max(len(bot_totals), 1) + 60, 300)

    img = Image.new("RGB", (W, H), _BG)
    d = ImageDraw.Draw(img)
    f_title = _font(40)
    f_name = _font(28)
    f_id = _font(22)
    f_val = _font(22)
    f_leg = _font(24)

    d.text((40, 30), "全部 Bot 收发汇总", font=f_title, fill=_FG)

    recv_c, sent_c = (94, 129, 244), (244, 129, 129)
    lx = W - 360
    d.rounded_rectangle([lx, 40, lx + 26, 66], radius=5, fill=recv_c)
    d.text((lx + 34, 40), "收", font=f_leg, fill=_FG)
    d.rounded_rectangle([lx + 120, 40, lx + 146, 66], radius=5, fill=sent_c)
    d.text((lx + 154, 40), "发", font=f_leg, fill=_FG)

    peak = max((max(r[2], r[3]) for r in bot_totals), default=0) or 1

    name_max_w = left - text_x
    y = top
    bar_h = 30
    for row in bot_totals:
        nick, botid, recv, sent = row[0], row[1], row[2], row[3]
        avatar = row[4] if len(row) > 4 else None
        nm = _truncate(str(nick), f_name, name_max_w)
        idl = _truncate(str(botid), f_id, name_max_w)
        _paste_avatar(img, avatar, (30, y + group_h // 2 - av_size // 2), av_size)
        d.text((text_x, y + group_h // 2 - 34), nm, font=f_name, fill=_FG)
        d.text((text_x, y + group_h // 2 + 2), idl, font=f_id, fill=_SUB)

        for idx, (val, col) in enumerate(((recv, recv_c), (sent, sent_c))):
            by = y + idx * (bar_h + 6)
            w = int(bar_area * val / peak)
            d.rounded_rectangle([left, by, left + max(w, 2), by + bar_h], radius=6, fill=col)
            d.text((left + max(w, 2) + 12, by + 2), str(val), font=f_val, fill=_SUB)
        y += group_h

    _stamp_date(img, date_text)
    return _encode(img)
