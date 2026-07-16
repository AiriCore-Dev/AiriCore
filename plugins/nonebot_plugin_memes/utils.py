from datetime import datetime, timezone


def remove_timezone(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


def add_timezone(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone()
    return dt.replace(tzinfo=timezone.utc).astimezone()
