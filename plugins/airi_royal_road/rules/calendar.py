from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..base.constants import ACTIVITY_END, ACTIVITY_START, ACTIVITY_TZ, TOTAL_DAYS


@dataclass(frozen=True)
class CalendarContext:
    current_date: date
    activity_day: int | None
    week_index: int | None
    weekday: int
    act_id: str
    holiday_ids: tuple[str, ...]
    solar_term_ids: tuple[str, ...]
    weather_key: str
    can_start: bool
    is_frozen: bool


_holidays = {
    date(2026, 9, 21): ("中秋",),
    date(2026, 10, 31): ("万圣夜",),
    date(2026, 12, 25): ("圣诞节",),
    date(2026, 12, 31): ("跨年守夜",),
    date(2027, 1, 1): ("元旦",),
}
_solar_terms = {
    date(2026, 9, 23): ("秋分",),
    date(2026, 11, 7): ("立冬",),
    date(2026, 11, 22): ("小雪",),
    date(2027, 1, 5): ("小寒",),
    date(2027, 1, 20): ("大寒",),
}


def _act(day: int) -> str:
    if day <= 35:
        return "act_1"
    if day <= 62:
        return "act_2"
    if day <= 97:
        return "act_3"
    if day <= 125:
        return "act_4"
    return "act_5"


def calendar_context(value: datetime | date) -> CalendarContext:
    if isinstance(value, datetime):
        current = value.astimezone(ACTIVITY_TZ).date() if value.tzinfo else value.replace(tzinfo=ACTIVITY_TZ).date()
    else:
        current = value
    offset = (current - ACTIVITY_START.date()).days
    in_range = 0 <= offset < TOTAL_DAYS
    day = offset + 1 if in_range else None
    week = offset // 7 if in_range else None
    return CalendarContext(
        current,
        day,
        week,
        current.weekday(),
        _act(day) if day else "outside",
        _holidays.get(current, ()),
        _solar_terms.get(current, ()),
        ("autumn" if current.month in (9, 10, 11) else "winter" if current.month in (12, 1, 2) else "summer"),
        in_range,
        current > ACTIVITY_END.date(),
    )


def date_for_activity_day(activity_day: int) -> date:
    if not 1 <= activity_day <= TOTAL_DAYS:
        raise ValueError("活动日必须在 1 至 154 之间")
    return ACTIVITY_START.date() + timedelta(days=activity_day - 1)
