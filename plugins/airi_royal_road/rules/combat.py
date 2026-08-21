from __future__ import annotations

from dataclasses import replace

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
    return CombatState(encounter_id, enemy_id, 0, 60, enemy["hp"], [], None, False, {})


def validate_action(state: CombatState, action: str) -> None:
    if state.resolved or action not in ACTIONS:
        raise ValueError("当前战斗行动无效")


def resolve_turn(state: CombatState, action: str, companion_action: str | None = None, job: str | None = None) -> CombatState:
    validate_action(state, action)
    enemy = ENCOUNTERS[state.enemy_id]
    seed = seed_for("combat", state.turn, state.encounter_id, state.enemy_id)
    random = stream(seed, action)
    player_hp = state.player_hp
    enemy_hp = state.enemy_hp
    statuses = list(state.statuses)
    if action == "attack":
        damage = 8
    elif action == "skill":
        damage = 14 if job in JOBS else 11
    elif action == "companion":
        damage = 10 if companion_action else 5
    elif action == "item":
        player_hp = min(60, player_hp + 12)
        damage = 0
    else:
        damage = 0
    damage = max(0, damage - enemy["defense"] // 3)
    enemy_hp = max(0, enemy_hp - damage)
    enemy_damage = 0 if action == "defend" else max(1, enemy["attack"] - 2 if action == "item" else enemy["attack"])
    if enemy_hp == 0:
        return replace(state, turn=state.turn + 1, player_hp=player_hp, enemy_hp=0, pending_action=None, resolved=True, result={"status": "victory", "damage": damage, "reward": enemy["reward"]})
    player_hp = max(0, player_hp - enemy_damage)
    if player_hp == 0:
        return replace(state, turn=state.turn + 1, player_hp=0, enemy_hp=enemy_hp, pending_action=None, resolved=True, result={"status": "defeat", "damage": damage, "reward": 0})
    return replace(state, turn=state.turn + 1, player_hp=player_hp, enemy_hp=enemy_hp, statuses=statuses, pending_action=None, result={"status": "ongoing", "damage": damage, "enemy_telegraph": enemy["telegraph_id"], "roll": random.randrange(100)})


def resolve_battle(state: CombatState) -> dict:
    if not state.resolved:
        raise ValueError("战斗尚未结束")
    return dict(state.result)
