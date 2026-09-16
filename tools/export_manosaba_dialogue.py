import argparse
import hashlib
import json
import re
from pathlib import Path

import UnityPy
from PIL import Image


UI_NAMES = {
    "NormalPrinter_Frame_Top", "NormalPrinter_Frame_Bottom",
    "NormalPrinter_Grass_1", "NormalPrinter_Grass_2", "NormalPrinter_Screen",
    "NamePlateBase", "InputIndicator", "MenuButton", "AutoToggle_Off",
}
CATEGORIES = (("mainbackground", "场景"), ("stills", "插图"), ("tricks", "特效"))


def natural_key(value):
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", str(value)))


def export_assets(bundle_root, evidence_path, output):
    output.mkdir(parents=True, exist_ok=True)
    for folder in ("ui", "backgrounds"):
        (output / folder).mkdir(exist_ok=True)
    catalog_path = output / "backgrounds.json"
    old = json.loads(catalog_path.read_text(encoding="utf-8"))["backgrounds"] if catalog_path.exists() else []
    previous = {item["source"]: item["code"] for item in old}
    next_id = max((int(item["code"][3:]) for item in old), default=0) + 1
    records = []
    for folder, category in CATEGORIES:
        directory = bundle_root / "naninovel-backgrounds_assets_naninovel/backgrounds" / folder
        for path in sorted(directory.rglob("*.bundle"), key=lambda item: natural_key(item.relative_to(directory))):
            env = UnityPy.load(str(path))
            for obj in sorted((o for o in env.objects if o.type.name == "Sprite"), key=lambda item: item.path_id):
                sprite = obj.read()
                source = path.relative_to(bundle_root).as_posix() + ":" + sprite.m_Name
                code = previous.get(source)
                if code is None:
                    code = f"@BG{next_id:03d}"
                    next_id += 1
                image = sprite.image.convert("RGBA")
                original_size = image.size
                image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
                relative = f"backgrounds/{code[1:]}.webp"
                image.save(output / relative, "WEBP", quality=95, method=6)
                records.append({"code": code, "category": category, "path": relative,
                                "name": category + " " + path.stem.replace("_", "-"),
                                "source": source, "original_size": original_size,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            if len(records) % 20 == 0:
                print("背景已导出", len(records), flush=True)
    missing = set(previous) - {item["source"] for item in records}
    if missing:
        raise ValueError("旧目录中的背景缺失，停止覆盖目录：" + ", ".join(sorted(missing)))
    for obj in UnityPy.load(str(bundle_root / "general-sprites_assets_all.bundle")).objects:
        if obj.type.name == "Sprite" and obj.peek_name() in UI_NAMES:
            sprite = obj.read()
            image = sprite.image
            size = {"AutoToggle_Off": (253, 169)}.get(sprite.m_Name, image.size)
            image.resize(size, Image.Resampling.LANCZOS).save(output / "ui" / (sprite.m_Name + ".png"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    configuration = evidence["configs"]["CharactersConfiguration"]["data"]["Metadata"]
    metadata = dict(zip(configuration["ids"], configuration["metas"], strict=True))
    scales = {item["Character"]: item["Scale"] for item in evidence["configs"]["CharactersConfigurationExtended"]["data"]["Options"]}
    templates = {}
    for item in evidence["author_data"]["AuthorData"]["data"]["_items"]:
        if item["_id"] not in metadata:
            continue
        template = next((value["_text"] for value in item["_taggedText"] if value["_locale"] == 2), "")
        if template:
            meta = metadata[item["_id"]]
            templates[item["_id"]] = {"template": template,
                "color": [round(meta["NameColor"][key] * 255) for key in "rgba"],
                "pivot": [meta["Pivot"][key] for key in "xy"],
                "scale": scales.get(item["_id"], 1.0)}
    catalog_path.write_text(json.dumps({"version": 1, "backgrounds": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "authors.json").write_text(json.dumps(templates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("资源导出完成", len(records), "个背景，", len(templates), "个姓名模板")


def main():
    parser = argparse.ArgumentParser(description="导出魔裁对话背景、UI 和官方姓名模板")
    parser.add_argument("bundle_root", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "plugins/nonebot_plugin_manosaba_memes/assets/dialogue")
    args = parser.parse_args()
    export_assets(args.bundle_root, args.evidence, args.output)


if __name__ == "__main__":
    main()
