import io
import json
import hashlib
import re
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from ..asset_cache import get_metadata, get_render, get_source
from ..prefab import Prefab
from ..sprite_editor.codec import RecipeCodec
from ..sprite_editor.presets import PresetCatalog
from ..sprite_editor.rendering import SpriteRenderer
from .catalog import GRID_COLUMNS, GRID_ROWS, PAGE_SIZE, BackgroundCatalog


ASSETS = Path(__file__).resolve().parent.parent / "assets"
ROOT = ASSETS / "dialogue"
FONT = ASSETS / "fonts/SourceHanSerifSC.otf"
PICKER_FONT = ASSETS / "fonts/SourceHanSansSC-Bold.otf"
SIZE = (2560, 1440)
BODY_WIDTH = 1414
BODY_FONT_SIZE = 48
LINE_HEIGHT = 69
UI_LAYERS = (
    ("NormalPrinter_Frame_Top", (2273, 0)),
    ("NormalPrinter_Frame_Bottom", (0, 643)),
    ("NormalPrinter_Screen", (0, 588)),
    ("NormalPrinter_Grass_1", (2195, 0)),
    ("NormalPrinter_Grass_2", (0, 1011)),
    ("MenuButton", (2302, 2)),
    ("AutoToggle_Off", (4, 1273)),
    ("InputIndicator", (2072, 1301)),
)
CLOSING = frozenset("，。！？、；：）》】」』〕〉…,.!?;:%％")
OPENING = frozenset("（《【「『〔〈(")


def _font(size, path=FONT):
    return ImageFont.truetype(io.BytesIO(get_source(path)), size)


def _image(path):
    with Image.open(io.BytesIO(get_source(path))) as image:
        return image.convert("RGBA")


def _png(image):
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def _signature(path):
    stat = path.stat()
    return str(path), stat.st_mtime_ns, stat.st_size


def _tree_signature(path):
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(repr(_signature(path)).encode())
    else:
        for child in sorted(path.rglob("*")):
            if child.is_file():
                digest.update(repr(_signature(child)).encode())
    return digest.hexdigest()


def _authors():
    path = ROOT / "authors.json"
    return get_metadata(("dialogue-authors", _signature(path)), lambda: json.loads(get_source(path)))


def wrap_body(text):
    if not text.strip():
        raise ValueError("请输入对话正文")
    if len(text) > 1000:
        raise ValueError("正文过长，请缩短后再生成")
    font = _font(BODY_FONT_SIZE)
    lines = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        remaining = paragraph
        while remaining:
            end = 0
            for index in range(1, len(remaining) + 1):
                if font.getlength(remaining[:index]) > BODY_WIDTH:
                    break
                end = index
            if end == 0:
                raise ValueError("正文包含无法放入对话框的字符")
            if end < len(remaining):
                while end > 1 and (remaining[end] in CLOSING or remaining[end - 1] in OPENING):
                    end -= 1
                if remaining[end - 1].isascii() and remaining[end - 1].isalnum() and remaining[end].isascii() and remaining[end].isalnum():
                    space = remaining.rfind(" ", 0, end)
                    if space > 0:
                        end = space + 1
            lines.append(remaining[:end])
            remaining = remaining[end:]
        if not paragraph:
            lines.append("")
    if len(lines) > 3:
        raise ValueError("正文超出对话框的三行空间，请缩短文字或减少换行")
    return lines


def _name_runs(template, color):
    markup = re.sub(r"<(size|voffset|cspace|color)=([^>]+)>", r'<\1 value="\2">', template)
    markup = re.sub(r"<space=([^>]+)>", r'<space value="\1"/>', markup)
    root = ElementTree.fromstring("<root>" + markup.replace("%COLOR%", "character") + "</root>")
    runs = []

    def visit(node, size=48, offset=0, fill=(255, 255, 255, 255), spacing=0):
        if node.tag == "size":
            size = int(node.attrib["value"])
        elif node.tag == "voffset":
            offset = float(node.attrib["value"])
        elif node.tag == "color":
            fill = tuple(color)
        elif node.tag == "cspace":
            spacing = float(node.attrib["value"])
        elif node.tag == "space":
            runs.append((None, float(node.attrib["value"]), 0, fill, 0))
        if node.text:
            runs.append((node.text, size, offset, fill, spacing))
        for child in node:
            visit(child, size, offset, fill, spacing)
            if child.tail:
                runs.append((child.tail, size, offset, fill, spacing))

    visit(root)
    return runs


def _draw_text(canvas, operations):
    foreground = Image.new("RGBA", canvas.size)
    shadow = Image.new("RGBA", canvas.size)
    draw = ImageDraw.Draw(foreground)
    dark = ImageDraw.Draw(shadow)
    for xy, text, font, color in operations:
        dark.text((xy[0] + 2, xy[1] + 3), text, font=font, fill=(0, 0, 0, 220), anchor="ls", stroke_width=1)
        draw.text(xy, text, font=font, fill=color, anchor="ls")
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(1.5)))
    canvas.alpha_composite(foreground)


def _nameplate(canvas, author):
    key = "Unknown" if author == "?" else author
    metadata = _authors().get(key)
    if metadata is None:
        raise ValueError("没有找到该角色的官方姓名牌")
    canvas.alpha_composite(_image(ROOT / "ui/NamePlateBase.png"), (340, 902))
    runs = _name_runs(metadata["template"], metadata["color"])
    max_size = max(int(size) for text, size, _, _, _ in runs if text)
    baseline = 952 + _font(max_size).getmetrics()[0]
    x = 428.0
    operations = []
    fonts = {}
    for text, size, offset, color, spacing in runs:
        if text is None:
            x += size
            continue
        if size not in fonts:
            fonts[size] = _font(size)
        font = fonts[size]
        for character in text:
            operations.append(((x, baseline - offset), character, font, color))
            x += font.getlength(character) + spacing
    _draw_text(canvas, operations)


class _DialogueSpriteRenderer(SpriteRenderer):
    def prefab(self, character):
        path = self.asset_root / character
        return get_metadata(("dialogue-prefab", str(path), _tree_signature(path)),
                            lambda: Prefab(character, asset_path=self.asset_root))


def _sprite_runtime():
    def initialize():
        catalog = PresetCatalog(ASSETS / "presets/official_presets.json", asset_root=ASSETS / "prefabs")
        renderer = _DialogueSpriteRenderer(catalog, asset_root=ASSETS / "prefabs")
        return renderer, RecipeCodec(catalog, renderer.prefab)
    return get_metadata(("dialogue-sprites", _tree_signature(ASSETS / "prefabs"),
                         _signature(ASSETS / "presets/official_presets.json")), initialize)


def _character(canvas, code, x):
    renderer, codec = _sprite_runtime()
    decoded = codec.decode(code)
    if decoded is None:
        raise ValueError(f"立绘短码无效或校验失败：{code}")
    character, recipe = decoded
    meta = _authors().get(character)
    if meta is None:
        raise ValueError("该角色缺少场景定位数据")
    with Image.open(io.BytesIO(renderer.render_recipe(character, recipe))) as rendered:
        sprite = rendered.convert("RGBA")
    scale = meta.get("scale", 1.0)
    if scale != 1:
        sprite = sprite.resize((round(sprite.width * scale), round(sprite.height * scale)), Image.Resampling.LANCZOS)
    pivot_x, pivot_y = meta["pivot"]
    left = round(x - sprite.width * pivot_x)
    top = round(720 - sprite.height * (1 - pivot_y))
    canvas.alpha_composite(sprite, (left, top))


def render_dialogue(request):
    if len(request.sprites) > 3:
        raise ValueError("一张对话图片最多支持三个角色")
    lines = wrap_body(request.text)
    entry = BackgroundCatalog().get(request.background)
    descriptor = json.dumps({"kind": "dialogue", "layout": 2, "background": _signature(entry.path),
        "sprites": request.sprites, "author": request.author, "text": request.text,
        "font": _signature(FONT), "authors": _signature(ROOT / "authors.json"),
        "catalog": _signature(ASSETS / "presets/official_presets.json"),
        "prefabs": _tree_signature(ASSETS / "prefabs"),
        "ui": [_signature(ROOT / "ui" / (name + ".png")) for name, _ in UI_LAYERS] + [_signature(ROOT / "ui/NamePlateBase.png")]}, ensure_ascii=False, sort_keys=True)

    def render():
        canvas = Image.new("RGBA", SIZE, (0, 0, 0, 255))
        canvas.alpha_composite(ImageOps.fit(_image(entry.path), SIZE, Image.Resampling.LANCZOS))
        positions = {0: (), 1: (1280,), 2: (800, 1760), 3: (600, 1280, 1960)}[len(request.sprites)]
        for code, x in zip(request.sprites, positions, strict=True):
            _character(canvas, code, x)
        for name, position in UI_LAYERS:
            canvas.alpha_composite(_image(ROOT / "ui" / (name + ".png")), position)
        auto_font = _font(37)
        _draw_text(canvas, [((155 - auto_font.getlength("Auto") / 2, 1365), "Auto", auto_font, (255, 255, 255, 255))])
        if request.author is not None:
            _nameplate(canvas, request.author)
        font = _font(BODY_FONT_SIZE)
        baseline = 1163 + font.getmetrics()[0]
        _draw_text(canvas, [((573, baseline + index * LINE_HEIGHT), line, font, (255, 255, 255, 255)) for index, line in enumerate(lines)])
        return _png(canvas.convert("RGB"))

    return get_render(descriptor, render)


def render_background(entry):
    return get_render(json.dumps({"kind": "dialogue-background", "source": _signature(entry.path)}), lambda: _png(_image(entry.path)))


def render_background_picker(entries, start):
    if not entries or len(entries) > PAGE_SIZE or start < 0:
        raise ValueError("背景选择表的页码或数量无效")
    descriptor = json.dumps({"kind": "background-picker", "layout": 2, "start": start,
        "grid": (GRID_COLUMNS, GRID_ROWS),
        "entries": [(entry.code, entry.name, _signature(entry.path)) for entry in entries],
        "font": _signature(PICKER_FONT)}, ensure_ascii=False)

    def render():
        canvas = Image.new("RGB", (GRID_COLUMNS * 512, GRID_ROWS * 336), (24, 26, 32))
        draw = ImageDraw.Draw(canvas)
        font = _font(26, PICKER_FONT)
        for index, entry in enumerate(entries):
            x, y = (index % GRID_COLUMNS) * 512, (index // GRID_COLUMNS) * 336
            image = ImageOps.contain(_image(entry.path), (496, 280), Image.Resampling.LANCZOS)
            canvas.paste(image, (x + (512 - image.width) // 2, y + 8 + (280 - image.height) // 2), image)
            draw.text((x + 14, y + 296), f"B{start + index + 1}  {entry.code}", font=font, fill="white")
        return _png(canvas)

    return get_render(descriptor, render)
