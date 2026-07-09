import sys


_WEB_DEFAULTS = {
    "sekai_daily": dict,
    "sekai_started": dict,
    "sekai_activity": dict,
    "web_nick": str,
    "sekai_run": dict,
}


def _parent_module():
    parent_name = __package__.rsplit(".", 1)[0] if "." in __package__ else __package__
    return sys.modules.get(parent_name)


def get_data() -> dict:
    mod = _parent_module()
    if mod is None:
        return {}
    d = getattr(mod, "data", None)
    return d if isinstance(d, dict) else {}


def new_account() -> dict:
    mod = _parent_module()
    acc = mod.new_account() if mod and hasattr(mod, "new_account") else {"credits": 0}
    return _ensure_web_fields(acc)


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
