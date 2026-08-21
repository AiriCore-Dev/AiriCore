from __future__ import annotations

from .composer import compose
from .cache import RenderCache
from .output import message_image


_cache = RenderCache()


def frame(frame_kind: str, user_id: str, activity_day: int, step_key: str, state_version: int, layers: list[dict], title: str = "Airi · 王道征途"):
    key = (str(user_id), activity_day, step_key, state_version, frame_kind)
    payload = _cache.get(key)
    if payload is None:
        payload = compose(frame_kind, layers, {"title": title})
        _cache.put(key, payload)
    return message_image(payload)
