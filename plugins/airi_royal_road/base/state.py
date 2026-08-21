from __future__ import annotations

from .models import PersonalState, WorldState


_personal: dict[str, PersonalState] = {}
_world = WorldState()


def get_personal(user_id: str) -> PersonalState | None:
    return _personal.get(str(user_id))


def set_personal(state: PersonalState) -> PersonalState:
    current = _personal.get(state.user_id)
    if current is None:
        _personal[state.user_id] = state
        return state
    current.__dict__.clear()
    current.__dict__.update(state.__dict__)
    return current


def all_personal() -> dict[str, PersonalState]:
    return _personal


def get_world() -> WorldState:
    return _world


def set_world(state: WorldState) -> WorldState:
    _world.__dict__.clear()
    _world.__dict__.update(state.__dict__)
    return _world


def clear_all() -> None:
    _personal.clear()
    _world.__dict__.clear()
    _world.__dict__.update(WorldState().__dict__)
