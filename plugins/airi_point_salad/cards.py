import random

from .models import Card, Character, GameSpeed, RuleKind, ScoreRule


CHARACTERS = tuple(Character)


def cards_per_character(player_count: int, speed: GameSpeed) -> int:
    if not 2 <= player_count <= 6:
        raise ValueError("仅支持 2–6 名玩家")
    return player_count * (2 if speed is GameSpeed.QUICK else 3)


def build_rule(character: Character, index: int) -> ScoreRule:
    position = CHARACTERS.index(character)
    others = [CHARACTERS[(position + offset) % len(CHARACTERS)] for offset in range(1, len(CHARACTERS))]
    variant = index % 5
    if variant == 0:
        return ScoreRule(RuleKind.EACH, [character], 2)
    if variant == 1:
        return ScoreRule(RuleKind.PAIR, [character, others[index % len(others)]], 5)
    if variant == 2:
        first = others[index % len(others)]
        second = others[(index + 1) % len(others)]
        return ScoreRule(RuleKind.SET, [character, first, second], 7)
    if variant == 3:
        relation = (">", "<", "=")[index % 3]
        return ScoreRule(RuleKind.COMPARE, [character, others[index % len(others)]], 8, relation=relation)
    return ScoreRule(RuleKind.RISK, [character, others[index % len(others)]], 3, penalty=-1)


def build_deck(player_count: int, speed: GameSpeed, seed: int) -> list[Card]:
    cards = []
    count = cards_per_character(player_count, speed)
    for character in CHARACTERS:
        for index in range(count):
            card_id = f"{character.value}-{index:02d}"
            cards.append(Card(card_id, character, build_rule(character, index)))
    random.Random(seed).shuffle(cards)
    return cards
