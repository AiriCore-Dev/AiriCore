from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base.constants import ACTIVITY_TZ
from .base.locks import event_id, user_lock, world_lock
from .base.models import PersonalState
from .base.state import get_personal, get_world, set_personal
from .render.frames import frame
from .rules.calendar import calendar_context
from .rules.combat import resolve_turn, start_battle
from .rules.map import visible_routes
from .rules.progression import start_week
from .rules.rewards import grant_reward


@dataclass(frozen=True)
class ServiceResponse:
    frame_key: str
    image: object
    fallback_text: str
    duplicate: bool = False


class AdventureService:
    def _now(self, now: datetime | None = None):
        value = now or datetime.now(ACTIVITY_TZ)
        return calendar_context(value)

    async def start_or_resume(self, user_id: str, now: datetime | None = None) -> ServiceResponse:
        user_id = str(user_id)
        context = self._now(now)
        async with user_lock(user_id):
            personal = get_personal(user_id) or set_personal(PersonalState(user_id=user_id))
            if not context.can_start:
                payload = frame("journal", user_id, context.activity_day or 0, "outside", personal.weekly.week_index, [{"kind": "icon", "slot": "journal", "label": "活动当前不可行动"}])
                return ServiceResponse("outside", payload, "活动当前不可行动")
            start_week(personal, context.week_index or 0)
            date_key = context.current_date.isoformat()
            marker = event_id("daily", user_id, date_key, "action")
            duplicate = date_key in personal.weekly.action_dates
            if not duplicate:
                personal.weekly.action_dates.append(date_key)
                grant_reward(personal, marker, 300, source="daily")
            routes = visible_routes(personal, get_world(), context)
            key = f"{date_key}:route"
            payload = frame("route", user_id, context.activity_day or 0, "route", personal.weekly.week_index, [{"kind": "icon", "slot": "map", "label": f"可选地点 {len(routes)} 个"}], title=f"Airi · 第{context.activity_day}日")
            return ServiceResponse(key, payload, "请选择今日路线", duplicate)

    async def choose(self, user_id: str, choice: int, now: datetime | None = None) -> ServiceResponse:
        if not isinstance(choice, int) or choice < 1 or choice > 3:
            raise ValueError("征途选项无效")
        context = self._now(now)
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            key = f"{context.current_date.isoformat()}:choice:{choice}"
            payload = frame("loot", str(user_id), context.activity_day or 0, f"choice-{choice}", personal.weekly.week_index, [{"kind": "icon", "slot": "loot", "label": f"已确认第 {choice} 项"}])
            return ServiceResponse(key, payload, "规则结果已保存")

    async def combat_action(self, user_id: str, action: str) -> ServiceResponse:
        if action not in {"attack", "skill", "defend", "item", "companion"}:
            raise ValueError("战斗行动无效")
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            if personal.combat is None:
                personal.combat = start_battle(personal, "ordinary_001", f"combat:{personal.weekly.week_index}")
            personal.combat = resolve_turn(personal.combat, action, job=personal.job)
            payload = frame("combat", str(user_id), personal.weekly.week_index, "combat", personal.weekly.week_index, [{"kind": "enemy", "slot": "enemy", "label": personal.combat.result.get("status", "战斗中")}])
            return ServiceResponse(f"combat:{personal.combat.turn}", payload, "战斗结果已保存")

    async def partner_talk(self, user_id: str, quote: str) -> ServiceResponse:
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            payload = frame("partner", str(user_id), personal.weekly.week_index, "partner", personal.weekly.week_index, [{"kind": "character", "slot": "character", "label": "同行伙伴"}, {"kind": "icon", "slot": "bubble", "label": str(quote)[:40]}])
            return ServiceResponse(f"partner:{personal.weekly.week_index}", payload, "伙伴回应已记录")

    async def map_view(self, user_id: str, now: datetime | None = None) -> ServiceResponse:
        context = self._now(now)
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            routes = visible_routes(personal, get_world(), context)
            payload = frame("route", str(user_id), context.activity_day or 0, "map", personal.weekly.week_index, [{"kind": "icon", "slot": "map", "label": f"开放地点 {len(routes)} 个"}])
            return ServiceResponse("map", payload, "地图已更新")

    async def status_view(self, user_id: str) -> ServiceResponse:
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            payload = frame("journal", str(user_id), 0, "status", personal.weekly.week_index, [{"kind": "icon", "slot": "journal", "label": f"徽记 {personal.current_emblems} · 火种 {personal.weekly.fire}"}])
            return ServiceResponse("status", payload, "状态已更新")

    async def archive_view(self, user_id: str) -> ServiceResponse:
        return await self.status_view(user_id)

    async def help_view(self, user_id: str) -> ServiceResponse:
        return await self.status_view(user_id)


service = AdventureService()
