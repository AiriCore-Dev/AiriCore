from __future__ import annotations

from datetime import datetime

from nonebot import require

from .base.constants import ACTIVITY_END, ACTIVITY_START, ACTIVITY_TZ, SETTLEMENT_START
from .base.persistence import personal_store, world_store
from .rules.calendar import calendar_context


timing = require("nonebot_plugin_apscheduler").scheduler


async def royal_road_tick(now: datetime | None = None) -> str:
    value = (now or datetime.now(ACTIVITY_TZ)).astimezone(ACTIVITY_TZ)
    context = calendar_context(value)
    if context.can_start:
        await personal_store.flush()
        await world_store.flush()
        return "active"
    if value >= SETTLEMENT_START:
        await personal_store.flush()
        await world_store.flush()
        return "settlement"
    return "inactive"


def register_jobs() -> None:
    timing.add_job(royal_road_tick, "interval", minutes=5, id="airi_royal_road_tick", coalesce=True, misfire_grace_time=3600, replace_existing=True)


register_jobs()
