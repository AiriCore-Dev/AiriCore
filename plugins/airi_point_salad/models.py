from dataclasses import dataclass, field
from enum import Enum
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
    EACH = "each"
    PAIR = "pair"
    SET = "set"
    COMPARE = "compare"
    RISK = "risk"


@dataclass(slots=True)
class ScoreRule:
    kind: RuleKind
    characters: list[Character]
    points: int
    penalty: int = 0
    relation: str = ""


@dataclass(slots=True)
class Card:
    card_id: str
    character: Character
    rule: ScoreRule


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


@dataclass(slots=True)
class GameState:
    group_id: str
    host_id: str
    speed: GameSpeed
    mode: GameMode
    phase: Phase = Phase.LOBBY
    players: list[PlayerState] = field(default_factory=list)
    cards: dict[str, Card] = field(default_factory=dict)
    deck: list[str] = field(default_factory=list)
    score_market: list[str | None] = field(
        default_factory=lambda: [None, None, None]
    )
    character_market: list[list[str | None]] = field(
        default_factory=lambda: [[None, None] for _ in range(3)]
    )
    current_player: int = 0
    turn_number: int = 0
    turn_flips: int = 0
    centers: list[Character] = field(default_factory=list)
    mission_deck: list[str] = field(default_factory=list)
    active_missions: list[str] = field(default_factory=list)
    pending_skill: dict[str, Any] = field(default_factory=dict)
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
            "deck": list(self.deck),
            "score_market": list(self.score_market),
            "character_market": [list(row) for row in self.character_market],
            "current_player": self.current_player,
            "turn_number": self.turn_number,
            "turn_flips": self.turn_flips,
            "centers": [character.value for character in self.centers],
            "mission_deck": list(self.mission_deck),
            "active_missions": list(self.active_missions),
            "pending_skill": _json_value(self.pending_skill),
            "seed": self.seed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        return cls(
            group_id=str(data["group_id"]),
            host_id=str(data["host_id"]),
            speed=GameSpeed(data["speed"]),
            mode=GameMode(data["mode"]),
            phase=Phase(data.get("phase", Phase.LOBBY.value)),
            players=[_player_from_dict(player) for player in data.get("players", [])],
            cards={
                str(card_id): _card_from_dict(card)
                for card_id, card in data.get("cards", {}).items()
            },
            deck=[str(card_id) for card_id in data.get("deck", [])],
            score_market=[
                None if card_id is None else str(card_id)
                for card_id in data.get("score_market", [None, None, None])
            ],
            character_market=[
                [None if card_id is None else str(card_id) for card_id in row]
                for row in data.get(
                    "character_market", [[None, None] for _ in range(3)]
                )
            ],
            current_player=int(data.get("current_player", 0)),
            turn_number=int(data.get("turn_number", 0)),
            turn_flips=int(data.get("turn_flips", 0)),
            centers=[Character(character) for character in data.get("centers", [])],
            mission_deck=[str(mission_id) for mission_id in data.get("mission_deck", [])],
            active_missions=[
                str(mission_id) for mission_id in data.get("active_missions", [])
            ],
            pending_skill=_plain_dict(data.get("pending_skill", {})) or {},
            seed=int(data.get("seed", 0)),
            created_at=float(data.get("created_at", 0.0)),
            updated_at=float(data.get("updated_at", 0.0)),
        )


def _rule_to_dict(rule: ScoreRule) -> dict[str, Any]:
    return {
        "kind": rule.kind.value,
        "characters": [character.value for character in rule.characters],
        "points": rule.points,
        "penalty": rule.penalty,
        "relation": rule.relation,
    }


def _rule_from_dict(data: dict[str, Any]) -> ScoreRule:
    return ScoreRule(
        kind=RuleKind(data["kind"]),
        characters=[Character(character) for character in data.get("characters", [])],
        points=int(data["points"]),
        penalty=int(data.get("penalty", 0)),
        relation=str(data.get("relation", "")),
    )


def _card_to_dict(card: Card) -> dict[str, Any]:
    return {
        "card_id": card.card_id,
        "character": card.character.value,
        "rule": _rule_to_dict(card.rule),
    }


def _card_from_dict(data: dict[str, Any]) -> Card:
    return Card(
        card_id=str(data["card_id"]),
        character=Character(data["character"]),
        rule=_rule_from_dict(data["rule"]),
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
    }


def _player_from_dict(data: dict[str, Any]) -> PlayerState:
    center = data.get("center")
    return PlayerState(
        user_id=str(data["user_id"]),
        name=str(data["name"]),
        score_cards=[str(card_id) for card_id in data.get("score_cards", [])],
        character_cards=[
            str(card_id) for card_id in data.get("character_cards", [])
        ],
        center=None if center is None else Character(center),
        skill_used=bool(data.get("skill_used", False)),
        mission_ids=[str(mission_id) for mission_id in data.get("mission_ids", [])],
        mission_points=int(data.get("mission_points", 0)),
        skill_payload=_plain_dict(data.get("skill_payload", {})) or {},
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"不支持序列化的数据类型：{type(value).__name__}")


def _plain_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("字典字段必须是对象")
    return {str(key): _plain_value(item) for key, item in value.items()}


def _plain_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"不支持反序列化的数据类型：{type(value).__name__}")
