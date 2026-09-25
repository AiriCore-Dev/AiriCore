import json
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw

from utils.cache import get_font, get_image

from .profile_rendering import blank, resize_sprite
from .settlement_rendering import nodes, positioned


ASSETS = Path(__file__).parent / 'assets'
CARDS = json.loads((ASSETS / 'cards.json').read_text('utf8'))
CATALOG = json.loads((ASSETS / 'cards/catalog.json').read_text('utf8'))
LAYOUT = json.loads((ASSETS / 'cards/Common.json').read_text('utf8'))
RESAMPLE = Image.Resampling.LANCZOS


def resolve_text(value):
    def astral(match):
        kind, key, content = match.groups()
        if kind == 'Card':
            content = CARDS.get(key, {}).get('name', content)
        elif kind == 'Buff':
            content = CATALOG['buffs'].get(key, content)
        return '[color=#FFB425]' + content + '[/color]'
    value = re.sub(r'\[Astral=([A-Za-z]+):([^\]]+)\](.*?)\[/Astral\]', astral, value)
    return re.sub(r'\{\w+=([^{}]*)\}', r'\1', value)


def rich_text(value, child):
    value = resolve_text(value)
    base_color = tuple(child.get('color', (255, 255, 255, 255)))
    colors = [base_color]
    glyphs = []
    for token in re.split(r'(\[/?[^\]]+\]|<img\s[^>]+/>)', value):
        if token.startswith('[color='):
            colors.append(ImageColor.getcolor(token[7:-1], 'RGBA'))
        elif token == '[/color]':
            if len(colors) > 1:
                colors.pop()
        elif token.startswith('[') and re.fullmatch(r'\[/?(?:url|b|i|u|size)(?:=[^\]]*)?\]', token):
            continue
        elif token.startswith('<img '):
            attributes = dict(re.findall(r"(\w+)=['\"]([^'\"]+)['\"]", token))
            url = attributes.get('src', '')
            if url.startswith('ui://' + LAYOUT['id']) and url[13:] in LAYOUT['items']:
                icon = get_image(ASSETS / 'cards/Common' / (url[13:] + '.png'))
                glyphs.append((icon.resize((int(attributes.get('width', icon.width)), int(attributes.get('height', icon.height))), RESAMPLE), None))
        else:
            glyphs.extend((char, colors[-1]) for char in token)
    width, height = child['width'], child['height']
    name = (child.get('font') or 'SIMHEI').removesuffix('_TMP')
    size = child['fontSize']
    spacing = child.get('letterSpacing', 0)
    line_spacing = child.get('lineSpacing', 0)
    while True:
        font = get_font(ASSETS / (name + '.ttf'), size)
        lines, line, measured, line_height = [], [], 0, size
        for char, color in glyphs:
            icon = isinstance(char, Image.Image)
            if icon:
                char = char.resize((max(1, round(char.width * size / child['fontSize'])), max(1, round(char.height * size / child['fontSize']))), RESAMPLE)
            advance = (char.width if icon else font.getlength(char)) + spacing
            if char == '\n' or (not child.get('singleLine') and line and measured + advance > width - 4):
                lines.append((line, measured, line_height))
                line, measured, line_height = [], 0, size
                if char == '\n':
                    continue
            line.append((char, color, advance))
            measured += advance
            line_height = max(line_height, char.height if icon else size)
        lines.append((line, measured, line_height))
        total = sum(line_height for _, _, line_height in lines) + max(0, len(lines) - 1) * line_spacing
        fits = total <= height - 4 and all(measure <= width - 4 for _, measure, _ in lines)
        if fits or child.get('autoSize') != 3 or size <= 12:
            break
        size -= 1
    image = blank((width, height))
    draw = ImageDraw.Draw(image)
    y = 2 + max(0, height - 4 - total) * child.get('verticalAlign', 0) / 2
    outline = round(child.get('outline', 0))
    if (child.get('font') or '').endswith('_TMP') and outline:
        outline = 3
    for line, measured, line_height in lines:
        x = 2 + max(0, width - 4 - measured) * child.get('align', 0) / 2
        for char, color, advance in line:
            if isinstance(char, Image.Image):
                image.alpha_composite(char, (round(x), round(y + (line_height - char.height) / 2)))
                x += advance
                continue
            bounds = font.getbbox(char)
            draw.text((round(x), round(y + (line_height - bounds[3] + bounds[1]) / 2 - bounds[1])), char,
                      font=font, fill=color, stroke_width=outline,
                      stroke_fill=tuple(child.get('outlineColor', base_color)))
            x += advance
        y += line_height + line_spacing
    return image


def loader_image(image, child):
    width, height = child['width'], child['height']
    fill = child.get('fill', 0)
    factor = 1
    if fill == 1:
        factor = min(width / image.width, height / image.height)
    elif fill == 2:
        factor = height / image.height
    elif fill == 3:
        factor = width / image.width
    elif fill == 5:
        factor = max(width / image.width, height / image.height)
    if child.get('shrinkOnly'):
        factor = min(1, factor)
    size = (width, height) if fill == 4 else (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    if image.size != size:
        image = image.resize(size, RESAMPLE)
    canvas = blank((width, height))
    canvas.alpha_composite(image, (round((width - image.width) * child.get('align', 0) / 2),
                                   round((height - image.height) * child.get('verticalAlign', 0) / 2)))
    return canvas


def component(key, state, images=None, texts=None, transition=None):
    item = LAYOUT['items'][key]
    children = nodes(key, 'Common', state, transition, {'Common': LAYOUT})
    child_states = {}
    for controller in item.get('controllers', []):
        pages = controller['pages']
        selected = state.get(controller['name'], 0)
        page = pages[selected][0] if 0 <= selected < len(pages) else None
        for action in controller.get('actions', []):
            if action['from'] or (action['to'] and page not in action['to']):
                continue
            target = next((child for child in children if child['id'] == action['target']), None)
            if target is None or target['type'] != 9:
                continue
            target_controllers = LAYOUT['items'][target['source']].get('controllers', [])
            linked = next((row for row in target_controllers if row['name'] == action['controller']), None)
            if linked:
                index = next((i for i, choice in enumerate(linked['pages']) if choice[0] == action['page']), None)
                if index is not None:
                    child_states.setdefault(target['id'], dict(state))[linked['name']] = index
    layers, mask_layer = [], None
    images, texts = images or {}, texts or {}
    for index, child in enumerate(children):
        group = child.get('group', -1)
        if not child['visible'] or (group >= 0 and not children[group]['visible']):
            continue
        name, kind = child['name'], child['type']
        image = None
        if name in images:
            if images[name] is not None:
                image = loader_image(images[name], child)
        elif kind == 0:
            resource = LAYOUT['items'][child['source']]
            image = get_image(ASSETS / 'cards/Common' / (child['source'] + '.png')).copy()
            image = resize_sprite(image, (child.get('width', image.width), child.get('height', image.height)), resource.get('scale9Grid'))
            if child.get('color'):
                image = ImageChops.multiply(image, Image.new('RGBA', image.size, tuple(child['color'])))
            if child.get('flip') in (1, 3):
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if child.get('flip') in (2, 3):
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        elif kind == 9:
            image = component(child['source'], child_states.get(child['id'], state), images, texts)
        elif kind in (6, 7, 8):
            image = rich_text(texts.get(name, child.get('text') or ''), child)
        if image is None:
            continue
        if index == item.get('mask', -1):
            mask_layer = positioned(image, child)
        else:
            layers.append(positioned(image, child))
    width, height = item['width'], item['height']
    left = min([0] + [xy[0] for image, xy in layers])
    top = min([0] + [xy[1] for image, xy in layers])
    right = max([width] + [xy[0] + image.width for image, xy in layers])
    bottom = max([height] + [xy[1] + image.height for image, xy in layers])
    canvas = blank((right - left, bottom - top))
    for image, (x, y) in layers:
        canvas.alpha_composite(image, (x - left, y - top))
    if mask_layer:
        mask = blank(canvas.size)
        image, (x, y) = mask_layer
        mask.alpha_composite(image, (x - left, y - top))
        alpha = mask.getchannel('A')
        if item.get('reversedMask'):
            alpha = ImageChops.invert(alpha)
        canvas.putalpha(ImageChops.multiply(canvas.getchannel('A'), alpha))
    canvas.info.update(origin=(left, top), logical_size=(width, height))
    return canvas


def back_config(player):
    key = CATALOG.get('back_items', {}).get(str(player.get('card_back_item_id')))
    return CATALOG['backs'].get(str(key), CATALOG['backs'][CATALOG.get('default_back', '75001')])


def group_cards(cards, player, map_type):
    from .card_state import card_state
    groups, positions = [], {}
    for card in cards:
        if str(card.get('id')) not in CARDS:
            groups.append([card, 1])
            continue
        current = card_state(card, player, map_type)
        key = (card['id'], card.get('alt_art_id') or 0, current['cost'], current['description'],
               bool(card.get('temporary')), card.get('purify') or 0)
        if key in positions:
            groups[positions[key]][1] += 1
        else:
            positions[key] = len(groups)
            groups.append([card, 1])
    return groups


def render_card(card, player, map_type):
    from .card_state import card_state
    config = CARDS.get(str(card.get('id')))
    back = back_config(player)
    if config is None:
        child = next(row for row in LAYOUT['items']['h334q3o']['children'] if row['name'] == 'loader_CardBack')
        canvas = blank((440, 644))
        image, xy = positioned(loader_image(get_image(ASSETS / back['back']), child), child)
        canvas.alpha_composite(image, xy)
        return canvas
    current = card_state(card, player, map_type)
    alt = CATALOG['alt_arts'].get(str(card['id']), {}).get(str(card.get('alt_art_id')))
    art = get_image(ASSETS / (alt['image'] if alt and alt.get('image') else config['image']))
    frame = get_image(ASSETS / back['frame']).copy()
    if back.get('color'):
        frame = ImageChops.multiply(frame, Image.new('RGBA', frame.size, ImageColor.getcolor(back['color'], 'RGBA')))
    state = {'showFront': 0, 'isVideo': 0, 'frontState': alt['type'] if alt else 0,
             'Cost': current['cost'], 'CardType': config['type'], 'TargetType': config['target']}
    images = {'loader_CardFrame': frame, 'loader_FrontCard': art, 'loader_FullCard': art,
              'loader_CardFront': get_image(ASSETS / alt['front']) if alt and alt.get('front') else None}
    texts = {'txt_Name': config['name'], 'txt_Content': current['description'],
             'txt_CardIndex': config['index'], 'txt_CardIndex_2': config['index'], 'txt_CardTips': config['tips']}
    canvas = component('micc2g', state, images, texts, 'ShowDescState')
    x, y = canvas.info['origin']
    bounds = canvas.getbbox() or (-x, -y, 440 - x, 644 - y)
    left, top = min(0, bounds[0] + x), min(0, bounds[1] + y)
    right, bottom = max(440, bounds[2] + x), max(644, bounds[3] + y)
    result = canvas.crop((left - x, top - y, right - x, bottom - y))
    result.info.update(origin=(left, top), logical_size=(440, 644))
    return result
