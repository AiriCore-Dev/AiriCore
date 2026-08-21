from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FRAME_KINDS = {"route", "combat", "loot", "partner", "journal", "vote", "weekly", "final"}
MOODS = {"bright", "tense", "tender", "resolute", "quiet"}
BOND_TAGS = {"trust", "candor", "rapport", "courage", "none"}
CAMERAS = {"wide", "medium", "close", "map", "battle"}


@dataclass(frozen=True)
class SceneScript:
    scene_id: str
    frame_kind: str
    asset_layers: tuple[str, ...]
    camera: str
    character_lines: tuple[tuple[str, str], ...]
    bubble_text: str
    mood_tag: str
    bond_tag: str
    journal_text: str

    def to_dict(self) -> dict[str, Any]:
        return {"scene_id": self.scene_id, "frame_kind": self.frame_kind, "asset_layers": list(self.asset_layers), "camera": self.camera, "character_lines": [list(item) for item in self.character_lines], "bubble_text": self.bubble_text, "mood_tag": self.mood_tag, "bond_tag": self.bond_tag, "journal_text": self.journal_text}


def validate_scene_script(script: Any, allowed_assets: set[str], allowed_characters: set[str], allowed_facts: set[str] | None = None) -> SceneScript:
    if not isinstance(script, dict):
        raise TypeError("剧情脚本必须是对象")
    fields = {"scene_id", "frame_kind", "asset_layers", "camera", "character_lines", "bubble_text", "mood_tag", "bond_tag", "journal_text"}
    if set(script) != fields:
        raise ValueError("剧情脚本字段不匹配")
    if not isinstance(script["scene_id"], str) or not script["scene_id"]:
        raise ValueError("剧情场景 ID 无效")
    if script["frame_kind"] not in FRAME_KINDS or script["camera"] not in CAMERAS or script["mood_tag"] not in MOODS or script["bond_tag"] not in BOND_TAGS:
        raise ValueError("剧情脚本枚举无效")
    layers = script["asset_layers"]
    if not isinstance(layers, list) or len(layers) > 16 or any(item not in allowed_assets for item in layers):
        raise ValueError("剧情脚本素材无效")
    lines = script["character_lines"]
    if not isinstance(lines, list) or len(lines) > 4:
        raise ValueError("剧情对白数量无效")
    parsed_lines = []
    for line in lines:
        if not isinstance(line, list) or len(line) != 2 or line[0] not in allowed_characters or not isinstance(line[1], str) or len(line[1]) > 80:
            raise ValueError("剧情对白无效")
        parsed_lines.append((line[0], line[1]))
    bubble = script["bubble_text"]
    journal = script["journal_text"]
    if not isinstance(bubble, str) or not isinstance(journal, str) or len(bubble) > 120 or len(journal) > 160:
        raise ValueError("剧情文字过长")
    for value in (bubble, journal, *(line[1] for line in parsed_lines)):
        if any(token in value for token in ("奖励", "积分", "执行命令", "忽略规则", "system prompt")):
            raise ValueError("剧情文字包含越权内容")
    return SceneScript(script["scene_id"], script["frame_kind"], tuple(layers), script["camera"], tuple(parsed_lines), bubble, script["mood_tag"], script["bond_tag"], journal)
