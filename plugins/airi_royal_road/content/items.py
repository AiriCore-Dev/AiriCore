ITEMS = {}
for index in range(1, 181):
    item_id = f"item_{index:03d}"
    ITEMS[item_id] = {"item_id": item_id, "kind": ("equipment", "relic", "consumable")[index % 3], "effect_id": f"effect_{index % 24:02d}", "icon_id": f"icon_item_{index:03d}", "rarity": 1 + index % 5}
