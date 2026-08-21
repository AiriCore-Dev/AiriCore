from __future__ import annotations

from dataclasses import dataclass

from ..base.locks import event_id
from ..base.models import BondState, PersonalState, WeeklyRun
from ..content.characters import JOBS


@dataclass(frozen=True)
class Job:
    name: str
    job_id: str
    skills: tuple[str, ...]
    element: str
    stats: tuple[tuple[str, int], ...]


def available_jobs() -> tuple[Job, ...]:
    return tuple(Job(name, value["job_id"], value["skills"], value["element"], tuple(value["stats"].items())) for name, value in JOBS.items())


def apply_bond_delta(personal: PersonalState, member_id: str, delta: dict[str, int], event: str) -> bool:
    if set(delta) - {"trust", "candor", "rapport", "courage"} or any(not isinstance(value, int) or abs(value) > 1 for value in delta.values()):
        raise ValueError("羁绊变化不在规则范围内")
    marker = event_id("bond", personal.user_id, member_id, event)
    if marker in personal.event_ids:
        return False
    bond = personal.bonds.setdefault(member_id, BondState())
    for axis, value in delta.items():
        setattr(bond, axis, max(-10, min(10, getattr(bond, axis) + value)))
    personal.event_ids.append(marker)
    return True


def start_week(personal: PersonalState, week_index: int) -> bool:
    if personal.weekly.week_index == week_index:
        return False
    personal.weekly = WeeklyRun(week_index=week_index)
    personal.combat = None
    return True


def end_week(personal: PersonalState) -> None:
    personal.inventory.temporary_items.clear()
    personal.weekly.temporary_items.clear()
    personal.weekly.blessings.clear()
    personal.weekly.injuries.clear()
    personal.weekly.fire = 3
    personal.weekly.recalls_used = 0


def use_recall(personal: PersonalState, historical_date: str) -> bool:
    if personal.weekly.recalls_used >= 2 or historical_date in personal.weekly.action_dates:
        return False
    personal.weekly.recalls_used += 1
    personal.event_ids.append(event_id("recall", personal.user_id, historical_date, str(personal.weekly.week_index)))
    return True


def lose_fire(personal: PersonalState, injury_id: str, event: str) -> bool:
    marker = event_id("fire", personal.user_id, event, injury_id)
    if marker in personal.event_ids:
        return False
    personal.event_ids.append(marker)
    personal.weekly.fire = max(0, personal.weekly.fire - 1)
    if injury_id not in personal.weekly.injuries:
        personal.weekly.injuries.append(injury_id)
    return True


def camp_support(personal: PersonalState, event: str) -> int:
    if personal.weekly.fire != 0:
        raise ValueError("火种尚未归零")
    marker = event_id("camp", personal.user_id, event, str(personal.weekly.week_index))
    if marker in personal.event_ids:
        return 0
    personal.event_ids.append(marker)
    return 150 + personal.weekly.week_index % 101
