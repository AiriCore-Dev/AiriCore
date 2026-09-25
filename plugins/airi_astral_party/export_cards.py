import argparse
import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

try:
    from .export_assets import fields, package
    from .export_settlement_assets import AssetSource
except ImportError:
    from export_assets import fields, package
    from export_settlement_assets import AssetSource


def packed(values):
    result = []
    for value in values:
        if isinstance(value, int):
            result.append((value >> 1) ^ -(value & 1))
            continue
        number = shift = 0
        for byte in value:
            number |= (byte & 127) << shift
            if byte & 128:
                shift += 7
            else:
                result.append((number >> 1) ^ -(number & 1))
                number = shift = 0
    return result


def export(args):
    source = AssetSource(args.game_dir, args.cache_dir, args.catalog)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    manifest = {'sources': [], 'files': {}, 'limitations': ['静态图不复现视频异画、材质着色器和临时牌动画']}

    def save(path, origin, name):
        manifest['files'][path.relative_to(out).as_posix()] = {
            'asset': name,
            'bundle': origin.name if origin.name != '__data' else origin.parent.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def write(path, value, origin, name):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf8')
        save(path, origin, name)

    def table(name):
        asset, origin = source.read(name, 'GameData_CN')
        raw = asset.m_Script.encode('utf8', 'surrogateescape')
        manifest['sources'].append({'asset': name, 'sha256': hashlib.sha256(raw).hexdigest()})
        return fields(raw), origin

    def localized(name):
        raw, _ = table('STR' + name)
        return {row[1][0]: row.get(2, [b''])[0].decode('utf8') for row in map(fields, raw[1])}

    textures = {}

    def picture(name):
        if not name:
            return None
        if name not in textures:
            asset, origin = source.read(name)
            path = out / 'cards/textures' / (name + '.webp')
            path.parent.mkdir(parents=True, exist_ok=True)
            asset.image.save(path, lossless=True, method=4)
            save(path, origin, name)
            textures[name] = path.relative_to(out).as_posix()
        return textures[name]

    def string(row, key):
        return row.get(key, [b''])[0].decode('utf8')

    raw, origin = table('Card')
    strings = localized('Card')
    cards = {}
    for row in map(fields, raw[1]):
        cards[str(row[1][0])] = {
            'name': strings.get(row.get(2, [0])[0], ''),
            'index': strings.get(row.get(3, [0])[0], ''),
            'description': strings.get(row.get(4, [0])[0], ''),
            'tips': strings.get(row.get(5, [0])[0], ''),
            'image': picture(string(row, 6)),
            'type': row.get(9, [0])[0], 'target': row.get(10, [0])[0],
            'cost': row.get(19, [0])[0], 'params': packed(row.get(20, [])),
        }
    write(out / 'cards.json', cards, origin, 'Card/STRCard')
    alt_arts = {}
    for row in map(fields, raw.get(7, [])):
        variants = {}
        for item in map(fields, row.get(2, [])):
            variants[str(item[2][0])] = {
                'type': item.get(1, [0])[0], 'image': picture(string(item, 3)),
                'video': string(item, 5), 'front': picture(string(item, 7)),
                'material': string(item, 8),
            }
        alt_arts[str(row[1][0])] = variants
    fashion, origin = table('Fashion')
    backs = {}
    for row in map(fields, fashion.get(7, [])):
        backs[str(row[1][0])] = {'frame': picture(string(row, 2)), 'color': string(row, 3),
                                'back': picture(string(row, 6)), 'material': string(row, 5)}
    buffs, _ = table('Buff')
    strings = localized('Buff')
    buffs = {str(row[1][0]): strings.get(row.get(14, [0])[0], '') for row in map(fields, buffs[1])}
    items, _ = table('Item')
    back_items = {str(row[1][0]): row[3][0] for row in map(fields, items[1])
                  if str(row.get(3, [0])[0]) in backs}
    skills, _ = table('Skill')
    skills = {str(row[1][0]): packed(row.get(7, [])) for row in map(fields, skills[1])}
    skins, skin_origin = table('Skin')
    portraits = {}
    for row in map(fields, skins[1]):
        default = next((item for item in map(fields, row.get(2, [])) if item.get(2, [0])[0]), None)
        if default and string(default, 14):
            portraits[str(row[1][0])] = picture(string(default, 14))
    write(out / 'cards/portraits.json', portraits, skin_origin, 'Skin/ProfilePhoto')
    write(out / 'cards/catalog.json', {'backs': backs, 'back_items': back_items, 'default_back': next(iter(backs)),
                                     'alt_arts': alt_arts, 'buffs': buffs, 'skills': skills}, origin, 'Fashion/Card/Buff/Item/Skill')
    asset, origin = source.read('Common_fui')
    with TemporaryDirectory(prefix='astral-cards-') as directory:
        path = Path(directory) / 'Common.bytes'
        path.write_bytes(asset.m_Script.encode('utf8', 'surrogateescape'))
        layout = package(path, include_state=True)
    selected = set()

    def collect(key):
        if key in selected:
            return
        selected.add(key)
        item = layout['items'][key]
        for child in item.get('children', []):
            if child.get('source') and child.get('package') in (None, layout['id']):
                collect(child['source'])
            url = child.get('url') or ''
            if url.startswith('ui://' + layout['id']):
                collect(url[13:])

    collect('micc2g')
    for card in cards.values():
        for url in re.findall(r"<img\s+src=['\"]([^'\"]+)['\"]", card['description']):
            if url.startswith('ui://' + layout['id']):
                collect(url[13:])
    layout['items'] = {key: value for key, value in layout['items'].items() if key in selected}
    atlas_cache = {}
    folder = out / 'cards/Common'
    folder.mkdir(parents=True, exist_ok=True)
    for key, item in layout['items'].items():
        sprite = item.get('sprite')
        if not sprite:
            continue
        atlas_id = sprite['atlas']
        if atlas_id not in atlas_cache:
            atlas_asset, atlas_origin = source.read('Common_' + atlas_id)
            atlas_cache[atlas_id] = atlas_asset.image, atlas_origin
        atlas, atlas_origin = atlas_cache[atlas_id]
        x, y, width, height = sprite['rect']
        image = atlas.crop((x, y, x + width, y + height))
        if sprite['rotated']:
            image = image.transpose(Image.Transpose.ROTATE_90)
        target = Image.new('RGBA', tuple(sprite['originalSize']))
        target.paste(image, tuple(sprite['offset']))
        path = folder / (key + '.png')
        target.save(path, optimize=True)
        save(path, atlas_origin, 'Common/' + item['name'])
    write(out / 'cards/Common.json', layout, origin, 'Common_fui')
    manifest.update(count=len(cards), sha256=hashlib.sha256((out / 'cards.json').read_bytes()).hexdigest())
    (out / 'cards_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', 'utf8')
    print(f'已导出 {len(cards)} 张卡牌、{len(textures)} 张原始贴图和原生卡牌布局')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='离线导出吉星派对原版卡牌素材与布局')
    parser.add_argument('--game-dir', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    export(parser.parse_args())
