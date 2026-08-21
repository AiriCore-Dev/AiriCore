from __future__ import annotations

from dataclasses import replace
from math import ceil

from ..base.models import CombatState, PersonalState
from ..content.encounters import ENCOUNTERS
from ..content.characters import JOBS
from .rng import seed_for, stream


ACTIONS = {"attack", "skill", "defend", "item", "companion"}
ELEMENT_ADVANTAGE = {"火": "风", "风": "潮", "潮": "火", "光": "暗"}


def start_battle(personal: PersonalState, enemy_id: str, encounter_id: str) -> CombatState:
    if enemy_id not in ENCOUNTERS:
        raise ValueError("未知敌人")
    enemy = ENCOUNTERS[enemy_id]
    player_hp = 60 + personal.weekly.fire * 10 if enemy["kind"] in {"weekly_boss", "act_boss"} else 60
    return CombatState(encounter_id, enemy_id, 0, player_hp, enemy["hp"], [], enemy["telegraph_id"], False, {})


def validate_action(state: CombatState, action: str) -> None:
    if state.resolved or action not in ACTIONS:
        raise ValueError("当前战斗行动无效")


def resolve_turn(state: CombatState, action: str, companion_action: str | None = None, job: str | None = None, request_id: str | None = None) -> CombatState:
    request_id = request_id or f"turn:{state.turn}:{action}"
    if request_id in state.action_receipts:
        return state
    validate_action(state, action)
    enemy = ENCOUNTERS[state.enemy_id]
    seed = seed_for("combat", state.turn, state.encounter_id, state.enemy_id)
    random = stream(seed, action)
    player_hp = state.player_hp
    enemy_hp = state.enemy_hp
    statuses = list(state.statuses)
    job_record = JOBS.get(job or "", {})
    player_element = job_record.get("element", "")
    player_speed = int(job_record.get("stats", {}).get("speed", 5))
    order = "player_first" if player_speed >= enemy["speed"] else "enemy_first"
    next_turn = state.turn + 1
    minimum_turn, maximum_turn = enemy["turn_range"]

    def recorded(next_state: CombatState) -> CombatState:
        receipts = {key: dict(value) for key, value in state.action_receipts.items()}
        receipts[request_id] = dict(next_state.result)
        return replace(next_state, action_receipts=receipts)
    if action == "attack":
        damage = 8
    elif action == "skill":
        damage = 14 if job in JOBS else 11
    elif action == "companion":
        if not companion_action:
            raise ValueError("需要同行伙伴协力")
        damage = 10
    elif action == "item":
        maximum_player_hp = 90 if enemy["kind"] in {"weekly_boss", "act_boss"} else 60
        player_hp = min(maximum_player_hp, player_hp + 12)
        damage = 0
    else:
        damage = 0
        if "guard" not in statuses:
            statuses.append("guard")
    weakness = action == "skill" and player_element == enemy["weakness"]
    if weakness:
        damage += 4
    damage = max(0, damage - enemy["defense"] // 3)
    if action in {"attack", "skill", "companion"}:
        damage = max(damage, ceil(enemy["hp"] / maximum_turn))
    if next_turn < minimum_turn:
        damage = min(damage, max(0, enemy_hp - 1))
    enemy_damage = max(1, enemy["attack"] - 2 if action == "item" else enemy["attack"])
    if action == "defend":
        enemy_damage = max(1, enemy_damage // 2)
    if order == "enemy_first":
        player_hp = max(0, player_hp - enemy_damage)
        if player_hp == 0:
            return recorded(replace(state, turn=next_turn, player_hp=0, pending_action=None, resolved=True, result={"status": "defeat", "damage": 0, "reward": 0, "order": order, "weakness": weakness}))
    enemy_hp = max(0, enemy_hp - damage)
    if enemy_hp == 0:
        return recorded(replace(state, turn=next_turn, player_hp=player_hp, enemy_hp=0, statuses=statuses, pending_action=None, resolved=True, result={"status": "victory", "damage": damage, "reward": enemy["reward"], "order": order, "weakness": weakness}))
    if order == "player_first":
        player_hp = max(0, player_hp - enemy_damage)
    if player_hp == 0:
        return recorded(replace(state, turn=next_turn, player_hp=0, enemy_hp=enemy_hp, statuses=statuses, pending_action=None, resolved=True, result={"status": "defeat", "damage": damage, "reward": 0, "order": order, "weakness": weakness}))
    if next_turn >= maximum_turn:
        return recorded(replace(state, turn=next_turn, player_hp=player_hp, enemy_hp=enemy_hp, statuses=statuses, pending_action=None, resolved=True, result={"status": "defeat", "damage": damage, "reward": 0, "order": order, "weakness": weakness}))
    return recorded(replace(state, turn=next_turn, player_hp=player_hp, enemy_hp=enemy_hp, statuses=statuses, pending_action=enemy["telegraph_id"], result={"status": "ongoing", "damage": damage, "enemy_telegraph": enemy["telegraph_id"], "roll": random.randrange(100), "order": order, "weakness": weakness}))


def resolve_battle(state: CombatState) -> dict:
    if not state.resolved:
        raise ValueError("战斗尚未结束")
    return dict(state.result)
