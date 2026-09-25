import json
import unicodedata
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from utils.cache import get_font, get_image


ASSETS = Path(__file__).parent / "assets"
PROFILE = json.loads((ASSETS / "profile.json").read_text(encoding="utf-8"))
LAYOUTS = {
    name: json.loads((ASSETS / f"{name}_layout.json").read_text(encoding="utf-8"))[
        "items"
    ]
    for name in ("AccountInfo", "Common")
}
RESAMPLE = Image.Resampling.LANCZOS


def node(component, name, package="Common"):
    return next(
        child
        for child in LAYOUTS[package][component]["children"]
        if child["name"] == name
    )


def cosmetic(section, value):
    key = str(value if value is not None else 0)
    return PROFILE[section].get(key) if key.isascii() and key.isdecimal() else None


def blank(size):
    return Image.new("RGBA", size)


def put(canvas, image, child):
    scale = child.get("scale", (1, 1))
    size = tuple(
        max(1, round(length * factor)) for length, factor in zip(image.size, scale)
    )
    x, y = child["x"], child["y"]
    pivot = child.get("pivot")
    if pivot and pivot[2]:
        x -= image.width * pivot[0]
        y -= image.height * pivot[1]
    canvas.alpha_composite(
        image.resize(size, RESAMPLE) if image.size != size else image,
        (round(x), round(y)),
    )


def sprite(child, package="Common"):
    item = LAYOUTS[package][child["source"]]
    image = get_image(ASSETS / f"ui/{package}/{item['id']}.png").copy()
    size = (child.get("width", image.width), child.get("height", image.height))
    if size == image.size:
        return image
    grid = item.get("scale9Grid")
    if not grid:
        return image.resize(size, RESAMPLE)
    x, y, width, height = grid
    xs, ys = [0, x, x + width, image.width], [0, y, y + height, image.height]
    dx = [0, x, size[0] - (image.width - x - width), size[0]]
    dy = [0, y, size[1] - (image.height - y - height), size[1]]
    result = blank(size)
    for row in range(3):
        for column in range(3):
            target = (dx[column + 1] - dx[column], dy[row + 1] - dy[row])
            if min(target) > 0:
                tile = image.crop((xs[column], ys[row], xs[column + 1], ys[row + 1]))
                result.alpha_composite(
                    tile.resize(target, RESAMPLE), (dx[column], dy[row])
                )
    return result


def shape(child):
    size = (child["width"], child["height"])
    image = blank(size)
    draw = ImageDraw.Draw(image)
    radius = child.get("cornerRadius", [0])[0]
    draw.rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius, fill=tuple(child["color"])
    )
    return image


def mask(image, component, package="Common"):
    item = LAYOUTS[package][component]
    child = item["children"][item["mask"]]
    layer = blank(image.size)
    put(layer, sprite(child, package) if child["type"] == 0 else shape(child), child)
    image.putalpha(ImageChops.multiply(image.getchannel("A"), layer.getchannel("A")))
    return image


def loader(canvas, row, child, offset=None):
    if not row or not row.get("path"):
        return False
    image = get_image(ASSETS / row["path"]).copy()
    width, height = child["width"], child["height"]
    if child.get("fill") == 1:
        factor = min(width / image.width, height / image.height)
        image = image.resize(
            (max(1, round(image.width * factor)), max(1, round(image.height * factor))),
            RESAMPLE,
        )
    elif child.get("fill") == 4:
        image = image.resize((width, height), RESAMPLE)
    x = (width - image.width) * (child.get("align", 0) / 2)
    y = (height - image.height) * (child.get("verticalAlign", 0) / 2)
    if offset and any(offset):
        x, y = offset[0], -offset[1]
    canvas.alpha_composite(image, (round(child["x"] + x), round(child["y"] + y)))
    return True


def text_image(value, child, fit=False):
    value = "".join(
        c for c in str(value)[:4096] if not unicodedata.category(c).startswith("C")
    )
    name = {"Impact_TMP": "Impact", None: "SIMHEI"}.get(
        child.get("font"), child.get("font")
    )
    size = child["fontSize"]
    width, height = child["width"], child["height"]
    if fit:
        size = min(size, height - 4)
    spacing = child.get("letterSpacing", 0)
    font = get_font(ASSETS / f"{name}.ttf", size)
    if fit:
        while (
            size > 10
            and font.getlength(value) + spacing * max(0, len(value) - 1) > width - 4
        ):
            size -= 1
            font = get_font(ASSETS / f"{name}.ttf", size)
    image = blank((width, height))
    draw = ImageDraw.Draw(image)
    bounds = font.getbbox(value)
    measured = font.getlength(value) + spacing * max(0, len(value) - 1)
    x = 2 + max(0, width - 4 - measured) * child.get("align", 0) / 2
    y = 2 + max(0, height - 4 - size) * child.get("verticalAlign", 0) / 2
    y = round(y - bounds[1] + max(0, size - bounds[3] + bounds[1]) / 2)
    parts = (
        [(value, 0)]
        if not spacing
        else [
            (letter, font.getlength(value[:index]) + spacing * index)
            for index, letter in enumerate(value)
        ]
    )
    for part, offset in parts:
        draw.text(
            (round(x + offset), y),
            part,
            font=font,
            fill=tuple(child["color"]),
            stroke_width=round(child.get("outline", 0)),
            stroke_fill=tuple(child.get("outlineColor", child["color"])),
        )
    return image


def paint_character(canvas, snapshot):
    selected = (snapshot.get("show") or {}).get("standingPainting")
    row = cosmetic("paintings", selected)
    layer = blank((2000, 2200))
    if not loader(
        layer, row, node("ak421h", "loader_Skin_Image"), (row or {}).get("offset")
    ):
        return "立绘资源未收录" if selected else "未设置展示立绘"
    clipped = blank((836, 828))
    put(clipped, layer, node("f3tl1y", "com_Skin", "AccountInfo"))
    put(
        canvas,
        mask(clipped, "f3tl1y", "AccountInfo"),
        node("x20l20", "com_Skin", "AccountInfo"),
    )
    return None


def paint_label(canvas, snapshot):
    info = snapshot.get("info") or {}
    label = blank((760, 180))
    background = blank(label.size)
    row = cosmetic("backgrounds", info.get("background"))
    background_node = (
        dict(node("heh5a5", "loader_Video"), fill=4)
        if row and row.get("frame") == 0
        else node("heh5a5", "loader_Image")
    )
    available = loader(background, row, background_node)
    label.alpha_composite(mask(background, "aepoa6"))
    photo = blank((184, 156))
    photo_node = node("z1wk2", "n82")
    put(photo, sprite(photo_node), photo_node)
    if not loader(
        photo,
        cosmetic("headshots", info.get("headIcon")),
        node("z1wk2", "loader_PlayerPhoto"),
    ):
        missing = dict(
            node("mouys8q", "txt_PlayerName"),
            x=20,
            y=30,
            width=130,
            height=80,
            fontSize=60,
            align=1,
            color=[139, 139, 139, 255],
            pivot=None,
        )
        put(photo, text_image("？", missing), missing)
    put(label, mask(photo, "z1wk2"), node("z1wk0", "com_PlayerPhoto"))
    name = info.get("name") or "未提供昵称"
    name_node = node("mouys8q", "txt_PlayerName")
    clean_name = "".join(
        c for c in str(name)[:4096] if not unicodedata.category(c).startswith("C")
    )
    name_width = min(
        480, round(get_font(ASSETS / "SIMHEI.ttf", 28).getlength(clean_name)) + 4
    )
    bar = dict(node("z1wk0", "image_Icon"), width=max(60, min(530, 60 + name_width)))
    put(label, sprite(bar), bar)
    name_layer = blank((480, 40))
    put(name_layer, text_image(name, name_node), name_node)
    put(label, name_layer, node("z1wk0", "com_Name"))
    for key, value in (
        ("n77", "LV."),
        ("txt_lv", info.get("lv") if info.get("lv") is not None else "—"),
    ):
        child = node("z1wk0", key)
        put(label, text_image(value, child, fit=key == "txt_lv"), child)
    border = node("z1wk0", "n85")
    put(label, sprite(border), border)
    put(canvas, mask(label, "z1wk0"), node("x20l20", "com_Label", "AccountInfo"))
    origin = node("x20l20", "btn_UID", "AccountInfo")
    child = dict(node("p5xi2j", "txt_UID", "AccountInfo"))
    child["height"] = min(
        child["fontSize"] + 4,
        node("x20l20", "btn_Achieve_0", "AccountInfo")["y"] - origin["y"] - child["y"],
    )
    child["x"] += origin["x"]
    child["y"] += origin["y"]
    put(canvas, text_image(f"UID:{snapshot.get('uid', '—')}", child, fit=True), child)
    child = dict(node("p5xi2j", "n72", "AccountInfo"))
    child["x"] += origin["x"]
    child["y"] += origin["y"]
    put(canvas, sprite(child, "AccountInfo"), child)
    return None if available else "名片资源未收录"


def paint_achievements(canvas, snapshot):
    selected = (snapshot.get("show") or {}).get("achieveId") or []
    for index in range(6):
        value = selected[index] if index < len(selected) else 0
        image = blank((132, 133))
        if value:
            achievement = blank((132, 132))
            loader(
                achievement,
                cosmetic("achievements", value),
                node("f3tl19", "loader_Achieve", "AccountInfo"),
            )
            put(
                image,
                mask(achievement, "f3tl19", "AccountInfo"),
                node("zhzta", "com_AchieveLoader", "AccountInfo"),
            )
        else:
            for key in ("n19", "n20"):
                child = node("zhzta", key, "AccountInfo")
                put(image, shape(child), child)
            child = node("zhzta", "n21", "AccountInfo")
            put(image, text_image("EMPTY", child), child)
        put(canvas, image, node("x20l20", f"btn_Achieve_{index}", "AccountInfo"))


def paint_tabs(canvas):
    for key in ("btn_Data", "btn_Battle"):
        origin = node("x20l20", key, "AccountInfo")
        layer = blank((origin["width"], origin["height"] - 3))
        selected = key == "btn_Data"
        child = dict(
            node("zhztd", "n8" if selected else "n7", "AccountInfo"), width=layer.width
        )
        put(layer, shape(child), child)
        child = dict(node("zhztd", "title", "AccountInfo"), width=layer.width)
        if selected:
            child["color"] = [0, 0, 0, 255]
        put(layer, text_image(origin["title"], child), child)
        put(canvas, layer, origin)
