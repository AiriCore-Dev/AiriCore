"""Safe accessors for the parent plugin's in-memory `data` dict.

The parent module (``server/__init__.py``) rebinds its module-level ``data``
object on startup / load (see ``load_json``), so we must never cache a direct
reference to the dict — we always look it up on the parent module at call time.

We also lazily backfill the web-only account fields so old pickles keep working
without touching the parent's ``new_account()``.
"""

import sys


# Account fields this subsystem adds on top of the parent's new_account().
#   sekai_daily   : {date_str: best_score}  — 每日SEKAI排行榜分数
#   sekai_started : {date_str: count}       — 当日已用掉的每日资格次数（上限见 api.SEKAI_DAILY_LIMIT）
#   sekai_activity: {activity_id: best_score} — 各限时活动的历史最高分（按活动分别排行）
#   web_nick      : str                     — 最近一次绑定/登录时缓存的QQ昵称
#   sekai_run     : {rev:int, run:dict|None} — 进行中的对局存档（跨设备同步）
_WEB_DEFAULTS = {
    "sekai_daily": dict,
    "sekai_started": dict,
    "sekai_activity": dict,
    "web_nick": str,
    "sekai_run": dict,
}


def _parent_module():
    """Return the parent package module (server) that owns `data`."""
    parent_name = __package__.rsplit(".", 1)[0] if "." in __package__ else __package__
    # __package__ is e.g. "server.roguelike"; parent is "server".
    return sys.modules.get(parent_name)


def get_data() -> dict:
    """Return the live `data` dict from the parent module (never a stale ref)."""
    mod = _parent_module()
    if mod is None:
        return {}
    d = getattr(mod, "data", None)
    return d if isinstance(d, dict) else {}


def new_account() -> dict:
    """Delegate to the parent's new_account() so records stay schema-compatible."""
    mod = _parent_module()
    acc = mod.new_account() if mod and hasattr(mod, "new_account") else {"credits": 0}
    return _ensure_web_fields(acc)


def _ensure_web_fields(acc: dict) -> dict:
    for key, factory in _WEB_DEFAULTS.items():
        if key not in acc:
            acc[key] = factory()
    return acc


def get_account(user_id: str):
    """Return the (web-field-backfilled) account, or None if not registered."""
    data = get_data()
    acc = data.get(user_id)
    if acc is None:
        return None
    return _ensure_web_fields(acc)


def ensure_account(user_id: str) -> dict:
    """Return the account for user_id, creating a fresh one if missing."""
    data = get_data()
    if user_id not in data:
        data[user_id] = new_account()
    return _ensure_web_fields(data[user_id])


def is_registered(user_id: str) -> bool:
    return user_id in get_data()
