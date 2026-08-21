from datetime import date


DATE_EVENTS = {
    "中秋": {"scene_id": "mid_autumn_lanterns", "regions": ("harvest_plain", "fjord_coast")},
    "万圣夜": {"scene_id": "halloween_tide", "regions": ("mist_isles",)},
    "立冬": {"scene_id": "first_winter_lights", "regions": ("starlit_mountains",)},
    "小雪": {"scene_id": "first_snow", "regions": ("starlit_mountains", "polar_snowfield")},
    "圣诞节": {"scene_id": "christmas_stage", "regions": ("polar_snowfield",)},
    "跨年守夜": {"scene_id": "new_year_watch", "regions": ("polar_snowfield", "aurora_capital")},
    "元旦": {"scene_id": "first_light", "regions": ("aurora_capital",)},
    "小寒": {"scene_id": "minor_cold", "regions": ("aurora_capital",)},
    "大寒": {"scene_id": "major_cold", "regions": ("aurora_capital",)},
}
