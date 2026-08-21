from __future__ import annotations

from datetime import datetime

from nonebot import require

from .base.constants import ACTIVITY_END, ACTIVITY_START, ACTIVITY_TZ, SETTLEMENT_END, SETTLEMENT_START
from .base.locks import world_lock
from .base.persistence import personal_store, world_store
from .base.state import all_personal, get_world
from .content.chapters import WEEKS
from .rules.calendar import calendar_context
from .service import service
from .world.votes import open_vote


timing = require("nonebot_plugin_apscheduler").scheduler


async def royal_road_tick(now: datetime | None = None) -> str:
    value = (now or datetime.now(ACTIVITY_TZ)).astimezone(ACTIVITY_TZ)
    context = calendar_context(value)
    if context.can_start:
        await service._persist()
        return "active"
    if value >= SETTLEMENT_START:
        if SETTLEMENT_START.date() <= value.date() <= SETTLEMENT_END.date():
            await service.freeze()
            for user_id in tuple(all_personal()):
                try:
                    await service.settle(user_id, value)
                except ValueError:
                    pass
        await service._persist()
        return "settlement"
    return "inactive"


async def royal_road_weekly_events(now: datetime | None = None) -> str:
    value = (now or datetime.now(ACTIVITY_TZ)).astimezone(ACTIVITY_TZ)
    context = calendar_context(value)
    if not context.can_start or context.week_index is None:
        return "inactive"
    if context.weekday == 4:
        week = WEEKS[context.week_index]
        async with world_lock(context.week_index):
            if str(context.week_index) not in get_world().votes:
                open_vote(get_world(), context.week_index, week["vote_options"], week["tie_priority"])
                await world_store.save(get_world().to_dict())
        return "vote_open"
    if context.weekday == 6:
        try:
            await service.close_week(context.week_index)
        except ValueError:
            return "vote_missing"
        return "week_closed"
    return "idle"


def register_jobs() -> None:
    timing.add_job(royal_road_tick, "interval", minutes=5, id="airi_royal_road_tick", coalesce=True, misfire_grace_time=3600, replace_existing=True)
    timing.add_job(royal_road_weekly_events, "interval", minutes=5, id="airi_royal_road_weekly_events", coalesce=True, misfire_grace_time=3600, replace_existing=True)


register_jobs()
