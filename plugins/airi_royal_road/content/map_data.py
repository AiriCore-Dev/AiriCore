REGIONS = (
    "harvest_plain",
    "fjord_coast",
    "mist_isles",
    "starlit_mountains",
    "polar_snowfield",
    "aurora_capital",
)


LOCATIONS = {
    "hope_carriage": {"region": "harvest_plain", "terrain": "camp", "risk": 0, "resources": ("rest",), "scene_id": "hope_carriage", "unlock": (), "date_events": (), "revisit": "camp"}
}
for region in REGIONS:
    prefix = region.replace("_", "-")
    for index in range(15):
        location_id = f"{region}_{index + 1:02d}"
        LOCATIONS[location_id] = {
            "region": region,
            "terrain": ("town", "village", "port", "wild", "ruin", "stage")[index % 6],
            "risk": (index % 5) + 1,
            "resources": ("supply", "bond", "relic")[index % 3],
            "scene_id": f"scene_{prefix}_{index + 1:02d}",
            "unlock": () if index < 3 else (f"{region}_{index - 2:02d}",),
            "date_events": (),
            "revisit": ("trade", "quest", "battle")[index % 3],
        }


for region in REGIONS:
    ids = [f"{region}_{index + 1:02d}" for index in range(15)]
    for index, location_id in enumerate(ids):
        LOCATIONS[location_id]["neighbors"] = tuple(ids[max(0, index - 1):index] + ids[index + 1:index + 2])
LOCATIONS["hope_carriage"]["neighbors"] = tuple(f"harvest_plain_{index + 1:02d}" for index in range(3))
