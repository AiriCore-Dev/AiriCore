import random
from dataclasses import dataclass
from typing import Any

from .game import (
    GameError,
    finish_action,
    pop_index,
    refill_market,
    require_character_slot,
    require_turn,
)
from .missions import TurnSummary
from .models import Character, GameState


@dataclass(frozen=True, slots=True)
class SkillResult:
    message: str
    turn_finished: bool = False


def assign_centers(state: GameState) -> None:
    centers = list(Character)
    random.Random(state.seed ^ 0x5A17).shuffle(centers)
    state.centers = centers[: len(state.players)]
    for player, center in zip(state.players, state.centers):
        player.center = center


def skill_usage(center: Character) -> str:
    return {
        Character.MINORI: "sl sk，然后正常拿角色牌，再按提示交换",
        Character.HARUKA: "sl sk A",
        Character.AIRI: "sl sk，然后使用 sl ta A A1",
        Character.SHIZUKU: "sl sk 2",
        Character.MIKU: "sl sk 2 rin",
        Character.RIN: "sl sk A1 B2 C1",
    }[center]


def use_skill(state: GameState, user_id: str, args: list[Any], now: float) -> SkillResult:
    player = require_turn(state, user_id)
    if player.center is None:
        raise GameError("当前角色没有可用技能")
    if player.skill_used:
        raise GameError("本局已经使用过 Center 技能")
    if player.center is Character.MINORI:
        return _use_minori(state, player, args, now)
    if player.center is Character.HARUKA:
        return _use_haruka(state, player, args, now)
    if player.center is Character.AIRI:
        return _arm(state, player, args, "airi_armed", now)
    if player.center is Character.SHIZUKU:
        return _use_shizuku(state, player, args, now)
    if player.center is Character.MIKU:
        return _use_miku(state, player, args, now)
    if player.center is Character.RIN:
        return _use_rin(state, player, args, now)
    raise GameError("未知 Center 技能")


def _arm(state, player, args, kind, now):
    if args:
        raise GameError(f"该技能无需参数：{skill_usage(player.center)}")
    if state.pending_skill:
        raise GameError("已有待完成的技能操作")
    if kind == "airi_armed" and state.turn_flips:
        raise GameError("本回合已经翻过牌，不能再发动桃井爱莉技能")
    state.pending_skill = {"kind": kind, "user_id": player.user_id}
    state.updated_at = now
    return SkillResult("技能已准备，请继续完成本回合拿牌")


def _use_minori(state, player, args, now):
    kind = state.pending_skill.get("kind")
    if not args and not state.pending_skill:
        return _arm(state, player, args, "minori_armed", now)
    if kind != "minori_swap" or state.pending_skill.get("user_id") != player.user_id:
        raise GameError(f"技能参数无效：{skill_usage(player.center)}")
    if len(args) != 2 or not all(isinstance(item, tuple) for item in args):
        raise GameError("请指定要放回的位置和新位置")
    return_slot, new_slot = args
    taken = state.pending_skill.get("taken", {})
    return_key = f"{return_slot[0]}:{return_slot[1]}"
    if return_key not in taken or return_slot == new_slot:
        raise GameError("放回位置不属于本回合取得的角色牌")
    new_card = require_character_slot(state, new_slot)
    returned_card = taken[return_key]
    player.character_cards.remove(returned_card)
    state.character_market[return_slot[0]][return_slot[1]] = returned_card
    state.character_market[new_slot[0]][new_slot[1]] = None
    player.character_cards.append(new_card)
    player.skill_used = True
    state.pending_skill = {}
    finish_action(state, now, TurnSummary([new_card]))
    return SkillResult("已完成实乃理的角色牌交换", True)


def _use_haruka(state, player, args, now):
    if len(args) != 1 or type(args[0]) is not int or not 0 <= args[0] < 3:
        raise GameError(f"请选择一列：{skill_usage(player.center)}")
    column = args[0]
    returned = []
    if state.score_market[column] is not None:
        returned.append(state.score_market[column])
    returned.extend(card_id for card_id in state.character_market[column] if card_id is not None)
    if not returned:
        raise GameError("该列没有可刷新的卡牌")
    state.score_market[column] = None
    state.character_market[column] = [None, None]
    state.deck[0:0] = returned
    refill_market(state)
    player.skill_used = True
    state.updated_at = now
    return SkillResult("已刷新指定市场列")


def _use_shizuku(state, player, args, now):
    if len(args) != 1 or type(args[0]) is not int:
        raise GameError(f"请选择计分牌：{skill_usage(player.center)}")
    card_id = pop_index(player.score_cards, args[0], "计分牌编号无效")
    player.character_cards.append(card_id)
    player.skill_used = True
    state.updated_at = now
    return SkillResult("已额外翻转一张计分牌")


def _use_miku(state, player, args, now):
    if len(args) != 2 or type(args[0]) is not int or not isinstance(args[1], Character):
        raise GameError(f"请选择计分牌和角色：{skill_usage(player.center)}")
    if not 0 <= args[0] < len(player.score_cards):
        raise GameError("计分牌编号无效")
    player.skill_payload = {
        "score_card_id": player.score_cards[args[0]],
        "as_character": args[1].value,
    }
    player.skill_used = True
    state.updated_at = now
    return SkillResult("未来共鸣已记录，将在结算时生效")


def _use_rin(state, player, args, now):
    if len(args) != 3 or len(set(args)) != 3 or not all(isinstance(item, tuple) for item in args):
        raise GameError(f"请选择三张不同角色牌：{skill_usage(player.center)}")
    card_ids = [require_character_slot(state, slot) for slot in args]
    if len({state.cards[card_id].character for card_id in card_ids}) != 3:
        raise GameError("铃的技能必须拿取三名不同角色")
    for column, row in args:
        state.character_market[column][row] = None
    player.character_cards.extend(card_ids)
    player.skill_used = True
    finish_action(state, now, TurnSummary(card_ids))
    return SkillResult("已拿取三名不同角色", True)
