import io
import json
import math
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from utils.cache import get_font, get_image

from .service import PAGE_SIZE


ASSETS = Path(__file__).parent / "assets"
NAMES = json.loads((ASSETS / "names.json").read_text(encoding="utf-8"))
LOCAL_TIME = timezone(timedelta(hours=8))
RESAMPLE = Image.Resampling.LANCZOS
INK = "#24232b"


def _number(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _clean(value):
    return "".join(
        character
        for character in str(value or "")[:4096]
        if character == "\n" or not unicodedata.category(character).startswith("C")
    )


def _image(path):
    return get_image(ASSETS / path).copy()


def _sprite(key, package="AccountInfo"):
    return _image(f"ui/{package}/{key}.png")


def _paste(canvas, image, xy, size=None):
    if size is not None:
        image = image.resize(size, RESAMPLE)
    canvas.alpha_composite(image, tuple(map(int, xy)))


def _background(size):
    canvas = _sprite("kn6fq3y", "Common").resize(size, RESAMPLE)
    _paste(canvas, _sprite("f3tl12"), (20, 20), (size[0] - 40, size[1] - 40))
    return canvas


def _text(canvas, value, box, size=30, color=INK, align="left", minimum=16):
    value = _clean(value).replace("\n", " ")
    left, top, width, height = box
    draw = ImageDraw.Draw(canvas)
    font = get_font(ASSETS / "JingNanBoBoHei.ttf", size)
    while size > minimum and draw.textbbox((0, 0), value, font=font)[2] > width:
        size -= 1
        font = get_font(ASSETS / "JingNanBoBoHei.ttf", size)
    if draw.textlength(value, font=font) > width:
        while value and draw.textlength(value + "…", font=font) > width:
            value = value[:-1]
        value += "…"
    bounds = draw.textbbox((0, 0), value, font=font)
    measured = draw.textlength(value, font=font)
    x = left + (width - measured) / 2 if align == "center" else left
    y = top + (height - bounds[3] + bounds[1]) / 2 - bounds[1]
    draw.text((round(x), round(y)), value, font=font, fill=color)


def _wrap(value, width, size=28):
    font = get_font(ASSETS / "JingNanBoBoHei.ttf", size)
    lines = []
    for paragraph in _clean(value).split("\n"):
        line = ""
        for character in paragraph:
            if line and font.getlength(line + character) > width:
                lines.append(line)
                line = ""
            line += character
        lines.append(line)
    return lines


def _png(canvas):
    result = io.BytesIO()
    canvas.convert("RGB").save(result, format="PNG", optimize=True)
    return result.getvalue()


def _hero(hero_id):
    return NAMES["heroes"].get(
        str(hero_id), f"角色 {_number(hero_id)}" if hero_id else "未提供角色"
    )


def _mode(mode_id):
    return NAMES["modes"].get(
        str(mode_id), f"模式 {_number(mode_id)}" if mode_id else "未提供模式"
    )


def _time(timestamp):
    try:
        value = int(timestamp)
        if value <= 0:
            return "时间未提供"
        return datetime.fromtimestamp(value, LOCAL_TIME).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OverflowError, OSError):
        return "时间未提供"


def _identity(snapshot):
    info = snapshot.get("info") or {}
    return (
        info.get("name") or "未提供昵称",
        info.get("lv"),
        str(snapshot.get("uid", "—")),
    )


def _header(canvas, title, snapshot, width=1280):
    name, level, uid = _identity(snapshot)
    _paste(canvas, _sprite("f3tl16"), (60, 50), (width - 120, 132))
    _text(canvas, title, (90, 64, width - 180, 45), 38)
    _text(canvas, name, (90, 120, width - 630, 38), 28)
    _text(canvas, f"UID：{uid}", (width - 480, 120, 390, 38), 24, align="center")


def render_message(title, lines):
    if isinstance(lines, str):
        lines = [lines]
    wrapped = []
    for line in list(lines)[:40]:
        wrapped.extend(_wrap(line, 1050))
        wrapped.append("")
    wrapped = wrapped[:44]
    while wrapped and not wrapped[-1]:
        wrapped.pop()
    height = max(500, math.ceil((155 + 43 * len(wrapped)) / 0.85) + 120)
    canvas = _background((1280, height))
    _paste(canvas, _sprite("f3tl16"), (60, 60), (1160, height - 120))
    _text(canvas, title, (110, 86, 1060, 66), 44)
    for index, line in enumerate(wrapped):
        _text(canvas, line, (110, 176 + index * 43, 1050, 40), 28)
    return _png(canvas)


def render_profile(snapshot):
    canvas = _sprite("kn6fq3y", "Common").resize((1920, 1080), RESAMPLE)
    _paste(canvas, _sprite("f3tl12"), (390, 98))
    _paste(canvas, _image("art/UT_Hero_Card_101.png"), (413, 122), (654, 826))
    _paste(canvas, _sprite("f3tl1c"), (964, 108))
    _paste(canvas, _sprite("it6m2u"), (1063, 175))
    _text(canvas, "统计资料", (1090, 117, 365, 46), 30, align="center")
    show = snapshot.get("show") or {}
    statistics = show.get("statistics") or {}
    if not show.get("isShowData"):
        _text(canvas, "该玩家未公开统计资料", (1085, 318, 365, 60), 30, align="center")
    elif not statistics:
        _text(canvas, "暂无统计资料", (1085, 318, 365, 60), 30, align="center")
    else:
        fields = (
            ("累计参与局数", "fightCount"),
            ("累计胜利局数", "winFightCount"),
            ("拥有角色数量", "roleCardCount"),
            ("最常用角色", "useHero"),
            ("拥有装扮数量", "adornCount"),
            ("拥有皮肤数量", "skinCount"),
        )
        for index, (label, key) in enumerate(fields):
            value = statistics.get(key)
            value = (
                _hero(value)
                if key == "useHero" and value
                else "—"
                if value is None
                else str(value)
            )
            _text(canvas, f"{label}：{value}", (1085, 181 + index * 66, 345, 44), 29)
    _paste(canvas, _sprite("m1i721"), (1015, 574), (48, 48))
    _paste(canvas, _sprite("m1i722"), (1015, 574), (48, 48))
    _text(canvas, str(show.get("praiseNum", "—")), (1073, 574, 270, 49), 34)
    _paste(canvas, _sprite("f3tl16"), (872, 659), (740, 278))
    name, level, uid = _identity(snapshot)
    _text(canvas, name, (919, 679, 634, 62), 40)
    _text(
        canvas, f"等级 {level if level is not None else '—'}", (922, 752, 260, 42), 28
    )
    _text(canvas, f"UID：{uid}", (922, 804, 634, 44), 28)
    _text(
        canvas,
        "战绩已公开" if show.get("isShowFight") else "战绩未公开",
        (922, 868, 630, 37),
        25,
        "#66636f",
    )
    _text(canvas, "固定主题 · 帕露南", (460, 904, 370, 40), 22, "white", align="center")
    return _png(canvas.crop((360, 75, 1642, 967)))


def render_records(snapshot, page=1):
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise ValueError("战绩页码应为正整数")
    show = snapshot.get("show") or {}
    if not show.get("isShowFight"):
        return render_message("近期战绩", ["该玩家未公开对局记录"])
    records = show.get("record") or []
    pages = max(1, math.ceil(len(records) / PAGE_SIZE))
    if page > pages:
        raise ValueError(f"战绩仅有 {pages} 页")
    if not records:
        return render_message("近期战绩", ["暂无公开对局记录"])
    canvas = _background((1280, 930))
    _header(canvas, "近期战绩", snapshot)
    _paste(canvas, _sprite("f3tl16"), (60, 206), (1160, 645))
    _text(canvas, "序号        对局时间 / 模式", (105, 218, 590, 38), 23, "#625e6d")
    _text(canvas, "名次", (735, 218, 120, 38), 23, "#625e6d", align="center")
    _text(canvas, "使用角色", (891, 218, 250, 38), 23, "#625e6d", align="center")
    start = (page - 1) * PAGE_SIZE
    for index, row in enumerate(records[start : start + PAGE_SIZE]):
        y = 271 + index * 86
        _paste(canvas, _sprite("f3tl1i"), (90, y), (1100, 79))
        _text(
            canvas,
            f"{start + index + 1:02d}",
            (107, y + 12, 65, 51),
            32,
            "white",
            align="center",
        )
        _text(canvas, _time(row.get("time")), (193, y + 2, 480, 37), 25, "white")
        _text(canvas, _mode(row.get("mapType")), (193, y + 39, 480, 33), 23, "#f4f0f7")
        rank = _number(row.get("rank"))
        _text(
            canvas,
            f"第 {rank} 名" if rank > 0 else "未提供",
            (730, y + 12, 130, 51),
            25,
            align="center",
        )
        _text(
            canvas, _hero(row.get("heroId")), (895, y + 12, 255, 51), 25, align="center"
        )
    _text(
        canvas,
        f"第 {page} / {pages} 页 · 共 {len(records)} 场",
        (80, 833, 1120, 42),
        25,
        "white",
        align="center",
    )
    return _png(canvas)


def render_detail(snapshot):
    show = snapshot.get("show") or {}
    if not show.get("isShowFight"):
        return render_message("对局详情", ["该玩家未公开对局记录"])
    details = snapshot.get("details") or []
    if not details:
        return render_message("对局详情", ["暂无该对局的公开详情"])
    details = details[:16]
    rows = math.ceil(len(details) / 4)
    width, height = 1600, 280 + rows * 530
    canvas = _background((width, height))
    _header(canvas, "对局详情", snapshot, width)
    selected = snapshot.get("selected") or {}
    _text(
        canvas,
        f"{_time(selected.get('time'))}  ·  {_mode(selected.get('mapType'))}",
        (100, 193, 1400, 45),
        27,
        "white",
        align="center",
    )
    for index, player in enumerate(details):
        x, y = 66 + index % 4 * 372, 257 + index // 4 * 530
        _paste(canvas, _sprite("it6m2r"), (x, y), (350, 497))
        rank = _number(player.get("rank"))
        if 1 <= rank <= 4:
            _paste(
                canvas,
                _sprite(("zhztq", "zhztr", "zhzts", "zhztt")[rank - 1]),
                (x + 68, y + 10),
                (135, 110),
            )
        else:
            _text(
                canvas,
                f"第 {rank} 名" if rank else "名次未提供",
                (x + 15, y + 28, 238, 72),
                30,
                "white",
                align="center",
            )
        _text(
            canvas,
            player.get("name") or "未提供昵称",
            (x + 15, y + 119, 238, 46),
            29,
            align="center",
        )
        hero_id = str(_number(player.get("heroId")))
        portrait = ASSETS / "portraits" / f"UT_Hero_ProfilePhoto_{hero_id}.png"
        if hero_id in NAMES["heroes"] and portrait.is_file():
            _paste(canvas, get_image(portrait).copy(), (x + 84, y + 183), (100, 100))
        else:
            _paste(canvas, _sprite("m1i721"), (x + 84, y + 183), (100, 100))
            _text(
                canvas, "？", (x + 84, y + 183, 100, 100), 45, "white", align="center"
            )
        _text(
            canvas,
            "角色图示",
            (x + 15, y + 288, 238, 26),
            18,
            "#7b7483",
            align="center",
        )
        _text(
            canvas,
            _hero(player.get("heroId")),
            (x + 15, y + 323, 238, 38),
            25,
            align="center",
        )
        _text(
            canvas,
            f"星级 {_number(player.get('lv'))}  ·  金币 {_number(player.get('gold'))}",
            (x + 15, y + 377, 238, 37),
            24,
            align="center",
        )
        status = (
            "已放弃对局"
            if player.get("isGiveUp")
            else f"玩家等级 {_number(player.get('playerLevel'))}"
        )
        _text(canvas, status, (x + 15, y + 438, 238, 32), 21, "white", align="center")
    return _png(canvas)


def render_notice(title, lines):
    return render_message(title, lines)


def render_help():
    return render_message(
        "吉星派对 · 查询帮助",
        [
            "吉星绑定 UID  ·  设置默认查询玩家",
            "吉星资料 [UID]  ·  查看公开资料与统计",
            "吉星战绩 [UID] [页码]  ·  每页六场，按近期顺序展示",
            "吉星战绩 第2页  ·  翻看已绑定玩家的战绩",
            "吉星对局 [UID] 序号  ·  查看战绩列表中对应对局",
            "吉星状态  ·  查看绑定与查询账号配置状态",
            "吉星解绑  ·  移除默认查询玩家",
            "方括号中的内容可以省略；省略 UID 时使用已绑定玩家。",
            "绑定仅用于快捷查询。资料和对局按玩家公开范围展示。",
        ],
    )
