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


def score_rule(
    rule: ScoreRule,
    own_counts: dict[Character, int],
    all_counts: tuple[dict[Character, int], ...],
) -> int:
    if rule.kind is RuleKind.MOST:
        value = own_counts[rule.target]
        return (
            rule.points
            if value == max(counts[rule.target] for counts in all_counts)
            else 0
        )
    if rule.kind is RuleKind.FEWEST:
        value = own_counts[rule.target]
        return (
            rule.points
            if value == min(counts[rule.target] for counts in all_counts)
            else 0
        )
    if rule.kind is RuleKind.PARITY:
        return (
            rule.points
            if own_counts[rule.target] % 2 == 0
            else rule.odd_points
        )
    if rule.kind is RuleKind.LINEAR:
        return sum(
            own_counts[character] * weight
            for character, weight in rule.weights.items()
        )
    if rule.kind in {RuleKind.SAME_PAIR, RuleKind.SAME_TRIPLE}:
        return own_counts[rule.target] // rule.threshold * rule.points
    if rule.kind is RuleKind.SET:
        groups = min(
            own_counts[character] // amount
            for character, amount in rule.requirements.items()
        )
        return groups * rule.points
    if rule.kind is RuleKind.MISSING_TYPES:
        return sum(own_counts[character] == 0 for character in Character) * rule.points
    if rule.kind is RuleKind.TYPES_AT_LEAST:
        return (
            sum(
                own_counts[character] >= rule.threshold
                for character in Character
            )
            * rule.points
        )
    if rule.kind is RuleKind.MOST_TOTAL:
        total = sum(own_counts.values())
        return (
            rule.points
            if total == max(sum(counts.values()) for counts in all_counts)
            else 0
        )
    if rule.kind is RuleKind.FEWEST_TOTAL:
        total = sum(own_counts.values())
        return (
            rule.points
            if total == min(sum(counts.values()) for counts in all_counts)
            else 0
        )
    if rule.kind is RuleKind.COMPLETE_SET:
        return min(own_counts.values()) * rule.points
    raise ValueError("未知计分规则")


def character_counts(state: GameState, player: PlayerState) -> dict[Character, int]:
    counts = Counter(state.cards[card_id].character for card_id in player.character_cards)
    return {character: counts.get(character, 0) for character in Character}


def score_player(state: GameState, player: PlayerState) -> ScoreBreakdown:
    players = state.players if state.players else [player]
    all_counts = tuple(character_counts(state, item) for item in players)
    try:
        player_index = players.index(player)
    except ValueError:
        all_counts = (*all_counts, character_counts(state, player))
        player_index = len(all_counts) - 1
    return _score_player(state, player, all_counts[player_index], all_counts)


def _score_player(
    state: GameState,
    player: PlayerState,
    base_counts: dict[Character, int],
    all_counts: tuple[dict[Character, int], ...],
) -> ScoreBreakdown:
    wildcard_card = player.skill_payload.get("score_card_id")
    wildcard_character = player.skill_payload.get("as_character")
    card_scores = []
    for card_id in player.score_cards:
        counts = dict(base_counts)
        if card_id == wildcard_card and wildcard_character:
            character = Character(wildcard_character)
            counts[character] = counts.get(character, 0) + 1
        points = score_rule(state.cards[card_id].rule, counts, all_counts)
        card_scores.append(CardScore(card_id, points))
    total = sum(item.points for item in card_scores) + player.mission_points
    return ScoreBreakdown(player.user_id, tuple(card_scores), player.mission_points, total)


def rank_players(state: GameState) -> list[RankedPlayer]:
    all_counts = tuple(character_counts(state, player) for player in state.players)
    scored = [
        (player, _score_player(state, player, all_counts[index], all_counts))
        for index, player in enumerate(state.players)
    ]
    scored.sort(
        key=lambda item: (
            item[1].total,
            item[0].last_action_turn,
        ),
        reverse=True,
    )
    return [
        RankedPlayer(position, player, breakdown)
        for position, (player, breakdown) in enumerate(scored, 1)
    ]
