def choose_notification_bot(bots, configured_account):
    if not bots:
        return None
    normalized = {str(key): value for key, value in bots.items()}
    account = str(configured_account or "").strip()
    if account and account in normalized:
        return normalized[account]
    return normalized[sorted(normalized)[0]]


def get_notification_bot(fallback=None):
    import nonebot

    bots = nonebot.get_bots()
    configured = ""
    try:
        configured = getattr(nonebot.get_driver().config, "notification_bot_account", "") or ""
    except Exception:
        configured = ""
    return choose_notification_bot(bots, configured) or fallback
