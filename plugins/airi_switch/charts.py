"""用 PIL + numpy 画统计图(项目里没有 matplotlib)。

- ``draw_pie``:单个饼图,扇区=各会话(群/私聊),带图例和条数/占比。
- ``draw_summary``:跨 bot 汇总条形图,每个 bot 一组「收 vs 发」总量。

所有函数返回 PNG bytes。CJK 字体复用 airi_kokomi_wows/fonts/SHSCN.ttf。
"""

import math
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# 优先使用系统已装的 Noto Sans CJK SC。解析顺序:
# fc-match 按家族名 -> 常见 Linux 安装路径 -> 项目自带 SHSCN.ttf 兜底(保证不崩)。
_FONT_FAMILY = "Noto Sans CJK SC"

_NOTO_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

_FALLBACK_PATH = (
    Path(__file__).resolve().parents[1]
    / "airi_kokomi_wows"
    / "fonts"
    / "SHSCN.ttf"
)


def _fc_match() -> Optional[Tuple[str, int]]:
    """用 fontconfig 把家族名解析成 (文件路径, face index)。没有 fc-match 或解析失败返回 None。"""
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
    """解析一次字体来源,返回 (路径, index)。"""
    matched = _fc_match()
    if matched:
        return matched
    for cand in _NOTO_CANDIDATES:
        if Path(cand).is_file():
            return cand, 0
    return str(_FALLBACK_PATH), 0


_FONT_SRC, _FONT_INDEX = _resolve_font_source()

_BG = (245, 247, 250)
_FG = (40, 44, 52)
_SUB = (120, 128, 140)

# 扇区/柱子取色板,循环使用
_PALETTE = [
    (94, 129, 244), (244, 129, 129), (129, 199, 132), (255, 183, 77),
    (149, 117, 205), (77, 208, 225), (240, 98, 146), (161, 136, 127),
    (120, 144, 156), (174, 213, 129), (255, 138, 101), (79, 195, 247),
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_SRC, size, index=_FONT_INDEX)
    except Exception:
        try:
            return ImageFont.truetype(str(_FALLBACK_PATH), size)
        except Exception:
            return ImageFont.load_default()


def _color(i: int) -> Tuple[int, int, int]:
    return _PALETTE[i % len(_PALETTE)]


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    return int(draw.textlength(text, font=font))


def _encode(img: Image.Image) -> bytes:
    """饼图/条形图是纯色块+文字,量化到 256 色 + PNG optimize,体积明显下降且基本无损。"""
    buf = BytesIO()
    img.convert("RGB").quantize(colors=256, method=Image.MEDIANCUT).save(
        buf, format="PNG", optimize=True
    )
    return buf.getvalue()


def _sorted_items(counts: Dict[str, int]) -> List[Tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)


def _paste_avatar(img: Image.Image, avatar, xy: Tuple[int, int], size: int) -> None:
    """把头像 avatar(bytes 或 PIL Image)缩放成 size 的圆形贴到 (x,y)。avatar 为空则跳过。"""
    if not avatar:
        return
    try:
        av = avatar if isinstance(avatar, Image.Image) else Image.open(BytesIO(avatar))
        av = av.convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        img.paste(av, xy, mask)
    except Exception:
        pass  # 头像坏了不影响出图


def draw_pie(title: str, counts: Dict[str, int], label_of=None, avatar_of=None) -> bytes:
    """counts: {会话id: 条数}。label_of(会话id)->显示名,缺省用原 id。"""
    return _encode(_render_pie(title, counts, label_of, avatar_of))


def _stack_pies(top_pie, bottom_pie, label_of=None, avatar_of=None) -> Image.Image:
    """把收/发两张饼图竖直拼成一张 Image。"""
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
                     label_of=None, avatar_of=None) -> bytes:
    """把两张饼图(收/发)竖直拼成一张。每项为 (标题, counts)。"""
    return _encode(_stack_pies(top_pie, bottom_pie, label_of, avatar_of))


def render_bot_cell(header: str, top_pie, bottom_pie, label_of=None, avatar_of=None,
                    header_avatar=None) -> Image.Image:
    """一个 bot 的单元格:顶部标题栏(可带 bot 头像) + 收/发拼接饼图,返回 Image(供网格拼接)。"""
    pies = _stack_pies(top_pie, bottom_pie, label_of, avatar_of)
    hh = 64  # 标题栏高度
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


def draw_grid(cells: List[Image.Image], cols: int = 4) -> bytes:
    """把多个 bot 单元格排成网格(每行 cols 个),返回 PNG bytes。"""
    if not cells:
        img = Image.new("RGB", (400, 200), _BG)
        d = ImageDraw.Draw(img)
        msg = "今日暂无数据"
        f = _font(40)
        d.text(((400 - int(f.getlength(msg))) // 2, 80), msg, font=f, fill=_SUB)
        return _encode(img)

    gap = 20
    cw = max(c.width for c in cells)
    rows = (len(cells) + cols - 1) // cols
    # 每行高度取该行最高单元格
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
            canvas.paste(c, (x, y))
            x += cw + gap
        y += row_h[r] + gap
    return _encode(canvas)


def _truncate(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    """一行放不下就在末尾省略。"""
    if font.getlength(text) <= max_w:
        return text
    while text and font.getlength(text + "…") > max_w:
        text = text[:-1]
    return text + "…"


def _norm_label(raw) -> Tuple[str, str]:
    """label_of 的返回统一成 (第一行群名, 第二行群号行)。兼容纯字符串。"""
    if isinstance(raw, (tuple, list)):
        line1 = str(raw[0]) if len(raw) > 0 else ""
        line2 = str(raw[1]) if len(raw) > 1 else ""
        return line1, line2
    return str(raw), ""


def _render_pie(title: str, counts: Dict[str, int], label_of=None, avatar_of=None) -> Image.Image:
    """画一张饼图,返回 PIL Image(不编码,便于拼接)。avatar_of(会话id)->头像 bytes/Image。"""
    label_of = label_of or (lambda k: k)
    avatar_of = avatar_of or (lambda k: None)
    items = _sorted_items({k: v for k, v in counts.items() if v > 0})
    total = sum(v for _, v in items)

    W = 1080
    top = 90
    pie_cx, pie_cy, pie_r = 260, top + 230, 180
    legend_x = 500
    av_x = legend_x + 40      # 头像列
    name_x = av_x + 74        # 文字列(头像宽 64 + 间距)
    line_h = 32       # 图例每行文字高度
    row_pad = 12      # 每行上下留白
    right_margin = 40

    f_title = _font(40)
    f_legend = _font(26)
    f_small = _font(22)

    # 先算好每个图例项(第一行群名截断/第二行群号),才能定整图高度
    legend = []  # (i, key, val, stat, name, id_line)
    for i, (key, val) in enumerate(items):
        pct = 100.0 * val / total if total else 0.0
        stat = f"{val}  ({pct:.1f}%)"
        stat_w = int(f_small.getlength(stat))
        name_max_w = (W - right_margin - stat_w - 20) - name_x
        name, id_line = _norm_label(label_of(key))
        name = _truncate(name, f_legend, name_max_w)  # 群名写不下就省略
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
        # 单扇区占满时 pieslice(start,start+360) 画不出,给它整圆
        if len(items) == 1:
            d.ellipse(box, fill=_color(i))
        else:
            d.pieslice(box, start, start + sweep, fill=_color(i))
        start += sweep

    # 中心挖白做成环形,顺带写总量
    inner = pie_r * 0.52
    d.ellipse(
        [pie_cx - inner, pie_cy - inner, pie_cx + inner, pie_cy + inner], fill=_BG
    )
    tot_txt = str(total)
    d.text((pie_cx - _text_w(d, tot_txt, f_title) // 2, pie_cy - 34), tot_txt, font=f_title, fill=_FG)
    d.text((pie_cx - _text_w(d, "总计", f_small) // 2, pie_cy + 8), "总计", font=f_small, fill=_SUB)

    # 图例
    ly = top
    for i, key, val, stat, name, id_line in legend:
        two = bool(id_line)
        d.rounded_rectangle([legend_x, ly, legend_x + 28, ly + 28], radius=6, fill=_color(i))
        # 头像:双行取两行高,单行取一行高
        av_size = (2 * line_h if two else line_h)
        _paste_avatar(img, avatar_of(key), (av_x, ly), av_size)
        d.text((name_x, ly + 1), name, font=f_legend, fill=_FG)         # 第一行:群名
        if two:
            d.text((name_x, ly + 1 + line_h), id_line, font=f_small, fill=_SUB)  # 第二行:群号,灰字
        # 条数/占比对齐到该项第一行右侧
        d.text((W - right_margin - _text_w(d, stat, f_small), ly + 3), stat, font=f_small, fill=_SUB)
        ly += (2 if two else 1) * line_h + row_pad

    return img


def draw_summary(bot_totals: List[Tuple]) -> bytes:
    """bot_totals: [(bot昵称, bot_id, 收总量, 发总量[, 头像]), ...]。跨 bot 横向分组条形图。
    左侧头像 + 名称两行:第一行昵称,第二行 bot_id 灰字。"""
    W = 1040
    top = 110
    left = 340           # 左侧留给 bot 名(加宽,图表右移)
    right_pad = 120      # 右侧留给数值
    bar_area = W - left - right_pad
    group_h = 96         # 每个 bot 一组(两根柱)
    av_size = 64         # 头像(约两行文字高)
    text_x = 30 + av_size + 14  # 头像右侧起文字
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
    # 顶部图例
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
        # 头像(两行文字高),整体在该组内垂直居中
        _paste_avatar(img, avatar, (30, y + group_h // 2 - av_size // 2), av_size)
        d.text((text_x, y + group_h // 2 - 34), nm, font=f_name, fill=_FG)
        d.text((text_x, y + group_h // 2 + 2), idl, font=f_id, fill=_SUB)

        for idx, (val, col) in enumerate(((recv, recv_c), (sent, sent_c))):
            by = y + idx * (bar_h + 6)
            w = int(bar_area * val / peak)
            d.rounded_rectangle([left, by, left + max(w, 2), by + bar_h], radius=6, fill=col)
            d.text((left + max(w, 2) + 12, by + 2), str(val), font=f_val, fill=_SUB)
        y += group_h

    return _encode(img)
