from __future__ import annotations

from typing import Any

from utils.llm import call_structured

from .fallbacks import fallback_scene
from .prompts import build_prompt
from .schema import SceneScript, validate_scene_script


async def generate_scene(fact_packet: dict[str, Any], player_quote: str, manifest: dict[str, Any]) -> SceneScript:
    event_id = str(fact_packet.get("event_id", "unknown"))
    frame_kind = str(fact_packet.get("frame_kind", "journal"))
    allowed_assets = {item["id"] if isinstance(item, dict) else item for item in manifest.get("assets", ()) if isinstance(item, (str, dict)) and (not isinstance(item, dict) or isinstance(item.get("id"), str))}
    allowed_characters = set(manifest.get("characters", ()))
    system, user = build_prompt(fact_packet, player_quote)
    try:
        result = await call_structured(system, user)
        if result is not None:
            return validate_scene_script(result, allowed_assets, allowed_characters, set(fact_packet.get("facts", ())))
    except Exception:
        pass
    return fallback_scene(event_id, frame_kind)
