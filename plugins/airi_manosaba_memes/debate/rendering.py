import io
import json
import math

from PIL import Image, ImageDraw, ImageFilter

from ..asset_cache import get_metadata, get_render, get_source
from ..dialogue.rendering import ASSETS, FONT, SIZE, _authors, _font, _image, _png, _signature, _sprite_runtime, _tree_signature
from .parser import split_highlights, validate_request


ROOT = ASSETS / "debate"


def _layout():
    path = ROOT / "layout.json"
    return get_metadata(("debate-layout", _signature(path)), lambda: json.loads(get_source(path)))


def _canvas_sprite(sprite, prefab, canvas):
    if canvas is None:
        return sprite
    minimum = [min(position[axis] - prefab._image_sizes[node][axis] * scale[axis] / 2
                   for node, scale, position in prefab._get_layers()) for axis in (0, 1)]
    size = tuple(canvas["size"])
    offset = canvas["offset"]
    origin = (round(size[0] / 2 - sprite.width - minimum[0] + offset[0] * 100),
              round(size[1] / 2 - sprite.height - minimum[1] + offset[1] * 100))
    restored = Image.new("RGBA", size)
    restored.alpha_composite(sprite, origin)
    return restored


def _project_sprite(sprite, pivot, side):
    layout = _layout()
    camera = layout["camera"]
    character = layout["character"]
    angle = math.radians(camera["yaw_degrees"] * (1 if side == "left" else -1))
    cosine, sine = math.cos(angle), math.sin(angle)
    focal = SIZE[1] / 2 / math.tan(math.radians(camera["field_of_view"] / 2))
    unit = character["scale"] / character["pixels_per_unit"]
    distance = camera["distance"]
    depth = character["position"][2] - distance * cosine
    denominator = cosine + sine * SIZE[0] / (2 * focal)
    slope = -sine / focal
    origin_x = distance * sine / unit + sprite.width * pivot[0]
    origin_y = sprite.height * (1 - pivot[1]) - (camera["height"] - character["position"][1]) / unit
    coefficients = (
        (origin_x * slope + depth * cosine / (unit * focal)) / denominator,
        0,
        (origin_x * denominator + depth / unit * (sine - cosine * SIZE[0] / (2 * focal))) / denominator,
        origin_y * slope / denominator,
        depth / (unit * focal * denominator),
        (origin_y * denominator - depth * SIZE[1] / (2 * unit * focal)) / denominator,
        slope / denominator,
        0,
    )
    return sprite.transform(SIZE, Image.Transform.PERSPECTIVE, coefficients, Image.Resampling.BICUBIC)


def _text_layer(text, side):
    lines = [[]]
    for content, highlighted in split_highlights(text):
        parts = content.split("\n")
        for index, part in enumerate(parts):
            if index:
                lines.append([])
            if part:
                lines[-1].append((part, highlighted))
    fonts = {False: _font(96), True: _font(120)}
    metrics = {flag: font.getmetrics() for flag, font in fonts.items()}
    line_metrics = []
    for runs in lines:
        flags = [flag for _, flag in runs] or [False]
        above = max(metrics[flag][0] - (7.2 if flag else 0) for flag in flags)
        below = max(metrics[flag][1] + (7.2 if flag else 0) for flag in flags)
        width = sum(fonts[flag].getlength(content) for content, flag in runs)
        line_metrics.append((width, above, below))
    width = math.ceil(max(width for width, _, _ in line_metrics))
    height = math.ceil(sum(above + below for _, above, below in line_metrics) + 40)
    if width > SIZE[0] or height > SIZE[1]:
        raise ValueError("文字超出审问画面，请缩短文字或调整换行")
    padding = 12
    layer = Image.new("RGBA", (max(1, width) + 2 * padding, height + 2 * padding))
    shadow = Image.new("RGBA", layer.size)
    draw, dark = ImageDraw.Draw(layer), ImageDraw.Draw(shadow)
    y = 20 + padding
    for runs, (_, above, below) in zip(lines, line_metrics):
        baseline = y + above
        x = padding
        for content, highlighted in runs:
            font = fonts[highlighted]
            offset = 7.2 if highlighted else 0
            color = (255, 146, 180, 255) if highlighted else (255, 255, 255, 255)
            dark.text((x + 2, baseline + offset + 3), content, font=font, fill=(0, 0, 0, 128), anchor="ls", stroke_width=3)
            draw.text((x, baseline + offset), content, font=font, fill=color, anchor="ls", stroke_width=2, stroke_fill=(0, 0, 0, 255))
            x += font.getlength(content)
        y += above + below
    combined = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(1.5)), layer)
    angle = 4 if side == "left" else -4
    rotated = combined.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    center_x = SIZE[0] * (.7 if side == "left" else .3)
    left = round(center_x - rotated.width / 2)
    top = round(SIZE[1] / 2 - rotated.height / 2)
    box = rotated.getbbox()
    if box and (left + box[0] < 0 or top + box[1] < 0 or left + box[2] > SIZE[0] or top + box[3] > SIZE[1]):
        raise ValueError("文字超出审问画面，请缩短文字或调整换行")
    return rotated, (left, top)


def render_debate(request):
    validate_request(request)
    text_layer, text_position = _text_layer(request.text, request.side)
    renderer, codec = _sprite_runtime()
    decoded = codec.decode(request.sprite)
    if decoded is None:
        raise ValueError(f"立绘短码无效或校验失败：{request.sprite}")
    character, recipe = decoded
    metadata = _authors().get(character)
    pivot = metadata["pivot"] if metadata else _layout()["pivots"].get(character)
    if pivot is None:
        raise ValueError("该角色缺少审问场景定位数据")
    background = ROOT / f"court_{request.side}.webp"
    descriptor = json.dumps({"kind": "debate", "version": 3, "sprite": request.sprite, "side": request.side,
        "text": request.text, "background": _signature(background), "layout": _signature(ROOT / "layout.json"),
        "font": _signature(FONT), "authors": _signature(ASSETS / "dialogue/authors.json"),
        "presets": _signature(ASSETS / "presets/official_presets.json"),
        "prefabs": _tree_signature(ASSETS / "prefabs")}, ensure_ascii=False, sort_keys=True)

    def render():
        canvas = _image(background)
        with Image.open(io.BytesIO(renderer.render_recipe(character, recipe))) as source:
            sprite = source.convert("RGBA")
        sprite = _canvas_sprite(sprite, renderer.prefab(character), _layout()["canvases"][character])
        canvas.alpha_composite(_project_sprite(sprite, pivot, request.side))
        canvas.alpha_composite(text_layer, text_position)
        return _png(canvas.convert("RGB"))

    return get_render(descriptor, render)
