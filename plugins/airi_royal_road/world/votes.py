from __future__ import annotations

from ..base.models import VoteBox, WorldState
from .state import normalized_user_id


def open_vote(world: WorldState, week_index: int, options: tuple[str, ...], hope_priority: str) -> VoteBox:
    box = VoteBox(week_index=week_index, opened=True, hope_priority=hope_priority)
    box.result = {"options": list(options)}
    world.votes[str(week_index)] = box
    return box


def mark_eligible(box: VoteBox, user_id: str | int) -> bool:
    user_id = normalized_user_id(user_id)
    if box.closed or user_id in box.eligible_users:
        return False
    box.eligible_users.append(user_id)
    return True


def cast_vote(box: VoteBox, user_id: str | int, choice: str) -> bool:
    user_id = normalized_user_id(user_id)
    if box.closed or not box.opened or user_id not in box.eligible_users:
        raise ValueError("当前没有投票资格")
    options = box.result.get("options", [])
    if choice not in options:
        raise ValueError("投票选项无效")
    changed = box.choices.get(user_id) != choice
    box.choices[user_id] = choice
    return changed


def change_vote(box: VoteBox, user_id: str | int, choice: str) -> bool:
    return cast_vote(box, user_id, choice)


def close_votes(box: VoteBox) -> dict:
    if box.closed:
        return dict(box.result.get("summary", {}))
    options = list(box.result.get("options", []))
    counts = {option: 0 for option in options}
    for choice in box.choices.values():
        counts[choice] = counts.get(choice, 0) + 1
    total = sum(counts.values())
    top = max(counts.values(), default=0)
    leaders = [option for option in options if counts.get(option, 0) == top]
    winner = box.hope_priority if box.hope_priority in leaders else (leaders[0] if leaders else box.hope_priority)
    percentages = {option: (counts[option] * 100.0 / total if total else 0.0) for option in options}
    summary = {"week_index": box.week_index, "counts": counts, "percentages": percentages, "winner": winner, "priority": box.hope_priority}
    box.closed = True
    box.result["summary"] = summary
    return summary
