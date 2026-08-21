from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .layouts import layout


_COLORS = {"background": (23, 47, 78, 255), "character": (255, 183, 197, 230), "enemy": (240, 110, 90, 230), "icon": (255, 219, 100, 255)}


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(1, width - 1)] + "…"


def compose(frame_kind: str, layer_records: list[dict[str, Any]], state_view: dict[str, Any] | None = None) -> bytes:
    spec = layout(frame_kind)
    image = Image.new("RGBA", spec["size"], _COLORS["background"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, spec["size"][0] - 20, spec["size"][1] - 20), outline=(116, 197, 255, 255), width=3)
    for record in layer_records:
        kind = record.get("kind", "icon")
        slot_name = record.get("slot", "journal")
        slot = spec["slots"].get(slot_name)
        if slot is None:
            continue
        x, y, width, height = slot
        color = _COLORS.get(kind, _COLORS["icon"])
        draw.rounded_rectangle((x, y, x + width, y + height), radius=18, fill=color, outline=(255, 255, 255, 180), width=2)
        label = _fit(str(record.get("label", record.get("id", "王道征途"))), max(8, width // 18))
        draw.text((x + 18, y + 18), label, fill=(30, 35, 50, 255))
    if state_view:
        draw.text((48, 42), _fit(str(state_view.get("title", "Airi · 王道征途")), 42), fill=(255, 255, 255, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()
