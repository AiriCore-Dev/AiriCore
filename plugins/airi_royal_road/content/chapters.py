from datetime import timedelta

from ..base.constants import ACTIVITY_START
from .characters import MEMBERS


ACTS = (
    {"act_id": "act_1", "title": "向着初升的光", "start_day": 1, "end_day": 35, "partner": "minori", "regions": ("harvest_plain", "fjord_coast")},
    {"act_id": "act_2", "title": "雾海彼端的约定", "start_day": 36, "end_day": 62, "partner": "haruka", "regions": ("mist_isles", "fjord_coast")},
    {"act_id": "act_3", "title": "绝不熄灭的星灯", "start_day": 63, "end_day": 97, "partner": "airi", "regions": ("starlit_mountains", "mist_isles")},
    {"act_id": "act_4", "title": "极夜中的归途", "start_day": 98, "end_day": 125, "partner": "shizuku", "regions": ("polar_snowfield", "starlit_mountains")},
    {"act_id": "act_5", "title": "王道征途", "start_day": 126, "end_day": 154, "partner": "all", "regions": ("aurora_capital", "harvest_plain", "fjord_coast", "mist_isles", "starlit_mountains", "polar_snowfield")},
)


def _act_for(day: int) -> dict:
    return next(item for item in ACTS if item["start_day"] <= day <= item["end_day"])


WEEKS = []
for week_index in range(22):
    start_day = week_index * 7 + 1
    act = _act_for(start_day)
    WEEKS.append({
        "week_id": f"week_{week_index + 1:02d}",
        "week_index": week_index,
        "start_day": start_day,
        "end_day": start_day + 6,
        "act_id": act["act_id"],
        "partner": act["partner"],
        "region_pool": act["regions"],
        "goal_id": f"goal_{week_index + 1:02d}",
        "friday_node_id": f"morning_star_{week_index + 1:02d}",
        "boss_id": f"weekly_boss_{week_index + 1:03d}",
        "vote_options": (f"path_{week_index + 1:02d}_a", f"path_{week_index + 1:02d}_b", f"path_{week_index + 1:02d}_c"),
        "tie_priority": f"path_{week_index + 1:02d}_a",
        "weather_pool": ("clear", "wind", "rain", "snow"),
        "support_scene_id": f"support_{week_index + 1:02d}",
        "outcome_overlay": f"overlay_{week_index + 1:02d}",
    })


DATE_PACKAGES = {}
for day in range(1, 155):
    week = WEEKS[(day - 1) // 7]
    current = ACTIVITY_START.date() + timedelta(days=day - 1)
    DATE_PACKAGES[current.isoformat()] = {
        "activity_day": day,
        "week_id": week["week_id"],
        "event_ids": (f"day_event_{day:03d}",),
        "scene_ids": (f"day_scene_{day:03d}",),
        "weather_pool": week["weather_pool"],
        "partner": week["partner"],
        "available_regions": week["region_pool"],
    }
