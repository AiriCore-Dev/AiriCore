from collections.abc import Mapping


def normalize_bot_whitelist(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def select_whitelisted_bots(bots: Mapping, whitelist) -> dict:
    allowed = set(normalize_bot_whitelist(whitelist))
    normalized = {str(key): bot for key, bot in bots.items()}
    if not allowed:
        return normalized
    return {key: bot for key, bot in normalized.items() if key in allowed}


def normalize_action(action: str, params: dict) -> tuple[str, dict]:
    action = str(action or "").strip()
    payload = dict(params or {})
    payload.pop("message_type", None)
    payload.pop("self_id", None)
    payload.pop("sender_id", None)
    payload.pop("operator_id", None)
    if action == "send_msg":
        if payload.get("group_id") is not None:
            action = "send_group_msg"
        elif payload.get("user_id") is not None:
            action = "send_private_msg"
    if action in {"send_group_msg", "send_group_forward_msg"}:
        payload.pop("user_id", None)
    if action in {"send_private_msg", "send_private_forward_msg"}:
        payload.pop("group_id", None)
    return action, payload
