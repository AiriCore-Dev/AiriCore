from __future__ import annotations

from .models import PersonalState, WorldState


_personal: dict[str, PersonalState] = {}
_world = WorldState()


def get_personal(user_id: str) -> PersonalState | None:
    return _personal.get(str(user_id))


def set_personal(state: PersonalState) -> PersonalState:
    _personal[state.user_id] = state
    return state


def all_personal() -> dict[str, PersonalState]:
    return _personal


def get_world() -> WorldState:
    return _world


def set_world(state: WorldState) -> WorldState:
    global _world
    _world = state
    return state


def clear_all() -> None:
    _personal.clear()
    global _world
    _world = WorldState()
