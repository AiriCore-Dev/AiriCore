from .composer import compose
from .output import message_image


def missing_asset_frame(frame_kind: str = "journal"):
    slots = {"cover": "bubble", "route": "map", "combat": "status", "loot": "loot", "partner": "character", "journal": "journal", "weekly": "report", "vote": "report", "final": "memorial"}
    slot = slots.get(frame_kind, "journal")
    payload = compose(frame_kind, [{"kind": "icon", "slot": slot, "id": "fallback_icon", "label": "素材暂缺，规则结果已保存"}], {"title": "Airi · 王道征途"})
    return message_image(payload)
