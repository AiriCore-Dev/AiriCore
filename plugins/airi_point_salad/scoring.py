from collections import Counter
from dataclasses import dataclass

from .models import Character, GameState, PlayerState, RuleKind, ScoreRule


@dataclass(frozen=True, slots=True)
class CardScore:
    card_id: str
    points: int


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    user_id: str
    card_scores: tuple[CardScore, ...]
    mission_points: int
    total: int


@dataclass(frozen=True, slots=True)
class RankedPlayer:
    rank: int
    player: PlayerState
    breakdown: ScoreBreakdown


def score_rule(rule: ScoreRule, counts: dict[Character, int]) -> int:
    values = [counts.get(character, 0) for character in rule.characters]
    if rule.kind is RuleKind.EACH:
        return values[0] * rule.points
    if rule.kind is RuleKind.PAIR:
        return min(values) * rule.points
    if rule.kind is RuleKind.SET:
        return min(values) * rule.points
    if rule.kind is RuleKind.COMPARE:
        matched = {
            ">": values[0] > values[1],
            "<": values[0] < values[1],
            "=": values[0] == values[1],
        }.get(rule.relation, False)
        return rule.points if matched else 0
    if rule.kind is RuleKind.RISK:
        return values[0] * rule.points + values[1] * rule.penalty
    raise ValueError("未知计分规则")


def character_counts(state: GameState, player: PlayerState) -> dict[Character, int]:
    counts = Counter(state.cards[card_id].character for card_id in player.character_cards)
    return {character: counts.get(character, 0) for character in Character}


def score_player(state: GameState, player: PlayerState) -> ScoreBreakdown:
    base_counts = character_counts(state, player)
    wildcard_card = player.skill_payload.get("score_card_id")
    wildcard_character = player.skill_payload.get("as_character")
    card_scores = []
    for card_id in player.score_cards:
        counts = dict(base_counts)
        if card_id == wildcard_card and wildcard_character:
            character = Character(wildcard_character)
            counts[character] = counts.get(character, 0) + 1
        points = score_rule(state.cards[card_id].rule, counts)
        card_scores.append(CardScore(card_id, points))
    total = sum(item.points for item in card_scores) + player.mission_points
    return ScoreBreakdown(player.user_id, tuple(card_scores), player.mission_points, total)


def rank_players(state: GameState) -> list[RankedPlayer]:
    scored = [(player, score_player(state, player)) for player in state.players]
    scored.sort(
        key=lambda item: (
            item[1].total,
            len(item[0].character_cards),
            len(item[0].mission_ids),
        ),
        reverse=True,
    )
    ranked = []
    previous_key = None
    previous_rank = 0
    for position, (player, breakdown) in enumerate(scored, 1):
        key = (breakdown.total, len(player.character_cards), len(player.mission_ids))
        rank = previous_rank if key == previous_key else position
        ranked.append(RankedPlayer(rank, player, breakdown))
        previous_key = key
        previous_rank = rank
    return ranked
