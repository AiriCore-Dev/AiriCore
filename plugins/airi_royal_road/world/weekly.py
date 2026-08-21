from __future__ import annotations

from ..base.models import WorldState
from .votes import close_votes


def close_week(world: WorldState, week_index: int) -> dict:
    key = str(week_index)
    box = world.votes.get(key)
    if box is None:
        raise ValueError("本周票箱不存在")
    summary = close_votes(box)
    world.week_results[key] = summary
    world.map_overlays[f"week_{week_index + 1}"] = summary["winner"]
    if key not in world.completed_events:
        world.completed_events.append(key)
    return summary
