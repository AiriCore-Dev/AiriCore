from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base.constants import ACTIVITY_TZ
from .base.locks import event_id, settlement_lock, user_lock, world_lock
from .base.models import PersonalState
from .base.persistence import personal_store, world_store
from .base.state import all_personal, get_personal, get_world, set_personal
from .content.chapters import WEEKS
from .content.characters import JOBS, MEMBERS
from .render.frames import frame
from .rules.calendar import calendar_context
from .rules.combat import ACTIONS, resolve_turn, start_battle
from .rules.map import enter_location, visible_routes
from .rules.progression import apply_bond_delta, camp_support, lose_fire, start_week
from .rules.rewards import grant_reward
from .world.votes import cast_vote, mark_eligible, open_vote
from .world.weekly import close_week


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

    async def _persist(self) -> None:
        await personal_store.save({key: value.to_dict() for key, value in all_personal().items()})
        await world_store.save(get_world().to_dict())

    def _response(self, personal: PersonalState, context, frame_kind: str, step_key: str, label: str, fallback_text: str) -> ServiceResponse:
        personal.last_render_key = step_key
        slot = {"route": "map", "combat": "status", "loot": "loot", "partner": "bubble", "journal": "journal", "vote": "report", "weekly": "report", "final": "memorial"}.get(frame_kind, "journal")
        payload = frame(frame_kind, personal.user_id, context.activity_day or 0, step_key, len(personal.event_ids), [{"kind": "icon", "slot": slot, "label": label}], title=f"Airi · 第{context.activity_day or 0}日")
        return ServiceResponse(step_key, payload, fallback_text)

    def _week(self, context):
        if context.week_index is None:
            raise ValueError("活动当前不可行动")
        return WEEKS[context.week_index]

    async def start_or_resume(self, user_id: str, now: datetime | None = None) -> ServiceResponse:
        user_id = str(user_id)
        context = self._now(now)
        async with user_lock(user_id):
            personal = get_personal(user_id) or set_personal(PersonalState(user_id=user_id))
            if not context.can_start:
                return self._response(personal, context, "journal", "outside", "活动当前不可行动", "活动当前不可行动")
            start_week(personal, context.week_index or 0)
            date_key = context.current_date.isoformat()
            duplicate = date_key in personal.weekly.action_dates
            if personal.job is None:
                personal.pending_choice = f"{date_key}:job"
                response = self._response(personal, context, "journal", personal.pending_choice, "选择职业：1 先锋 2 游侠 3 术士 4 诗旅者", "回复 征途 1 至 4 选择职业")
            elif duplicate:
                response = self._response(personal, context, "journal", f"{date_key}:complete", "今日远征已记录，可查看地图、状态或和伙伴交谈", "今日远征已完成")
            elif personal.weekly.fire == 0:
                personal.pending_choice = f"{date_key}:camp"
                response = self._response(personal, context, "journal", personal.pending_choice, "希望火种归零：1 执行营地支援", "回复 征途 1 执行营地支援")
            elif personal.pending_choice and personal.pending_choice.startswith(f"{date_key}:"):
                response = self._response(personal, context, "route" if ":route" in personal.pending_choice else "loot", personal.pending_choice, "今日远征可继续", "回复征途选项继续")
            else:
                routes = visible_routes(personal, get_world(), context)
                if not routes:
                    personal.pending_choice = f"{date_key}:camp"
                    response = self._response(personal, context, "journal", personal.pending_choice, "道路暂未开放：1 返回希望号支援", "回复 征途 1 执行营地支援")
                else:
                    personal.pending_choice = f"{date_key}:route"
                    labels = "；".join(f"{index + 1} {route.location_id} 风险{route.risk}" for index, route in enumerate(routes[:3]))
                    response = self._response(personal, context, "route", personal.pending_choice, labels, "回复 征途 1 至 3 选择路线")
            await self._persist()
            return ServiceResponse(response.frame_key, response.image, response.fallback_text, duplicate)

    async def choose(self, user_id: str, choice: int, now: datetime | None = None) -> ServiceResponse:
        if not isinstance(choice, int) or choice < 1 or choice > 5:
            raise ValueError("征途选项无效")
        context = self._now(now)
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            if not context.can_start or not personal.pending_choice:
                raise ValueError("当前没有可确认的征途选项")
            date_key = context.current_date.isoformat()
            pending = personal.pending_choice
            if not pending.startswith(f"{date_key}:"):
                raise ValueError("征途选项已过期")
            phase = pending.split(":", 1)[1]
            if phase == "job":
                jobs = tuple(JOBS)
                if choice > len(jobs):
                    raise ValueError("职业选项无效")
                personal.job = jobs[choice - 1]
                personal.pending_choice = None
                response = self._response(personal, context, "journal", f"{date_key}:job:{choice}", f"已成为{personal.job}，请再次发送王道征途选择路线", "职业已确定")
            elif phase == "route":
                routes = visible_routes(personal, get_world(), context)
                if choice > len(routes[:3]):
                    raise ValueError("路线选项无效")
                encounter = enter_location(personal, get_world(), context, routes[choice - 1].location_id)
                personal.weekly.location_id = encounter.location_id
                personal.pending_choice = f"{date_key}:encounter:{encounter.encounter_id}"
                response = self._response(personal, context, "loot", personal.pending_choice, "抵达地点：1 探索 2 谨慎前进 3 返回希望号", "回复征途选项处理遭遇")
            elif phase.startswith("encounter"):
                if choice > 3:
                    raise ValueError("遭遇选项无效")
                personal.weekly.action_dates.append(date_key)
                grant_reward(personal, event_id("daily", personal.user_id, date_key, "action"), 300, source="daily")
                if choice == 1:
                    grant_reward(personal, event_id("location", personal.user_id, date_key, personal.weekly.location_id), 150, source="location")
                    personal.pending_choice = f"{date_key}:loot"
                    response = self._response(personal, context, "loot", personal.pending_choice, "探索成功：1 收下补给 2 换成祝福", "回复征途选项领取战利品")
                elif choice == 2:
                    personal.combat = start_battle(personal, "ordinary_001", pending)
                    personal.pending_choice = f"{date_key}:combat"
                    response = self._response(personal, context, "combat", personal.pending_choice, "遭遇敌人：1 攻击 2 战技 3 防御 4 道具 5 协力", "回复征途 1 至 5 进行战斗")
                else:
                    personal.pending_choice = f"{date_key}:loot"
                    response = self._response(personal, context, "loot", personal.pending_choice, "安全返回希望号：1 整备补给", "回复征途 1 完成整备")
            elif phase == "combat":
                action = ("attack", "skill", "defend", "item", "companion")[choice - 1]
                if personal.combat is None:
                    raise ValueError("当前没有战斗")
                personal.combat = resolve_turn(personal.combat, action, companion_action="support", job=personal.job)
                result = personal.combat.result
                if personal.combat.resolved:
                    personal.weekly.action_dates.append(date_key)
                    if result["status"] == "victory":
                        grant_reward(personal, event_id("daily", personal.user_id, date_key, "action"), 300, source="daily")
                        grant_reward(personal, event_id("location", personal.user_id, date_key, personal.combat.encounter_id), result["reward"], source="location")
                        personal.pending_choice = f"{date_key}:loot"
                        response = self._response(personal, context, "loot", personal.pending_choice, "战斗胜利：1 收下战利品", "回复征途 1 完成远征")
                    else:
                        lose_fire(personal, "battle_injury", personal.combat.encounter_id)
                        personal.pending_choice = None
                        response = self._response(personal, context, "journal", f"{date_key}:defeat", f"战斗失利，剩余火种 {personal.weekly.fire}", "战斗结果已记录")
                else:
                    response = self._response(personal, context, "combat", personal.pending_choice, f"战斗继续，敌人生命 {personal.combat.enemy_hp}：1 攻击 2 战技 3 防御 4 道具 5 协力", "回复征途 1 至 5 继续战斗")
            elif phase in {"loot", "camp"}:
                if phase == "camp":
                    amount = camp_support(personal, date_key)
                    if amount:
                        grant_reward(personal, event_id("camp", personal.user_id, date_key, "support"), amount, source="camp")
                    personal.weekly.action_dates.append(date_key)
                else:
                    personal.inventory.temporary_items.append("item_001" if choice == 1 else "item_002")
                personal.pending_choice = None
                response = self._response(personal, context, "journal", f"{date_key}:{phase}:done", "今日旅途手账已更新", "今日远征已完成")
            else:
                raise ValueError("征途选项无效")
            await self._persist()
            return response

    async def combat_action(self, user_id: str, action: str) -> ServiceResponse:
        if action not in {"attack", "skill", "defend", "item", "companion"}:
            raise ValueError("战斗行动无效")
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            if personal.combat is None:
                personal.combat = start_battle(personal, "ordinary_001", f"combat:{personal.weekly.week_index}")
            personal.combat = resolve_turn(personal.combat, action, job=personal.job)
            context = self._now()
            response = self._response(personal, context, "combat", f"combat:{personal.combat.turn}", personal.combat.result.get("status", "战斗中"), "战斗结果已保存")
            await self._persist()
            return response

    async def partner_talk(self, user_id: str, quote: str, now: datetime | None = None) -> ServiceResponse:
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            context = self._now(now)
            date_key = context.current_date.isoformat()
            if not context.can_start:
                return self._response(personal, context, "journal", "partner:outside", "活动当前不可交谈", "活动当前不可交谈")
            if date_key in personal.partner_action_dates:
                return self._response(personal, context, "partner", f"partner:{date_key}:duplicate", "今天已经和同行伙伴交谈过", "今日伙伴对话已完成")
            partner = self._week(context)["partner"]
            if partner != "all":
                apply_bond_delta(personal, partner, {"rapport": 1}, date_key)
            personal.partner_action_dates.append(date_key)
            response = self._response(personal, context, "partner", f"partner:{date_key}", f"同行伙伴回应：{str(quote)[:36]}", "伙伴回应已记录")
            await self._persist()
            return response

    async def map_view(self, user_id: str, now: datetime | None = None) -> ServiceResponse:
        context = self._now(now)
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            routes = visible_routes(personal, get_world(), context)
            return self._response(personal, context, "route", "map", f"开放地点 {len(routes)} 个", "地图已更新")

    async def status_view(self, user_id: str) -> ServiceResponse:
        async with user_lock(str(user_id)):
            personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
            return self._response(personal, self._now(), "journal", "status", f"职业 {personal.job or '未选择'} · 徽记 {personal.current_emblems} · 火种 {personal.weekly.fire}", "状态已更新")

    async def archive_view(self, user_id: str) -> ServiceResponse:
        response = await self.status_view(user_id)
        return ServiceResponse("archive", response.image, "图鉴记录已更新")

    async def help_view(self, user_id: str) -> ServiceResponse:
        response = await self.status_view(user_id)
        return ServiceResponse("help", response.image, "发送王道征途开始当日远征")

    async def vote_view(self, user_id: str, choice: int | None = None, now: datetime | None = None) -> ServiceResponse:
        context = self._now(now)
        if not context.can_start or context.weekday < 4:
            raise ValueError("王道投票将在周五晨星节点后开放")
        week = self._week(context)
        async with world_lock(context.week_index or 0):
            async with user_lock(str(user_id)):
                personal = get_personal(str(user_id)) or set_personal(PersonalState(user_id=str(user_id)))
                if context.current_date.isoformat() not in personal.weekly.action_dates:
                    raise ValueError("完成今日晨星节点后才能投票")
                box = get_world().votes.get(str(context.week_index))
                if box is None:
                    box = open_vote(get_world(), context.week_index or 0, week["vote_options"], week["tie_priority"])
                mark_eligible(box, user_id)
                if choice is not None:
                    if choice < 1 or choice > len(week["vote_options"]):
                        raise ValueError("投票选项无效")
                    cast_vote(box, user_id, week["vote_options"][choice - 1])
                counts = sum(1 for _ in box.choices)
                response = self._response(personal, context, "vote", f"vote:{context.week_index}", f"本周投票 {counts} 人：1 {week['vote_options'][0]} 2 {week['vote_options'][1]} 3 {week['vote_options'][2]}", "回复 王道投票 1 至 3 投票或修改")
                await self._persist()
                return response

    async def settle(self, user_id: str, now: datetime | None = None) -> ServiceResponse:
        from .integration.checkin_bridge import settlement_service
        context = self._now(now)
        if context.current_date < datetime(2027, 2, 1, tzinfo=ACTIVITY_TZ).date():
            raise ValueError("活动尚未结束")
        if context.current_date > datetime(2027, 2, 7, tzinfo=ACTIVITY_TZ).date():
            raise ValueError("王道结算已截止")
        async with settlement_lock(str(user_id)):
            personal = get_personal(str(user_id))
            if personal is None:
                raise ValueError("尚未建立王道征途存档")
            if personal.settlement_status == "applied":
                response = self._response(personal, context, "final", "settlement:duplicate", f"已结算 {personal.settlement_amount} 签到积分", "王道结算已完成")
                return response
            settlement_id = personal.settlement_id or event_id("settlement", personal.user_id, "2027-02-01", "credits")
            result = await settlement_service.settle(personal.user_id, personal.total_emblems, settlement_id)
            personal.settlement_id = settlement_id
            personal.settlement_amount = int(result.get("amount", 0))
            personal.settlement_status = str(result.get("status", "pending"))
            await self._persist()
            response = self._response(personal, context, "final", f"settlement:{personal.settlement_status}", f"累计徽记 {personal.total_emblems}，结算 {personal.settlement_amount} 签到积分", "王道结算结果已保存")
            return response

    async def close_week(self, week_index: int) -> dict:
        async with world_lock(week_index):
            summary = close_week(get_world(), week_index)
            await self._persist()
            return summary

    async def freeze(self) -> None:
        async with world_lock("freeze"):
            get_world().frozen = True
            await self._persist()


service = AdventureService()
