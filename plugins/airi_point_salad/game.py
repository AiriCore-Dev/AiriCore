from .cards import build_decks
from .missions import TurnSummary
from .models import Character, GameMode, GameSpeed, GameState, Phase, PlayerState


class GameError(ValueError):
    pass


def create_game(
    group_id: str,
    host_id: str,
    host_name: str,
    speed: GameSpeed,
    mode: GameMode,
    seed: int,
    now: float,
) -> GameState:
    state = GameState(
        group_id=group_id,
        host_id=host_id,
        speed=speed,
        mode=mode,
        seed=seed,
        created_at=now,
        updated_at=now,
    )
    state.players.append(PlayerState(host_id, host_name))
    return state


def add_player(state: GameState, user_id: str, name: str, now: float) -> None:
    require_lobby(state)
    if any(player.user_id == user_id for player in state.players):
        raise GameError("你已经加入本局")
    if len(state.players) >= 6:
        raise GameError("本局人数已满")
    state.players.append(PlayerState(user_id, name))
    state.updated_at = now


def remove_player(state: GameState, user_id: str, now: float) -> None:
    require_lobby(state)
    index = next((i for i, player in enumerate(state.players) if player.user_id == user_id), None)
    if index is None:
        raise GameError("你还没有加入本局")
    state.players.pop(index)
    if not state.players:
        state.phase = Phase.FINISHED
    elif user_id == state.host_id:
        state.host_id = state.players[0].user_id
    state.updated_at = now


def start_game(state: GameState, user_id: str, now: float) -> None:
    require_lobby(state)
    if user_id != state.host_id:
        raise GameError("只有房主可以开始游戏")
    if len(state.players) < 2:
        raise GameError("至少需要 2 名玩家")
    state.cards, state.decks, starting_player = build_decks(
        len(state.players), state.speed, state.seed
    )
    state.phase = Phase.PLAYING
    state.current_player = starting_player
    state.starting_player = starting_player
    state.turn_number = 1
    state.turn_flips = 0
    refill_market(state)
    if state.mode is GameMode.MIX:
        from .missions import initialize_missions
        from .skills import assign_centers

        assign_centers(state)
        initialize_missions(state)
    state.updated_at = now


def stop_game(state: GameState, user_id: str, is_admin: bool, now: float) -> None:
    if user_id != state.host_id and not is_admin:
        raise GameError("只有房主或群管理员可以结束游戏")
    state.phase = Phase.FINISHED
    state.updated_at = now


def flip_score(state: GameState, user_id: str, score_index: int, now: float) -> str:
    if state.phase is not Phase.PLAYING:
        raise GameError("当前没有进行中的游戏")
    if state.post_flip_available and state.post_flip_user_id == user_id:
        player = next(
            (item for item in state.players if item.user_id == user_id),
            None,
        )
        if player is None:
            raise GameError("你不在本局游戏中")
        if not 0 <= score_index < len(player.score_cards):
            raise GameError("计分牌编号无效")
        card_id = player.score_cards.pop(score_index)
        player.character_cards.append(card_id)
        state.post_flip_user_id = None
        state.post_flip_available = False
        state.updated_at = now
        return card_id
    player = require_turn(state, user_id)
    pending = state.pending_skill.get("kind") if state.pending_skill.get("user_id") == user_id else None
    if pending == "airi_armed":
        raise GameError("Airi 技能生效的回合不能翻牌")
    if pending == "minori_swap":
        raise GameError("请先完成实乃理的角色牌交换")
    if state.turn_flips >= 1:
        raise GameError("本回合已经翻过牌")
    if not 0 <= score_index < len(player.score_cards):
        raise GameError("计分牌编号无效")
    close_post_flip_window(state, user_id)
    card_id = player.score_cards.pop(score_index)
    player.character_cards.append(card_id)
    state.turn_flips += 1
    state.updated_at = now
    return card_id


def take_score(
    state: GameState,
    user_id: str,
    column: int,
    now: float,
    extra_slot: tuple[int, int] | None = None,
) -> str:
    player = require_turn(state, user_id)
    pending = state.pending_skill.get("kind") if state.pending_skill.get("user_id") == user_id else None
    if pending in {"minori_armed", "minori_swap"}:
        raise GameError("实乃理技能准备后必须完成角色牌拿取与交换")
    if not 0 <= column < 3 or not state.decks[column]:
        raise GameError("该列没有可拿取的计分牌")
    airi_armed = (
        state.pending_skill.get("kind") == "airi_armed"
        and state.pending_skill.get("user_id") == user_id
        and player.center is Character.AIRI
    )
    extra_card = None
    if airi_armed:
        if extra_slot is None or extra_slot[0] != column:
            raise GameError("Airi 的技能需要选择同列一张角色牌")
        extra_card = require_character_slot(state, extra_slot)
    elif extra_slot is not None:
        raise GameError("普通拿取计分牌不能附带角色牌")
    close_post_flip_window(state, user_id)
    card_id = state.decks[column].pop()
    player.score_cards.append(card_id)
    summary = TurnSummary([], [card_id])
    if extra_card is not None:
        state.character_market[extra_slot[0]][extra_slot[1]] = None
        player.character_cards.append(extra_card)
        player.skill_used = True
        state.pending_skill = {}
        summary.character_ids.append(extra_card)
    finish_action(state, now, summary, allow_post_flip=not airi_armed)
    return card_id


def take_characters(
    state: GameState,
    user_id: str,
    slots: list[tuple[int, int]],
    now: float,
) -> list[str]:
    player = require_turn(state, user_id)
    pending = state.pending_skill.get("kind") if state.pending_skill.get("user_id") == user_id else None
    if pending == "airi_armed":
        raise GameError("Airi 技能准备后必须拿取计分牌和同列角色牌")
    if pending == "minori_swap":
        raise GameError("请先完成实乃理的角色牌交换")
    available = available_character_slots(state)
    required = min(2, len(available))
    if required == 0:
        raise GameError("市场中没有可拿取的角色牌")
    if len(slots) != required or len(set(slots)) != len(slots):
        raise GameError(f"本回合需要拿取 {required} 张不同位置的角色牌")
    card_ids = [require_character_slot(state, slot) for slot in slots]
    close_post_flip_window(state, user_id)
    for column, row in slots:
        state.character_market[column][row] = None
    player.character_cards.extend(card_ids)
    if (
        state.pending_skill.get("kind") == "minori_armed"
        and state.pending_skill.get("user_id") == user_id
        and player.center is Character.MINORI
    ):
        state.pending_skill = {
            "kind": "minori_swap",
            "user_id": user_id,
            "taken": {
                f"{slot[0]}:{slot[1]}": card_id
                for slot, card_id in zip(slots, card_ids)
            },
        }
        state.updated_at = now
        return card_ids
    finish_action(state, now, TurnSummary(card_ids))
    return card_ids


def refill_market(state: GameState) -> None:
    while True:
        changed = rebalance_empty_decks(state)
        for column in range(3):
            for row in range(2):
                if state.character_market[column][row] is None and state.decks[column]:
                    state.character_market[column][row] = state.decks[column].pop()
                    changed = True
        if not changed:
            return


def rebalance_empty_decks(state: GameState) -> bool:
    changed = False
    while True:
        empty_column = next(
            (index for index, deck in enumerate(state.decks) if not deck),
            None,
        )
        if empty_column is None:
            return changed
        source_column = max(
            range(3),
            key=lambda index: (len(state.decks[index]), -index),
        )
        amount = len(state.decks[source_column]) // 2
        if amount == 0:
            return changed
        source = state.decks[source_column]
        state.decks[empty_column] = source[:amount]
        del source[:amount]
        changed = True


def finish_action(
    state: GameState,
    now: float,
    summary: TurnSummary | None = None,
    allow_post_flip: bool = True,
) -> None:
    player = state.players[state.current_player]
    if state.mode is GameMode.MIX and summary is not None:
        from .missions import claim_completed_mission

        claim_completed_mission(state, player, summary)
    player.last_action_turn = state.turn_number
    refill_market(state)
    state.updated_at = now
    if not any(state.decks) and not any(
        card_id for column in state.character_market for card_id in column
    ):
        state.post_flip_user_id = None
        state.post_flip_available = False
        state.phase = Phase.FINISHED
        return
    state.post_flip_user_id = player.user_id
    state.post_flip_available = state.turn_flips == 0 and allow_post_flip
    state.current_player = (state.current_player + 1) % len(state.players)
    state.turn_number += 1
    state.turn_flips = 0


def close_post_flip_window(state: GameState, user_id: str) -> None:
    if state.post_flip_available and state.post_flip_user_id != user_id:
        state.post_flip_user_id = None
        state.post_flip_available = False


def require_lobby(state: GameState) -> None:
    if state.phase is not Phase.LOBBY:
        raise GameError("游戏已经开始")


def require_turn(state: GameState, user_id: str) -> PlayerState:
    if state.phase is not Phase.PLAYING:
        raise GameError("当前没有进行中的游戏")
    player = state.players[state.current_player]
    if player.user_id != user_id:
        raise GameError("还没轮到你")
    return player


def available_character_slots(state: GameState) -> list[tuple[int, int]]:
    return [
        (column, row)
        for column in range(3)
        for row in range(2)
        if state.character_market[column][row] is not None
    ]


def require_character_slot(state: GameState, slot: tuple[int, int]) -> str:
    column, row = slot
    if not 0 <= column < 3 or not 0 <= row < 2:
        raise GameError("角色牌位置无效")
    card_id = state.character_market[column][row]
    if card_id is None:
        raise GameError("该位置没有角色牌")
    return card_id


def pop_index(items: list[str], index: int, message: str) -> str:
    if not 0 <= index < len(items):
        raise GameError(message)
    return items.pop(index)
