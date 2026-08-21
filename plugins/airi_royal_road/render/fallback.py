from .composer import compose
from .output import message_image


def missing_asset_frame(frame_kind: str = "journal"):
    payload = compose(frame_kind, [{"kind": "icon", "slot": "journal", "id": "fallback_icon", "label": "素材暂缺，规则结果已保存"}], {"title": "Airi · 王道征途"})
    return message_image(payload)
