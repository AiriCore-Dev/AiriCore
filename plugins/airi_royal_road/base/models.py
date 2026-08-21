from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from .constants import SCHEMA_VERSION


def _keys(data: Any, expected: set[str]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TypeError("数据必须是对象")
    if set(data) != expected:
        raise ValueError("数据字段不匹配")
    return data


def _str(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("字段必须是字符串")
    return value


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("字段必须是整数")
    return value


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise TypeError("字段必须是布尔值")
    return value


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError("字段必须是列表")
    return list(value)


def _dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise TypeError("字段必须是字符串键对象")
    return dict(value)


def _string_list(value: Any) -> list[str]:
    result = _list(value)
    if any(not isinstance(item, str) for item in result):
        raise TypeError("列表元素必须是字符串")
    return result


@dataclass
class BondState:
    trust: int = 0
    candor: int = 0
    rapport: int = 0
    courage: int = 0

    FIELDS: ClassVar[set[str]] = {"trust", "candor", "rapport", "courage"}

    def to_dict(self) -> dict[str, Any]:
        return {"trust": self.trust, "candor": self.candor, "rapport": self.rapport, "courage": self.courage}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BondState":
        data = _keys(data, cls.FIELDS)
        values = [_int(data[key]) for key in ("trust", "candor", "rapport", "courage")]
        return cls(*values)


@dataclass
class InventoryState:
    durable_items: list[str] = field(default_factory=list)
    temporary_items: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    inheritance: str | None = None

    FIELDS: ClassVar[set[str]] = {"durable_items", "temporary_items", "skills", "inheritance"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "durable_items": list(self.durable_items),
            "temporary_items": list(self.temporary_items),
            "skills": list(self.skills),
            "inheritance": self.inheritance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InventoryState":
        data = _keys(data, cls.FIELDS)
        inheritance = data["inheritance"]
        if inheritance is not None:
            inheritance = _str(inheritance)
        return cls(_string_list(data["durable_items"]), _string_list(data["temporary_items"]), _string_list(data["skills"]), inheritance)


@dataclass
class CombatState:
    encounter_id: str = ""
    enemy_id: str = ""
    turn: int = 0
    player_hp: int = 0
    enemy_hp: int = 0
    statuses: list[str] = field(default_factory=list)
    pending_action: str | None = None
    resolved: bool = False
    result: dict[str, Any] = field(default_factory=dict)

    FIELDS: ClassVar[set[str]] = {"encounter_id", "enemy_id", "turn", "player_hp", "enemy_hp", "statuses", "pending_action", "resolved", "result"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "encounter_id": self.encounter_id,
            "enemy_id": self.enemy_id,
            "turn": self.turn,
            "player_hp": self.player_hp,
            "enemy_hp": self.enemy_hp,
            "statuses": list(self.statuses),
            "pending_action": self.pending_action,
            "resolved": self.resolved,
            "result": dict(self.result),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CombatState":
        data = _keys(data, cls.FIELDS)
        pending = data["pending_action"]
        if pending is not None:
            pending = _str(pending)
        return cls(_str(data["encounter_id"]), _str(data["enemy_id"]), _int(data["turn"]), _int(data["player_hp"]), _int(data["enemy_hp"]), _string_list(data["statuses"]), pending, _bool(data["resolved"]), _dict(data["result"]))


@dataclass
class WeeklyRun:
    week_index: int = 0
    location_id: str = "hope_carriage"
    fire: int = 3
    injuries: list[str] = field(default_factory=list)
    recalls_used: int = 0
    action_dates: list[str] = field(default_factory=list)
    temporary_items: list[str] = field(default_factory=list)
    blessings: list[str] = field(default_factory=list)

    FIELDS: ClassVar[set[str]] = {"week_index", "location_id", "fire", "injuries", "recalls_used", "action_dates", "temporary_items", "blessings"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "week_index": self.week_index,
            "location_id": self.location_id,
            "fire": self.fire,
            "injuries": list(self.injuries),
            "recalls_used": self.recalls_used,
            "action_dates": list(self.action_dates),
            "temporary_items": list(self.temporary_items),
            "blessings": list(self.blessings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeeklyRun":
        data = _keys(data, cls.FIELDS)
        return cls(_int(data["week_index"]), _str(data["location_id"]), _int(data["fire"]), _string_list(data["injuries"]), _int(data["recalls_used"]), _string_list(data["action_dates"]), _string_list(data["temporary_items"]), _string_list(data["blessings"]))


@dataclass
class VoteBox:
    week_index: int = 0
    eligible_users: list[str] = field(default_factory=list)
    choices: dict[str, str] = field(default_factory=dict)
    opened: bool = False
    closed: bool = False
    hope_priority: str = "hope"
    result: dict[str, Any] = field(default_factory=dict)

    FIELDS: ClassVar[set[str]] = {"week_index", "eligible_users", "choices", "opened", "closed", "hope_priority", "result"}

    def to_dict(self) -> dict[str, Any]:
        return {"week_index": self.week_index, "eligible_users": list(self.eligible_users), "choices": dict(self.choices), "opened": self.opened, "closed": self.closed, "hope_priority": self.hope_priority, "result": dict(self.result)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VoteBox":
        data = _keys(data, cls.FIELDS)
        return cls(_int(data["week_index"]), _string_list(data["eligible_users"]), _dict(data["choices"]), _bool(data["opened"]), _bool(data["closed"]), _str(data["hope_priority"]), _dict(data["result"]))


@dataclass
class SettlementRecord:
    user_id: str
    total_emblems: int = 0
    amount: int = 0
    status: str = "pending"
    settlement_id: str = ""
    created_at: str = ""

    FIELDS: ClassVar[set[str]] = {"user_id", "total_emblems", "amount", "status", "settlement_id", "created_at"}

    def to_dict(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "total_emblems": self.total_emblems, "amount": self.amount, "status": self.status, "settlement_id": self.settlement_id, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SettlementRecord":
        data = _keys(data, cls.FIELDS)
        return cls(_str(data["user_id"]), _int(data["total_emblems"]), _int(data["amount"]), _str(data["status"]), _str(data["settlement_id"]), _str(data["created_at"]))


@dataclass
class PersonalState:
    user_id: str
    schema_version: int = SCHEMA_VERSION
    job: str | None = None
    bonds: dict[str, BondState] = field(default_factory=dict)
    inventory: InventoryState = field(default_factory=InventoryState)
    weekly: WeeklyRun = field(default_factory=WeeklyRun)
    combat: CombatState | None = None
    current_emblems: int = 0
    total_emblems: int = 0
    event_ids: list[str] = field(default_factory=list)
    last_render_key: str | None = None
    settlement_status: str = "unsettled"

    FIELDS: ClassVar[set[str]] = {"user_id", "schema_version", "job", "bonds", "inventory", "weekly", "combat", "current_emblems", "total_emblems", "event_ids", "last_render_key", "settlement_status"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "schema_version": self.schema_version,
            "job": self.job,
            "bonds": {key: value.to_dict() for key, value in self.bonds.items()},
            "inventory": self.inventory.to_dict(),
            "weekly": self.weekly.to_dict(),
            "combat": self.combat.to_dict() if self.combat else None,
            "current_emblems": self.current_emblems,
            "total_emblems": self.total_emblems,
            "event_ids": list(self.event_ids),
            "last_render_key": self.last_render_key,
            "settlement_status": self.settlement_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonalState":
        data = _keys(data, cls.FIELDS)
        job = data["job"]
        if job is not None:
            job = _str(job)
        bonds = _dict(data["bonds"])
        parsed_bonds = {key: BondState.from_dict(value) for key, value in bonds.items()}
        combat = data["combat"]
        if combat is not None:
            combat = CombatState.from_dict(combat)
        return cls(_str(data["user_id"]), _int(data["schema_version"]), job, parsed_bonds, InventoryState.from_dict(data["inventory"]), WeeklyRun.from_dict(data["weekly"]), combat, _int(data["current_emblems"]), _int(data["total_emblems"]), _string_list(data["event_ids"]), data["last_render_key"] if data["last_render_key"] is None else _str(data["last_render_key"]), _str(data["settlement_status"]))


@dataclass
class WorldState:
    schema_version: int = SCHEMA_VERSION
    map_overlays: dict[str, str] = field(default_factory=dict)
    votes: dict[str, VoteBox] = field(default_factory=dict)
    completed_events: list[str] = field(default_factory=list)
    week_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    event_ids: list[str] = field(default_factory=list)
    frozen: bool = False

    FIELDS: ClassVar[set[str]] = {"schema_version", "map_overlays", "votes", "completed_events", "week_results", "event_ids", "frozen"}

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "map_overlays": dict(self.map_overlays), "votes": {key: value.to_dict() for key, value in self.votes.items()}, "completed_events": list(self.completed_events), "week_results": {key: dict(value) for key, value in self.week_results.items()}, "event_ids": list(self.event_ids), "frozen": self.frozen}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldState":
        data = _keys(data, cls.FIELDS)
        votes = _dict(data["votes"])
        return cls(_int(data["schema_version"]), _dict(data["map_overlays"]), {key: VoteBox.from_dict(value) for key, value in votes.items()}, _string_list(data["completed_events"]), _dict(data["week_results"]), _string_list(data["event_ids"]), _bool(data["frozen"]))
