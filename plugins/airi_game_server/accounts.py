from plugins.airi_daily_check.base import state
from plugins.airi_daily_check.base.constants import new_account as daily_new_account


_WEB_DEFAULTS = {
    "sekai_daily": dict,
    "sekai_started": dict,
    "sekai_activity": dict,
    "web_nick": str,
    "sekai_run": dict,
}


def get_data() -> dict:
    return state.data if isinstance(state.data, dict) else {}


def new_account() -> dict:
    return _ensure_web_fields(daily_new_account())


def _ensure_web_fields(acc: dict) -> dict:
    for key, factory in _WEB_DEFAULTS.items():
        if key not in acc:
            acc[key] = factory()
    return acc


def get_account(user_id: str):
    data = get_data()
    acc = data.get(user_id)
    if acc is None:
        return None
    return _ensure_web_fields(acc)


def ensure_account(user_id: str) -> dict:
    data = get_data()
    if user_id not in data:
        data[user_id] = new_account()
    return _ensure_web_fields(data[user_id])


def is_registered(user_id: str) -> bool:
    return user_id in get_data()
