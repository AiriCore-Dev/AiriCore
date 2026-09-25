import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import UnityPy
from PIL import Image

if __package__:
    from .export_assets import fields, load_catalog, package
else:
    from export_assets import fields, load_catalog, package


class AssetSource:
    def __init__(self, game_dir, cache_dir, catalog):
        self.catalog, self.buckets, self.entries, self.names = load_catalog(catalog)
        self.root = next(game_dir.glob("*_Data")) / "StreamingAssets/aa/StandaloneWindows64"
        self.cache = cache_dir

    def read(self, name, address=None):
        entry = self.entries[self.names[address or name][0]]
        for index in self.buckets[entry[2]][1]:
            internal = self.catalog["m_InternalIds"][self.entries[index][0]]
            filename = internal.replace("\\", "/").rsplit("/", 1)[-1]
            path = self.root / filename
            if not path.exists():
                stem = filename.removesuffix(".bundle")
                hits = list(self.cache.glob("*/" + stem.rsplit("_", 1)[-1] + "/__data"))
                hits += list(self.cache.glob("*/" + stem + "/__data"))
                if not hits:
                    continue
                path = hits[0]
            for obj in UnityPy.load(str(path)).objects:
                if obj.type.name in ("Texture2D", "TextAsset"):
                    value = obj.read()
                    if value.m_Name == name:
                        return value, path
        raise FileNotFoundError(f"未找到结算素材：{name}")


def export(args):
    source = AssetSource(args.game_dir, args.cache_dir, args.catalog)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf8")) if manifest_path.exists() else {
        "来源": "本机《吉星派对》安装资源与已下载更新缓存",
        "files": {},
    }

    def save(path, origin, name):
        manifest["files"][path.relative_to(out).as_posix()] = {
            "asset": name,
            "bundle": origin.name if origin.name != "__data" else origin.parent.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def write_json(path, value, origin, name):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf8", newline="\n")
        save(path, origin, name)

    layouts, origins = {}, {}
    for name in ("BattleSettlement", "Common", "Common_Internal", "Background"):
        asset, origin = source.read(name + "_fui")
        with TemporaryDirectory(prefix="astral-settlement-") as directory:
            raw = Path(directory) / "package.bytes"
            raw.write_bytes(asset.m_Script.encode("utf8", "surrogateescape"))
            layouts[name] = package(raw, include_state=True)
        origins[name] = origin

    common = layouts["Common"]
    selected = set()

    def collect(key):
        if key in selected:
            return
        selected.add(key)
        for child in common["items"][key].get("children", []):
            if child.get("source") and child.get("package") in (None, common["id"]):
                collect(child["source"])

    for key in ("imo37v", "mmmw3y", "9wy8bw", "kn6fq3y", "g1i49l", "ozsk8w"):
        collect(key)
    common["items"] = {key: value for key, value in common["items"].items() if key in selected}
    internal = layouts['Common_Internal']
    internal['items'] = {key: value for key, value in internal['items'].items() if key in ('k1ic8b', 'k1ic8b_0')}
    for name, layout in layouts.items():
        atlas_cache = {}
        folder = out / "settlement" / name
        folder.mkdir(parents=True, exist_ok=True)
        for key, item in layout["items"].items():
            sprite = item.get("sprite")
            if not sprite:
                continue
            atlas_id = sprite["atlas"]
            if atlas_id not in atlas_cache:
                atlas_name = name + "_" + atlas_id
                asset, origin = source.read(atlas_name)
                atlas_cache[atlas_id] = asset.image, origin
            atlas, origin = atlas_cache[atlas_id]
            x, y, width, height = sprite["rect"]
            image = atlas.crop((x, y, x + width, y + height))
            if sprite["rotated"]:
                image = image.transpose(Image.Transpose.ROTATE_90)
            target = Image.new("RGBA", tuple(sprite["originalSize"]))
            target.paste(image, tuple(sprite["offset"]))
            path = folder / (key + ".png")
            target.save(path, optimize=True)
            save(path, origin, name + "/" + item["name"])
        write_json(out / "settlement" / (name + ".json"), layout, origins[name], name + "_fui")

    asset, origin = source.read("Skin", "GameData_CN")
    skins = fields(asset.m_Script.encode("utf8", "surrogateescape"))
    heroes, paintings = {}, {}
    folder = out / "settlement" / "characters"
    folder.mkdir(exist_ok=True)
    for raw in skins[1]:
        row = fields(raw)
        hero_id = str(row[1][0])
        choices = [fields(value) for value in row.get(2, [])]
        for choice in choices:
            if not choice.get(17):
                continue
            name = choice[17][0].decode('utf8')
            try:
                asset, asset_origin = source.read(name)
            except FileNotFoundError:
                continue
            path = folder / (name + '.webp')
            asset.image.save(path, lossless=True, method=4)
            save(path, asset_origin, name)
            entry = {'asset': name, 'path': path.relative_to(out).as_posix()}
            if choice.get(3):
                paintings[str(choice[3][0])] = entry
            if choice.get(2, [0])[0]:
                heroes[hero_id] = entry
    write_json(out / "settlement" / "characters.json", heroes, origin, "Skin/CharacterReady")
    write_json(out / 'settlement/paintings.json', paintings, origin, 'Skin/CharacterReady')
    def table(name):
        asset, table_origin = source.read(name, 'GameData_CN')
        return fields(asset.m_Script.encode('utf8', 'surrogateescape')), table_origin

    def localized(name):
        raw, _ = table('STR' + name)
        return {row[1][0]: row.get(2, [b''])[0].decode('utf8') for row in map(fields, raw[1])}

    def picture(name):
        asset, asset_origin = source.read(name)
        target = out / 'settlement/textures' / (name + '.webp')
        target.parent.mkdir(parents=True, exist_ok=True)
        asset.image.save(target, lossless=True, method=4)
        save(target, asset_origin, name)
        return target.relative_to(out).as_posix()

    for name, icon_field in (('Relic', 6), ('Achieve', 3), ('Map', 9)):
        raw, table_origin = table(name)
        entries = {}
        strings = localized(name) if name == 'Map' else {}
        for row in map(fields, raw[1]):
            icon = row.get(icon_field, [b''])[0].decode('utf8')
            if not icon:
                continue
            try:
                path = picture(icon)
            except FileNotFoundError:
                continue
            entries[str(row[1][0])] = {'path': path}
            if name == 'Relic':
                entries[str(row[1][0])].update(quality=row.get(2, [0])[0], weight=row.get(13, [0])[0])
            elif name == 'Achieve':
                entries[str(row[1][0])]['weight'] = row.get(6, [0])[0]
            else:
                entries[str(row[1][0])]['name'] = strings.get(row.get(2, [0])[0], '')
        write_json(out / 'settlement' / (name.lower() + '.json'), entries, table_origin, name)
    raw, table_origin = table('ChoosingTimeLimit')
    strings = localized('ChoosingTimeLimit')
    difficulty = {str(row.get(1, [0])[0]): strings.get(row.get(3, [0])[0], '') for row in map(fields, raw[5])}
    write_json(out / 'settlement/difficulty.json', difficulty, table_origin, 'ChoosingTimeLimit')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf8", newline="\n")
    print(f"已导出结算布局、贴图及 {len(heroes)} 个角色的默认结算立绘")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="离线导出吉星派对原版结算界面素材")
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args())
