from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import random
from typing import Any

from .models import Card, Character, GameSpeed, RuleKind, ScoreRule


CATALOG_PATH = Path(__file__).resolve().parent / "assets" / "cards.json"
PRODUCE_MAPPING = {
    "cabbage": "haruka",
    "carrot": "shizuku",
    "lettuce": "minori",
    "onion": "airi",
    "pepper": "rin",
    "tomato": "miku",
}
PRODUCE_PREFIXES = {
    "cabbage": "CAB",
    "carrot": "CAR",
    "lettuce": "LET",
    "onion": "ONI",
    "pepper": "PEP",
    "tomato": "TOM",
}
RULE_FIELDS = {
    RuleKind.MOST: {"type", "target", "points"},
    RuleKind.FEWEST: {"type", "target", "points"},
    RuleKind.PARITY: {"type", "target", "points", "odd_points"},
    RuleKind.LINEAR: {"type", "weights"},
    RuleKind.SAME_PAIR: {"type", "target", "threshold", "points"},
    RuleKind.SAME_TRIPLE: {"type", "target", "threshold", "points"},
    RuleKind.SET: {"type", "requirements", "points"},
    RuleKind.MISSING_TYPES: {"type", "threshold", "points"},
    RuleKind.TYPES_AT_LEAST: {"type", "threshold", "points"},
    RuleKind.FEWEST_TOTAL: {"type", "points"},
    RuleKind.MOST_TOTAL: {"type", "points"},
    RuleKind.COMPLETE_SET: {"type", "points"},
}


@lru_cache(maxsize=1)
def load_catalog() -> tuple[Card, ...]:
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file, parse_constant=_reject_constant)
    return _decode_catalog(payload)


def _decode_catalog(payload: Any) -> tuple[Card, ...]:
    payload = _object(payload, "卡牌目录")
    _exact_keys(payload, {"schema_version", "produce_mapping", "cards"}, "卡牌目录")
    if _integer(payload["schema_version"], "schema_version") != 1:
        raise ValueError("不支持的卡牌目录版本")
    mapping = _decode_mapping(payload["produce_mapping"])
    raw_cards = _list(payload["cards"], "cards")
    cards = tuple(_decode_card(item, mapping) for item in raw_cards)
    expected = _expected_cards()
    if len(cards) != 108:
        raise ValueError("官方卡牌目录必须包含 108 张牌")
    if {card.card_id for card in cards} != set(expected):
        raise ValueError("卡牌 ID 未完整覆盖官方目录")
    if {card.source for card in cards} != {
        source for _, source in expected.values()
    }:
        raise ValueError("卡牌源位置未完整覆盖官方目录")
    if len({card.card_id for card in cards}) != len(cards):
        raise ValueError("卡牌 ID 不得重复")
    if len({card.source for card in cards}) != len(cards):
        raise ValueError("卡牌源位置不得重复")
    produce_counts = Counter(card.produce for card in cards)
    if produce_counts != Counter({produce: 18 for produce in PRODUCE_MAPPING}):
        raise ValueError("每种蔬菜面必须恰好包含 18 张牌")
    for card in cards:
        produce, source = expected[card.card_id]
        if card.produce != produce or card.source != source:
            raise ValueError("卡牌 ID、蔬菜面与源位置不匹配")
    return cards


def _decode_mapping(value: Any) -> dict[str, str]:
    value = _object(value, "produce_mapping")
    _exact_keys(value, set(PRODUCE_MAPPING), "produce_mapping")
    mapping = {
        _produce(key, "produce_mapping 键"): _string(
            character, "produce_mapping 值"
        )
        for key, character in value.items()
    }
    if set(mapping.values()) != {character.value for character in Character}:
        raise ValueError("蔬菜与角色映射必须是一一对应")
    if mapping != PRODUCE_MAPPING:
        raise ValueError("蔬菜与角色映射不符合主题目录")
    return mapping


def _decode_card(value: Any, mapping: dict[str, str]) -> Card:
    value = _object(value, "卡牌")
    _exact_keys(value, {"id", "produce", "source", "rule"}, "卡牌")
    produce = _produce(value["produce"], "card.produce")
    return Card(
        card_id=_string(value["id"], "card.id"),
        character=Character(mapping[produce]),
        rule=_decode_rule(value["rule"], mapping),
        produce=produce,
        source=_string(value["source"], "card.source"),
    )


def _decode_rule(value: Any, mapping: dict[str, str]) -> ScoreRule:
    value = _object(value, "rule")
    rule_type = RuleKind(_string(value.get("type"), "rule.type"))
    _exact_keys(value, RULE_FIELDS[rule_type], "rule")
    target = None
    points = 0
    odd_points = 0
    threshold = 0
    weights = {}
    requirements = {}
    if "target" in value:
        target = Character(mapping[_produce(value["target"], "rule.target")])
    if "points" in value:
        points = _integer(value["points"], "rule.points")
    if "odd_points" in value:
        odd_points = _integer(value["odd_points"], "rule.odd_points")
    if "threshold" in value:
        threshold = _integer(value["threshold"], "rule.threshold")
    if "weights" in value:
        weights = _decode_produce_values(value["weights"], mapping, "rule.weights")
        if not weights or any(weight == 0 for weight in weights.values()):
            raise ValueError("linear 权重必须为非零整数")
    if "requirements" in value:
        requirements = _decode_produce_values(
            value["requirements"], mapping, "rule.requirements"
        )
        if len(requirements) not in {2, 3} or set(requirements.values()) != {1}:
            raise ValueError("set 必须包含两种或三种各一张蔬菜")
    if rule_type is RuleKind.SAME_PAIR and threshold != 2:
        raise ValueError("same_pair 阈值必须为 2")
    if rule_type is RuleKind.SAME_TRIPLE and threshold != 3:
        raise ValueError("same_triple 阈值必须为 3")
    if rule_type is RuleKind.MISSING_TYPES and threshold != 0:
        raise ValueError("missing_types 阈值必须为 0")
    if rule_type is RuleKind.TYPES_AT_LEAST and threshold <= 0:
        raise ValueError("types_at_least 阈值必须为正整数")
    return ScoreRule(
        kind=rule_type,
        target=target,
        points=points,
        odd_points=odd_points,
        threshold=threshold,
        weights=weights,
        requirements=requirements,
    )


def _decode_produce_values(
    value: Any, mapping: dict[str, str], field_name: str
) -> dict[Character, int]:
    value = _object(value, field_name)
    return {
        Character(mapping[_produce(key, f"{field_name} 键")]): _integer(
            item, f"{field_name} 值"
        )
        for key, item in value.items()
    }


def _expected_cards() -> dict[str, tuple[str, str]]:
    expected = {}
    for group_index, (produce, prefix) in enumerate(PRODUCE_PREFIXES.items()):
        for number in range(1, 19):
            page = group_index * 2 + (number - 1) // 9 + 1
            position = (number - 1) % 9
            row = position // 3 + 1
            column = position % 3 + 1
            expected[f"{prefix}-{number:02d}"] = (
                produce,
                f"p{page}-r{row}c{column}",
            )
    return expected


def cards_per_character(player_count: int, speed: GameSpeed) -> int:
    if type(player_count) is not int or not 2 <= player_count <= 6:
        raise ValueError("仅支持 2–6 名玩家")
    if type(speed) is not GameSpeed:
        raise TypeError("speed 必须是游戏速度枚举")
    return player_count * (2 if speed is GameSpeed.QUICK else 3)


def build_decks(
    player_count: int,
    speed: GameSpeed,
    seed: int,
) -> tuple[dict[str, Card], list[list[str]], int]:
    count = cards_per_character(player_count, speed)
    if type(seed) is not int:
        raise TypeError("seed 必须是整数")
    generator = random.Random(seed)
    selected = []
    catalog = load_catalog()
    for character in Character:
        group = [card for card in catalog if card.character is character]
        selected.extend(generator.sample(group, count))
    generator.shuffle(selected)
    decks = [[], [], []]
    for index, card in enumerate(selected):
        decks[index % 3].append(card.card_id)
    cards = {card.card_id: card for card in selected}
    return cards, decks, generator.randrange(player_count)


def _reject_constant(value: str) -> None:
    raise ValueError(f"卡牌目录不允许非有限数值：{value}")


def _object(value: Any, field_name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise TypeError(f"{field_name} 必须是对象")
    return value


def _list(value: Any, field_name: str) -> list[Any]:
    if type(value) is not list:
        raise TypeError(f"{field_name} 必须是数组")
    return value


def _string(value: Any, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} 必须是字符串")
    return value


def _integer(value: Any, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} 必须是整数")
    return value


def _produce(value: Any, field_name: str) -> str:
    value = _string(value, field_name)
    if value not in PRODUCE_MAPPING:
        raise ValueError(f"{field_name} 不是官方蔬菜键")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], field_name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{field_name} 字段不匹配")
