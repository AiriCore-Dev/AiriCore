from __future__ import annotations

from dataclasses import dataclass

from ..base.models import PersonalState, WorldState
from ..content.map_data import LOCATIONS
from .calendar import CalendarContext
from .rng import seed_for, stream


@dataclass(frozen=True)
class Route:
    location_id: str
    terrain: str
    risk: int
    resources: tuple[str, ...]
    visible: bool


@dataclass(frozen=True)
class Encounter:
    location_id: str
    encounter_id: str
    choices: tuple[str, ...]
    reward_candidates: tuple[int, ...]


def visible_routes(personal: PersonalState, world: WorldState, date_context: CalendarContext) -> tuple[Route, ...]:
    current = personal.weekly.location_id
    candidates = LOCATIONS.get(current, {}).get("neighbors", ())
    result = []
    for location_id in candidates:
        record = LOCATIONS[location_id]
        unlocked = all(item in personal.event_ids or item in world.completed_events for item in record.get("unlock", ()))
        overlay = world.map_overlays.get(location_id) or world.map_overlays.get(f"week_{date_context.week_index}")
        if unlocked:
            result.append(Route(location_id, record["terrain"], record["risk"] + (1 if overlay else 0), (record["resources"],), True))
    return tuple(result)


def enter_location(personal: PersonalState, world: WorldState, date_context: CalendarContext, location_id: str) -> Encounter:
    routes = {route.location_id for route in visible_routes(personal, world, date_context)}
    if location_id not in routes:
        raise ValueError("该地点当前不可前往")
    if location_id not in personal.event_ids:
        personal.event_ids.append(location_id)
    personal.weekly.location_id = location_id
    seed = seed_for("encounter", personal.weekly.week_index, personal.user_id, location_id)
    random = stream(seed, date_context.current_date.isoformat())
    encounter_id = f"{location_id}:{random.randrange(100000):05d}"
    encounter = Encounter(location_id, encounter_id, ("探索", "谨慎前进", "返回希望号"), (100 + random.randrange(151),))
    personal.weekly.encounter = {
        "location_id": encounter.location_id,
        "encounter_id": encounter.encounter_id,
        "choices": list(encounter.choices),
        "reward_candidates": list(encounter.reward_candidates),
    }
    return encounter
