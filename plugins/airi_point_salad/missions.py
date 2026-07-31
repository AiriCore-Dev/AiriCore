import random
from collections import Counter
from dataclasses import dataclass, field

from .models import Character, GameState, PlayerState


@dataclass(frozen=True, slots=True)
class Mission:
    mission_id: str
    kind: str
    amount: int
    points: int
    characters: tuple[Character, ...] = ()


@dataclass(slots=True)
class TurnSummary:
    character_ids: list[str]
    score_ids: list[str] = field(default_factory=list)
    mission_claimed: bool = False


def mission_catalog() -> dict[str, Mission]:
    return {
        "same-3": Mission("same-3", "same", 3, 3),
        "different-3": Mission("different-3", "different", 3, 4),
        "two-pairs": Mission("two-pairs", "pairs", 2, 3),
        "score-and-character": Mission("score-and-character", "turn_types", 2, 2),
        "same-4": Mission("same-4", "same", 4, 4),
        "different-5": Mission("different-5", "different", 5, 4),
    }


def initialize_missions(state: GameState) -> None:
    state.mission_deck = list(mission_catalog())
    random.Random(state.seed ^ 0x7E21).shuffle(state.mission_deck)
    state.active_missions = []
    refill_missions(state)


def refill_missions(state: GameState) -> None:
    while len(state.active_missions) < 2 and state.mission_deck:
        state.active_missions.append(state.mission_deck.pop())


def claim_completed_mission(
    state: GameState,
    player: PlayerState,
    summary: TurnSummary,
) -> Mission | None:
    if summary.mission_claimed:
        return None
    catalog = mission_catalog()
    for mission_id in list(state.active_missions):
        mission = catalog[mission_id]
        if mission_completed(state, player, summary, mission):
            state.active_missions.remove(mission_id)
            player.mission_ids.append(mission_id)
            player.mission_points += mission.points
            summary.mission_claimed = True
            refill_missions(state)
            return mission
    return None


def mission_completed(
    state: GameState,
    player: PlayerState,
    summary: TurnSummary,
    mission: Mission,
) -> bool:
    counts = Counter(state.cards[card_id].character for card_id in player.character_cards)
    if mission.kind == "same":
        return bool(counts) and max(counts.values()) >= mission.amount
    if mission.kind == "different":
        return len(counts) >= mission.amount
    if mission.kind == "pairs":
        return sum(value >= 2 for value in counts.values()) >= mission.amount
    if mission.kind == "turn_types":
        return bool(summary.character_ids and summary.score_ids)
    return False
