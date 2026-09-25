import argparse
import base64
import hashlib
import json
import struct
from pathlib import Path

import UnityPy
from PIL import Image


class Buffer:
    def __init__(self, data, strings=None):
        self.data = data
        self.p = 0
        self.strings = strings or []

    def read(self, fmt):
        v = struct.unpack_from(">" + fmt, self.data, self.p)
        self.p += struct.calcsize(fmt)
        return v[0] if len(v) == 1 else v

    def byte(self):
        return self.read("B")

    def short(self):
        return self.read("H")

    def integer(self):
        return self.read("i")

    def string(self):
        n = self.short()
        s = self.data[self.p : self.p + n].decode("utf8")
        self.p += n
        return s

    def ref(self):
        n = self.short()
        return None if n == 65534 else "" if n == 65533 else self.strings[n]

    def seek(self, start, block):
        old = self.p
        self.p = start
        n = self.byte()
        small = self.byte()
        if block >= n:
            self.p = old
            return False
        self.p += block * (2 if small else 4)
        offset = self.short() if small else self.integer()
        if not offset:
            self.p = old
            return False
        self.p = start + offset
        return True

    def sub(self):
        n = self.integer()
        b = Buffer(self.data[self.p : self.p + n], self.strings)
        self.p += n
        return b


def child(b, start):
    b.seek(start, 0)
    d = {
        "type": b.byte(),
        "source": b.ref(),
        "package": b.ref(),
        "id": b.ref(),
        "name": b.ref(),
        "x": b.integer(),
        "y": b.integer(),
    }
    if b.byte():
        d.update(width=b.integer(), height=b.integer())
    if b.byte():
        b.p += 16
    if b.byte():
        d["scale"] = b.read("ff")
    if b.byte():
        d["skew"] = b.read("ff")
    if b.byte():
        d["pivot"] = [*b.read("ff"), b.byte()]
    d.update(alpha=b.read("f"), rotation=b.read("f"), visible=bool(b.byte()))
    if d["type"] in (6, 7, 8):
        b.seek(start, 5)
        d.update(
            font=b.ref(),
            fontSize=b.short(),
            color=list(b.read("BBBB")),
            align=b.byte(),
            verticalAlign=b.byte(),
        )
        b.seek(start, 6)
        d["text"] = b.ref()
    if d["type"] == 0 and b.seek(start, 5):
        if b.byte():
            d["color"] = list(b.read("BBBB"))
        d["flip"] = b.byte()
    return d


def package(path):
    b = Buffer(path.read_bytes())
    if b.integer() != 1179080009:
        raise ValueError("不支持的 FairyGUI 素材格式")
    version = b.integer()
    if b.byte():
        raise ValueError("不支持压缩的 FairyGUI 素材包")
    pid = b.string()
    name = b.string()
    b.p += 20
    start = b.p
    b.seek(start, 4)
    b.strings = [b.string() for _ in range(b.integer())]
    if b.seek(start, 5):
        for _ in range(b.integer()):
            idx = b.short()
            n = b.integer()
            b.strings[idx] = b.data[b.p : b.p + n].decode("utf8")
            b.p += n
    b.seek(start, 0)
    deps = [{"id": b.ref(), "name": b.ref()} for _ in range(b.short())]
    b.seek(start, 1)
    items = {}
    for _ in range(b.short()):
        size = b.integer()
        end = b.p + size
        d = {
            "type": b.byte(),
            "id": b.ref(),
            "name": b.ref(),
            "path": b.ref(),
            "file": b.ref(),
            "exported": bool(b.byte()),
            "width": b.integer(),
            "height": b.integer(),
        }
        if d["type"] == 0:
            d["scaleOption"] = b.byte()
            if d["scaleOption"] == 1:
                d["scale9Grid"] = list(b.read("iiii"))
                d["tileGridIndice"] = b.integer()
        elif d["type"] == 3:
            d["objectType"] = b.byte()
            raw = b.sub()
            raw.seek(0, 2)
            children = []
            for _ in range(raw.short()):
                n = raw.short()
                p = raw.p
                children.append(child(raw, p))
                raw.p = p + n
            d["children"] = children
        items[d["id"]] = d
        b.p = end
    b.seek(start, 2)
    for _ in range(b.short()):
        n = b.short()
        end = b.p + n
        sid = b.ref()
        atlas = b.ref()
        rect = list(b.read("iiii"))
        rot = bool(b.byte())
        offset = [0, 0]
        original = [rect[3], rect[2]] if rot else rect[2:]
        if version >= 2 and b.byte():
            offset = list(b.read("ii"))
            original = list(b.read("ii"))
        items.setdefault(
            sid, {"id": sid, "name": sid, "width": original[0], "height": original[1]}
        )["sprite"] = {
            "atlas": atlas,
            "rect": rect,
            "rotated": rot,
            "offset": offset,
            "originalSize": original,
        }
        b.p = end
    return {
        "id": pid,
        "name": name,
        "version": version,
        "dependencies": deps,
        "items": items,
        "strings": b.strings,
    }


def varint(data, p):
    v = 0
    s = 0
    while True:
        b = data[p]
        p += 1
        v |= (b & 127) << s
        if b < 128:
            return v, p
        s += 7


def fields(data):
    p = 0
    r = {}
    while p < len(data):
        t, p = varint(data, p)
        f = t >> 3
        w = t & 7
        if w == 0:
            v, p = varint(data, p)
        elif w == 2:
            n, p = varint(data, p)
            v = data[p : p + n]
            p += n
        elif w == 5:
            v = struct.unpack_from("<i", data, p)[0]
            p += 4
        elif w == 1:
            v = struct.unpack_from("<q", data, p)[0]
            p += 8
        else:
            raise ValueError(w)
        r.setdefault(f, []).append(v)
    return r


def load_catalog(path):
    c = json.loads(path.read_text(encoding="utf8"))
    keys, buckets, entry_data = [
        base64.b64decode(c[k])
        for k in ("m_KeyDataString", "m_BucketDataString", "m_EntryDataString")
    ]

    def key(p):
        kind = keys[p]
        n = struct.unpack_from("<i", keys, p + 1)[0]
        if kind in (0, 1):
            return keys[p + 5 : p + 5 + n].decode("utf8" if kind == 0 else "utf-16-le")
        return str(n)

    p = 4
    bs = []
    for _ in range(struct.unpack_from("<i", buckets)[0]):
        offset, n = struct.unpack_from("<ii", buckets, p)
        p += 8
        ids = struct.unpack_from("<" + "i" * n, buckets, p)
        p += 4 * n
        bs.append((key(offset), ids))
    entries = list(struct.iter_unpack("<7i", entry_data[4:]))
    return c, bs, entries, {str(name): ids for name, ids in bs}


def export(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    c, bs, entries, names = load_catalog(args.catalog)
    data = next(args.game_dir.glob("*_Data"))
    bundle_root = data / "StreamingAssets" / "aa" / "StandaloneWindows64"
    sources = {}
    packages = {}
    tables = {}

    def locate(entry):
        internal = c["m_InternalIds"][entry[0]].replace("\\", "/")
        filename = internal.rsplit("/", 1)[-1]
        path = bundle_root / filename
        if path.exists():
            return path
        stem = filename.removesuffix(".bundle")
        digest = stem.rsplit("_", 1)[-1]
        candidates = list(args.cache_dir.glob("*/" + digest + "/__data")) + list(
            args.cache_dir.glob("*/" + stem + "/__data")
        )
        if candidates:
            return candidates[0]
        raise FileNotFoundError("缺少游戏资源包：" + filename)

    def source(name):
        entry = entries[names[name][0]]
        return [locate(entries[i]) for i in bs[entry[2]][1]]

    def save(path, origin, asset):
        sources[str(path.relative_to(out)).replace("\\", "/")] = {
            "asset": asset,
            "bundle": origin.name if origin.name != "__data" else origin.parent.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def read_asset(name):
        for path in source(name):
            env = UnityPy.load(str(path))
            for obj in env.objects:
                if obj.type.name not in ("Texture2D", "TextAsset"):
                    continue
                value = obj.read()
                if value.m_Name == name:
                    return value, path
        raise ValueError("资源包中未找到：" + name)

    for name in ("AccountInfo", "Common", "Background"):
        value, origin = read_asset(name + "_fui")
        raw = out / (name + "_fui.bytes")
        raw.write_bytes(value.m_Script.encode("utf8", "surrogateescape"))
        layout = package(raw)
        raw.unlink()
        packages[name] = layout
        path = out / (name + "_layout.json")
        path.write_text(
            json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf8", newline="\n"
        )
        save(path, origin, name + "_fui")
    for name in ("AccountInfo", "Common"):
        value, origin = read_asset(name + "_atlas0")
        atlas = value.image
        ids = (
            [i for i, d in packages[name]["items"].items() if "sprite" in d]
            if name == "AccountInfo"
            else ["kn6fq3y", "z1wk4", "ru20q2t", "mmmw3x"]
        )
        folder = out / "ui" / name
        folder.mkdir(parents=True, exist_ok=True)
        for item_id in ids:
            d = packages[name]["items"][item_id]
            s = d["sprite"]
            x, y, w, h = s["rect"]
            im = atlas.crop((x, y, x + w, y + h))
            if s["rotated"]:
                im = im.transpose(Image.Transpose.ROTATE_90)
            target = Image.new("RGBA", tuple(s["originalSize"]))
            target.paste(im, tuple(s["offset"]))
            path = folder / (item_id + ".png")
            target.save(path, optimize=True)
            save(path, origin, name + "/" + d["name"])
    for obj in UnityPy.load(str(data / "data.unity3d")).objects:
        if obj.type.name != "Font":
            continue
        value = obj.read()
        if value.m_Name not in ("JingNanBoBoHei", "Impact", "SHOWG"):
            continue
        path = out / (value.m_Name + ".ttf")
        path.write_bytes(bytes(value.m_FontData))
        save(path, data / "data.unity3d", value.m_Name)
    for origin in source("GameData_CN"):
        for obj in UnityPy.load(str(origin)).objects:
            if obj.type.name != "TextAsset":
                continue
            value = obj.read()
            if value.m_Name in (
                "Character",
                "STRCharacter",
                "Map",
                "STRMap",
                "GameMode",
                "STRGameMode",
            ):
                tables[value.m_Name] = [
                    fields(x)
                    for x in fields(value.m_Script.encode("utf8", "surrogateescape"))[1]
                ]
    names_out = {}
    for table, key, field in [
        ("Character", "heroes", 4),
        ("Map", "maps", 2),
        ("GameMode", "modes", 2),
    ]:
        translations = {
            x[1][0]: x.get(2, [b""])[0].decode("utf8") for x in tables["STR" + table]
        }
        names_out[key] = {
            str(x[1][0]): translations.get(x.get(field, [0])[0], str(x[1][0]))
            for x in tables[table]
        }
    path = out / "names.json"
    path.write_text(
        json.dumps(names_out, ensure_ascii=False, indent=2), encoding="utf8", newline="\n"
    )
    save(path, source("GameData_CN")[0], "GameData_CN")
    selections = [
        "UT_Hero_ProfilePhoto_" + i
        for i in names_out["heroes"]
        if "UT_Hero_ProfilePhoto_" + i in names
    ]
    selections += ["UT_AccountBackground_101_01", "UT_Hero_Card_101"]
    for name in selections:
        value, origin = read_asset(name)
        folder = out / ("portraits" if "ProfilePhoto" in name else "art")
        folder.mkdir(exist_ok=True)
        path = folder / (name + ".png")
        value.image.save(path, optimize=True)
        save(path, origin, name)
    manifest = {
        "来源": "本机《吉星派对》安装资源与已下载更新缓存",
        "说明": "资源版权归游戏权利人；该清单仅记录本机离线导出来源。界面坐标为1920×1080设计坐标，组件控制器状态由调用方选择。",
        "files": sources,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8", newline="\n"
    )
    print("已导出", len(sources), "项素材至", out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="离线导出吉星派对账号界面素材")
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args())
