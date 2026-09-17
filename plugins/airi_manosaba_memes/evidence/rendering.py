import hashlib
import io
import json
import re

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from ..asset_cache import get_render, get_source
from ..dialogue.rendering import ASSETS, CLOSING, OPENING, PICKER_FONT, _font, _image, _png, _signature
from .catalog import PAGE_SIZE, ItemCatalog


ROOT = ASSETS / 'evidence'
FONT = ASSETS / 'fonts/SourceHanSerifSC.otf'
SIZE = (2560, 1440)
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
BODY_WIDTH = 758
BODY_LINES = 12
LINE_HEIGHT = 54.932
UI_LAYERS = (
    ('Background_1', (0, 0)),
    ('EvidenceFrame', (223, 92)),
    ('EvidenceNameBase', (1338, 97)),
    ('BookTitle@ZhHans', (0, 0)),
)


def decode_upload(payload: bytes) -> Image.Image:
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError('物品图片不能为空或超过 10 MB')
    try:
        with Image.open(io.BytesIO(payload)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError('物品图片不能超过 2000 万像素')
            return ImageOps.exif_transpose(image).convert('RGBA')
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError('无法读取物品图片，请发送有效的图片') from error


def wrap_description(text: str, font_size: int = 36, max_lines: int = BODY_LINES) -> list[str]:
    if not text.strip() or len(text) > 1000:
        raise ValueError('证物描述须为 1～1000 字，且能够放入说明区域')
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    font = _font(font_size)
    lines = []
    for paragraph in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        remaining = paragraph
        if not remaining:
            lines.append('')
        while remaining:
            end = 0
            for index in range(1, len(remaining) + 1):
                if font.getlength(remaining[:index]) > BODY_WIDTH:
                    break
                end = index
            if not end:
                raise ValueError('证物描述包含无法放入说明区域的字符')
            if end < len(remaining):
                while end > 1 and (remaining[end] in CLOSING or remaining[end - 1] in OPENING):
                    end -= 1
                if remaining[end - 1].isascii() and remaining[end - 1].isalnum() and remaining[end].isascii() and remaining[end].isalnum():
                    space = remaining.rfind(' ', 0, end)
                    if space > 0:
                        end = space + 1
            lines.append(remaining[:end])
            remaining = remaining[end:]
        if len(lines) > max_lines:
            raise ValueError('证物描述超出十二行空间，请缩短文字或减少换行')
    return lines


def description_layout(text: str, original: bool = False) -> tuple[list[str], int, float]:
    if not original:
        return wrap_description(text), 36, LINE_HEIGHT
    for font_size in range(36, 17, -1):
        lines = wrap_description(text, font_size, max_lines=1000)
        line_height = LINE_HEIGHT * font_size / 36
        if len(lines) * line_height <= BODY_LINES * LINE_HEIGHT:
            return lines, font_size, line_height
    raise ValueError('原版证物描述超出说明区域，请使用 *名称 描述 自定义证物')


def render_evidence(request, uploaded_image: bytes | None = None) -> bytes:
    if bool(request.item) == (uploaded_image is not None):
        raise ValueError('请指定且只指定一个物品短码或图片')
    entry = ItemCatalog().get(request.item) if request.item else None
    name, description = request.name, request.description
    original = name is None and description is None and entry is not None
    if original:
        if entry.description is None:
            raise ValueError('这个物品没有原版证物文案，请使用 *名称 描述 自定义证物')
        name, description = entry.name, entry.description
    initial_font, name_font = _font(90), _font(60)
    if not name or not name.strip() or '\n' in name or '\r' in name or len(name) > 80 or initial_font.getlength(name[0]) + name_font.getlength(name[1:]) > 812:
        raise ValueError('证物名称超出名称栏，请缩短名称并去掉换行')
    lines, font_size, line_height = description_layout(description or '', original)
    if uploaded_image is None:
        source = get_source(entry.path)
        item_image = _image(entry.path)
    else:
        source = uploaded_image
        item_image = decode_upload(source)
    descriptor = json.dumps({'kind': 'evidence', 'layout': 2, 'source': hashlib.sha256(source).hexdigest(),
        'name': name, 'description': description, 'font_size': font_size, 'font': _signature(FONT),
        'ui': [_signature(ROOT / 'ui' / f'{name}.png') for name, _ in UI_LAYERS]}, ensure_ascii=False)

    def render():
        canvas = Image.new('RGBA', SIZE, (0, 0, 0, 255))
        for layer, position in UI_LAYERS:
            canvas.alpha_composite(_image(ROOT / 'ui' / f'{layer}.png'), position)
        thumbnail = ImageOps.contain(item_image, (500, 500), Image.Resampling.LANCZOS)
        canvas.alpha_composite(thumbnail, (376 + (500 - thumbnail.width) // 2, 250 + (500 - thumbnail.height) // 2))
        draw = ImageDraw.Draw(canvas)
        draw.text((1388, 228), name[0], font=initial_font, fill=(40, 34, 32), anchor='ls')
        draw.text((1388 + initial_font.getlength(name[0]), 228), name[1:], font=name_font, fill=(40, 34, 32), anchor='ls')
        body_font = _font(font_size)
        for index, line in enumerate(lines):
            draw.text((1365, 357.436 + index * line_height), line, font=body_font, fill=(48, 36, 35), anchor='ls')
        return _png(canvas.convert('RGB'))

    return get_render(descriptor, render)


def render_item(entry) -> bytes:
    return get_render(json.dumps({'kind': 'evidence-item', 'source': _signature(entry.path)}), lambda: _png(_image(entry.path)))


def render_item_picker(entries, start: int) -> bytes:
    if not entries or len(entries) > PAGE_SIZE or start < 0:
        raise ValueError('物品选择表的页码或数量无效')
    descriptor = json.dumps({'kind': 'item-picker', 'layout': 1, 'start': start,
        'entries': [(entry.code, entry.name, _signature(entry.path)) for entry in entries],
        'font': _signature(PICKER_FONT)}, ensure_ascii=False)

    def render():
        canvas = Image.new('RGB', (2000, 1800), (24, 26, 32))
        draw = ImageDraw.Draw(canvas)
        font = _font(24, PICKER_FONT)
        for index, entry in enumerate(entries):
            x, y = index % 5 * 400, index // 5 * 360
            thumbnail = ImageOps.contain(_image(entry.path), (270, 270), Image.Resampling.LANCZOS)
            canvas.paste(thumbnail, (x + (400 - thumbnail.width) // 2, y + 8 + (270 - thumbnail.height) // 2), thumbnail)
            draw.text((x + 16, y + 285), f'W{start + index + 1}  {entry.code}', font=font, fill='white')
            name = entry.name
            while font.getlength(name) > 350:
                name = name[:-2] + '…'
            draw.text((x + 16, y + 320), name, font=font, fill=(205, 205, 205))
        return _png(canvas)

    return get_render(descriptor, render)
