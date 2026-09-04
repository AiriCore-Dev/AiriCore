import calendar
import re
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple

from utils import llm
SOURCE_ORDER = ("对话", "对话机制", "海龟汤", "水表", "心愿瓶审核", "RCON翻译")

USAGE_TEXT = "用法：airillmquery [N|YYYY-MM-DD|YYYY-MM|YYYY]"
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_RE = re.compile(r"^\d{4}$")


def parse_scope(
    raw: str,
    today: Optional[date] = None,
) -> Tuple[date, date, str]:
    current = today or datetime.now(llm.UTC_PLUS_8).date()
    text = str(raw or "").strip()
    try:
        if not text:
            return current, current, current.isoformat()
        if _DAY_RE.fullmatch(text):
            day = date.fromisoformat(text)
            return day, day, day.isoformat()
        month_match = _MONTH_RE.fullmatch(text)
        if month_match:
            year, month = map(int, month_match.groups())
            last = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, last), text
        if _YEAR_RE.fullmatch(text):
            year = int(text)
            return date(year, 1, 1), date(year, 12, 31), text
        if text.isdigit():
            days = int(text)
            if days <= 0:
                raise ValueError
            start = current - timedelta(days=days - 1)
            return start, current, f"{start.isoformat()} 至 {current.isoformat()}"
    except (OverflowError, ValueError):
        raise ValueError(USAGE_TEXT)
    raise ValueError(USAGE_TEXT)


def render_query(
    raw: str,
    stats: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None,
    today: Optional[date] = None,
) -> str:
    start, end, label = parse_scope(raw, today)
    snapshot = llm.get_usage_snapshot() if stats is None else stats
    aggregate: Dict[str, Dict[str, int]] = {}
    start_key = start.isoformat()
    end_key = end.isoformat()
    for day, sources in snapshot.items():
        if not start_key <= day <= end_key:
            continue
        for source, models in sources.items():
            if source not in SOURCE_ORDER:
                continue
            target = aggregate.setdefault(source, {})
            for model, count in models.items():
                target[model] = target.get(model, 0) + int(count)
    total = sum(sum(models.values()) for models in aggregate.values())
    lines = [f"LLM 调用统计（{label}）"]
    if total <= 0:
        lines.append("暂无成功调用记录。")
        return "\n".join(lines)
    lines.append(f"成功调用：{total} 次")
    for source in SOURCE_ORDER:
        models = aggregate.get(source)
        if not models:
            continue
        source_total = sum(models.values())
        lines.extend(("", f"{source}：{source_total} 次"))
        for model, count in sorted(
            models.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            lines.append(f"- {model}：{count} 次")
    return "\n".join(lines)
