from __future__ import annotations

from dataclasses import dataclass

from ..base.constants import CREDIT_CAP, EMBLEM_TO_CREDIT
from ..base.locks import event_id
from ..base.models import PersonalState


SOURCES = {"daily", "location", "weekly", "boss", "act", "camp"}


@dataclass(frozen=True)
class RewardResult:
    event_id: str
    current_delta: int
    total_delta: int
    duplicate: bool


def grant_reward(personal: PersonalState, source_event: str, current_delta: int, total_delta: int | None = None, source: str = "daily") -> RewardResult:
    if source not in SOURCES or isinstance(current_delta, bool) or not isinstance(current_delta, int) or current_delta < 0:
        raise ValueError("奖励来源或数值无效")
    if total_delta is None:
        total_delta = current_delta
    if total_delta < 0 or total_delta < current_delta:
        raise ValueError("累计奖励无效")
    marker = event_id("reward", personal.user_id, source_event, source)
    if marker in personal.event_ids:
        return RewardResult(marker, 0, 0, True)
    personal.event_ids.append(marker)
    personal.current_emblems += current_delta
    personal.total_emblems += total_delta
    return RewardResult(marker, current_delta, total_delta, False)


def spend_emblems(personal: PersonalState, amount: int, item_id: str) -> bool:
    if not isinstance(amount, int) or amount < 0 or amount > personal.current_emblems or item_id.startswith("daily_check"):
        return False
    personal.current_emblems -= amount
    return True


def settlement_amount(total_emblems: int) -> int:
    if total_emblems < 0:
        raise ValueError("累计徽记不能为负")
    return min(total_emblems // EMBLEM_TO_CREDIT, CREDIT_CAP)
