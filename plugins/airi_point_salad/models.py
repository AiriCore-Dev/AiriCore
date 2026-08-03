from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any


class Character(str, Enum):
    MINORI = "minori"
    HARUKA = "haruka"
    AIRI = "airi"
    SHIZUKU = "shizuku"
    MIKU = "miku"
    RIN = "rin"

    @property
    def display_name(self) -> str:
        return {
            Character.MINORI: "花里实乃理",
            Character.HARUKA: "桐谷遥",
            Character.AIRI: "桃井爱莉",
            Character.SHIZUKU: "日野森雫",
            Character.MIKU: "初音未来",
            Character.RIN: "镜音铃",
        }[self]

    @property
    def short_name(self) -> str:
        return {
            Character.MINORI: "实乃理",
            Character.HARUKA: "遥",
            Character.AIRI: "爱莉",
            Character.SHIZUKU: "雫",
            Character.MIKU: "未来",
            Character.RIN: "铃",
        }[self]


class GameSpeed(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"


class GameMode(str, Enum):
    CLASSIC = "classic"
    MIX = "mix"


class Phase(str, Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    FINISHED = "finished"


class Face(str, Enum):
    SCORE = "score"
    CHARACTER = "character"


class RuleKind(str, Enum):
    MOST = "most"
    FEWEST = "fewest"
    PARITY = "parity"
    LINEAR = "linear"
    SAME_PAIR = "same_pair"
    SAME_TRIPLE = "same_triple"
    SET = "set"
    MISSING_TYPES = "missing_types"
    TYPES_AT_LEAST = "types_at_least"
    FEWEST_TOTAL = "fewest_total"
    MOST_TOTAL = "most_total"
    COMPLETE_SET = "complete_set"


@dataclass(slots=True)
class ScoreRule:
    kind: RuleKind
    target: Character | None = None
    points: int = 0
    odd_points: int = 0
    threshold: int = 0
    weights: dict[Character, int] = field(default_factory=dict)
    requirements: dict[Character, int] = field(default_factory=dict)


@dataclass(slots=True)
class Card:
    card_id: str
    character: Character
    rule: ScoreRule
    produce: str
    source: str


@dataclass(slots=True)
class PlayerState:
    user_id: str
    name: str
    score_cards: list[str] = field(default_factory=list)
    character_cards: list[str] = field(default_factory=list)
    center: Character | None = None
    skill_used: bool = False
    mission_ids: list[str] = field(default_factory=list)
    mission_points: int = 0
    skill_payload: dict[str, Any] = field(default_factory=dict)
    last_action_turn: int = -1


@dataclass(slots=True)
class GameState:
    group_id: str
    host_id: str
    speed: GameSpeed
    mode: GameMode
    phase: Phase = Phase.LOBBY
    players: list[PlayerState] = field(default_factory=list)
    cards: dict[str, Card] = field(default_factory=dict)
    decks: list[list[str]] = field(default_factory=lambda: [[], [], []])
    character_market: list[list[str | None]] = field(
        default_factory=lambda: [[None, None] for _ in range(3)]
    )
    current_player: int = 0
    starting_player: int = 0
    turn_number: int = 0
    turn_flips: int = 0
    post_flip_user_id: str | None = None
    post_flip_available: bool = False
    centers: list[Character] = field(default_factory=list)
    mission_deck: list[str] = field(default_factory=list)
    active_missions: list[str] = field(default_factory=list)
    pending_skill: dict[str, Any] = field(default_factory=dict)
    player_swap_request: dict[str, str] = field(default_factory=dict)
    turn_start_user_id: str | None = None
    turn_start_score_cards: list[str] = field(default_factory=list)
    turn_start_character_cards: list[str] = field(default_factory=list)
    last_turn_user_id: str | None = None
    last_turn_score_cards_before: list[str] = field(default_factory=list)
    last_turn_character_cards_before: list[str] = field(default_factory=list)
    seed: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "host_id": self.host_id,
            "speed": self.speed.value,
            "mode": self.mode.value,
            "phase": self.phase.value,
            "players": [_player_to_dict(player) for player in self.players],
            "cards": {
                card_id: _card_to_dict(card) for card_id, card in self.cards.items()
            },
            "decks": [list(deck) for deck in self.decks],
            "character_market": [list(row) for row in self.character_market],
            "current_player": self.current_player,
            "starting_player": self.starting_player,
            "turn_number": self.turn_number,
            "turn_flips": self.turn_flips,
            "post_flip_user_id": self.post_flip_user_id,
            "post_flip_available": self.post_flip_available,
            "centers": [character.value for character in self.centers],
            "mission_deck": list(self.mission_deck),
            "active_missions": list(self.active_missions),
            "pending_skill": _json_value(self.pending_skill),
            "player_swap_request": _json_value(self.player_swap_request),
            "turn_start_user_id": self.turn_start_user_id,
            "turn_start_score_cards": list(self.turn_start_score_cards),
            "turn_start_character_cards": list(self.turn_start_character_cards),
            "last_turn_user_id": self.last_turn_user_id,
            "last_turn_score_cards_before": list(
                self.last_turn_score_cards_before
            ),
            "last_turn_character_cards_before": list(
                self.last_turn_character_cards_before
            ),
            "seed": self.seed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        data = _object(data, "游戏状态")
        players = _list(data.get("players", []), "players")
        cards = _object(data.get("cards", {}), "cards")
        decks = _list(data.get("decks", [[], [], []]), "decks")
        if len(decks) != 3:
            raise ValueError("decks 必须恰好包含三列")
        character_market = _list(
            data.get("character_market", [[None, None] for _ in range(3)]),
            "character_market",
        )
        if len(character_market) != 3 or any(
            len(_list(row, "character_market 行")) != 2
            for row in character_market
        ):
            raise ValueError("character_market 必须是三行两列")
        centers = _list(data.get("centers", []), "centers")
        mission_deck = _list(data.get("mission_deck", []), "mission_deck")
        active_missions = _list(data.get("active_missions", []), "active_missions")
        player_swap_request = _plain_dict(data.get("player_swap_request", {}))
        if set(player_swap_request) - {"from_user_id", "to_user_id"}:
            raise ValueError("player_swap_request 字段不匹配")
        if player_swap_request and set(player_swap_request) != {"from_user_id", "to_user_id"}:
            raise ValueError("player_swap_request 字段不匹配")
        if player_swap_request:
            player_swap_request = {
                key: _string(value, f"player_swap_request.{key}")
                for key, value in player_swap_request.items()
            }
        turn_start_score_cards = _list(
            data.get("turn_start_score_cards", []),
            "turn_start_score_cards",
        )
        turn_start_character_cards = _list(
            data.get("turn_start_character_cards", []),
            "turn_start_character_cards",
        )
        last_turn_score_cards_before = _list(
            data.get("last_turn_score_cards_before", []),
            "last_turn_score_cards_before",
        )
        last_turn_character_cards_before = _list(
            data.get("last_turn_character_cards_before", []),
            "last_turn_character_cards_before",
        )
        return cls(
            group_id=_string(data["group_id"], "group_id"),
            host_id=_string(data["host_id"], "host_id"),
            speed=GameSpeed(_string(data["speed"], "speed")),
            mode=GameMode(_string(data["mode"], "mode")),
            phase=Phase(_string(data.get("phase", Phase.LOBBY.value), "phase")),
            players=[_player_from_dict(player) for player in players],
            cards={
                _string(card_id, "cards 键"): _card_from_dict(card)
                for card_id, card in cards.items()
            },
            decks=[
                _string_list(_list(deck, "decks 列"), "decks 列")
                for deck in decks
            ],
            character_market=[
                [
                    None
                    if card_id is None
                    else _string(card_id, "character_market 元素")
                    for card_id in _list(row, "character_market 行")
                ]
                for row in character_market
            ],
            current_player=_integer(data.get("current_player", 0), "current_player"),
            starting_player=_integer(
                data.get("starting_player", 0), "starting_player"
            ),
            turn_number=_integer(data.get("turn_number", 0), "turn_number"),
            turn_flips=_integer(data.get("turn_flips", 0), "turn_flips"),
            post_flip_user_id=(
                None
                if data.get("post_flip_user_id") is None
                else _string(data["post_flip_user_id"], "post_flip_user_id")
            ),
            post_flip_available=_boolean(
                data.get("post_flip_available", False), "post_flip_available"
            ),
            centers=[
                Character(_string(character, "centers 元素")) for character in centers
            ],
            mission_deck=_string_list(mission_deck, "mission_deck"),
            active_missions=_string_list(active_missions, "active_missions"),
            pending_skill=_plain_dict(data.get("pending_skill", {})),
            player_swap_request=player_swap_request,
            turn_start_user_id=(
                None
                if data.get("turn_start_user_id") is None
                else _string(data["turn_start_user_id"], "turn_start_user_id")
            ),
            turn_start_score_cards=_string_list(
                turn_start_score_cards,
                "turn_start_score_cards",
            ),
            turn_start_character_cards=_string_list(
                turn_start_character_cards,
                "turn_start_character_cards",
            ),
            last_turn_user_id=(
                None
                if data.get("last_turn_user_id") is None
                else _string(data["last_turn_user_id"], "last_turn_user_id")
            ),
            last_turn_score_cards_before=_string_list(
                last_turn_score_cards_before,
                "last_turn_score_cards_before",
            ),
            last_turn_character_cards_before=_string_list(
                last_turn_character_cards_before,
                "last_turn_character_cards_before",
            ),
            seed=_integer(data.get("seed", 0), "seed"),
            created_at=_number(data.get("created_at", 0.0), "created_at"),
            updated_at=_number(data.get("updated_at", 0.0), "updated_at"),
        )


def _rule_to_dict(rule: ScoreRule) -> dict[str, Any]:
    return {
        "kind": _rule_kind(rule.kind, "rule.kind").value,
        "target": (
            None
            if rule.target is None
            else _character(rule.target, "rule.target").value
        ),
        "points": _integer(rule.points, "rule.points"),
        "odd_points": _integer(rule.odd_points, "rule.odd_points"),
        "threshold": _integer(rule.threshold, "rule.threshold"),
        "weights": _character_integer_dict(rule.weights, "rule.weights"),
        "requirements": _character_integer_dict(
            rule.requirements, "rule.requirements"
        ),
    }


def _rule_from_dict(data: dict[str, Any]) -> ScoreRule:
    data = _object(data, "rule")
    _exact_keys(
        data,
        {
            "kind",
            "target",
            "points",
            "odd_points",
            "threshold",
            "weights",
            "requirements",
        },
        "rule",
    )
    target = data["target"]
    return ScoreRule(
        kind=RuleKind(_string(data["kind"], "rule.kind")),
        target=(
            None
            if target is None
            else Character(_string(target, "rule.target"))
        ),
        points=_integer(data["points"], "rule.points"),
        odd_points=_integer(data["odd_points"], "rule.odd_points"),
        threshold=_integer(data["threshold"], "rule.threshold"),
        weights=_character_integer_dict_from_dict(data["weights"], "rule.weights"),
        requirements=_character_integer_dict_from_dict(
            data["requirements"], "rule.requirements"
        ),
    )


def _card_to_dict(card: Card) -> dict[str, Any]:
    return {
        "card_id": _string(card.card_id, "card.card_id"),
        "character": _character(card.character, "card.character").value,
        "rule": _rule_to_dict(card.rule),
        "produce": _string(card.produce, "card.produce"),
        "source": _string(card.source, "card.source"),
    }


def _card_from_dict(data: dict[str, Any]) -> Card:
    data = _object(data, "card")
    _exact_keys(data, {"card_id", "character", "rule", "produce", "source"}, "card")
    return Card(
        card_id=_string(data["card_id"], "card.card_id"),
        character=Character(_string(data["character"], "card.character")),
        rule=_rule_from_dict(data["rule"]),
        produce=_string(data["produce"], "card.produce"),
        source=_string(data["source"], "card.source"),
    )


def _player_to_dict(player: PlayerState) -> dict[str, Any]:
    return {
        "user_id": player.user_id,
        "name": player.name,
        "score_cards": list(player.score_cards),
        "character_cards": list(player.character_cards),
        "center": None if player.center is None else player.center.value,
        "skill_used": player.skill_used,
        "mission_ids": list(player.mission_ids),
        "mission_points": player.mission_points,
        "skill_payload": _json_value(player.skill_payload),
        "last_action_turn": _integer(
            player.last_action_turn, "player.last_action_turn"
        ),
    }


def _player_from_dict(data: dict[str, Any]) -> PlayerState:
    data = _object(data, "player")
    center = data.get("center")
    score_cards = _list(data.get("score_cards", []), "player.score_cards")
    character_cards = _list(data.get("character_cards", []), "player.character_cards")
    mission_ids = _list(data.get("mission_ids", []), "player.mission_ids")
    return PlayerState(
        user_id=_string(data["user_id"], "player.user_id"),
        name=_string(data["name"], "player.name"),
        score_cards=_string_list(score_cards, "player.score_cards"),
        character_cards=_string_list(character_cards, "player.character_cards"),
        center=(
            None if center is None else Character(_string(center, "player.center"))
        ),
        skill_used=_boolean(data.get("skill_used", False), "player.skill_used"),
        mission_ids=_string_list(mission_ids, "player.mission_ids"),
        mission_points=_integer(data.get("mission_points", 0), "player.mission_points"),
        skill_payload=_plain_dict(data.get("skill_payload", {})),
        last_action_turn=_integer(
            data.get("last_action_turn", -1), "player.last_action_turn"
        ),
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, dict):
        return {
            _string(key, "JSON 对象键"): _json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("JSON 数值必须是有限值")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"不支持序列化的数据类型：{type(value).__name__}")


def _plain_dict(value: Any) -> dict[str, Any]:
    value = _object(value, "字典字段")
    return {
        _string(key, "JSON 对象键"): _plain_value(item) for key, item in value.items()
    }


def _plain_value(value: Any) -> Any:
    if type(value) is dict:
        return {
            _string(key, "JSON 对象键"): _plain_value(item)
            for key, item in value.items()
        }
    if type(value) is list:
        return [_plain_value(item) for item in value]
    if type(value) is float and not isfinite(value):
        raise ValueError("JSON 数值必须是有限值")
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError(f"不支持反序列化的数据类型：{type(value).__name__}")


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


def _number(value: Any, field_name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{field_name} 必须是数值")
    if not isfinite(value):
        raise ValueError(f"{field_name} 必须是有限值")
    return float(value)


def _boolean(value: Any, field_name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field_name} 必须是布尔值")
    return value


def _string_list(value: list[Any], field_name: str) -> list[str]:
    return [_string(item, f"{field_name} 元素") for item in value]


def _exact_keys(
    value: dict[str, Any], expected: set[str], field_name: str
) -> None:
    if set(value) != expected:
        raise ValueError(f"{field_name} 字段不匹配")


def _character(value: Any, field_name: str) -> Character:
    if type(value) is not Character:
        raise TypeError(f"{field_name} 必须是角色枚举")
    return value


def _rule_kind(value: Any, field_name: str) -> RuleKind:
    if type(value) is not RuleKind:
        raise TypeError(f"{field_name} 必须是规则枚举")
    return value


def _character_integer_dict(
    value: Any, field_name: str
) -> dict[str, int]:
    value = _object(value, field_name)
    return {
        _character(key, f"{field_name} 键").value: _integer(
            item, f"{field_name} 值"
        )
        for key, item in value.items()
    }


def _character_integer_dict_from_dict(
    value: Any, field_name: str
) -> dict[Character, int]:
    value = _object(value, field_name)
    return {
        Character(_string(key, f"{field_name} 键")): _integer(
            item, f"{field_name} 值"
        )
        for key, item in value.items()
    }
