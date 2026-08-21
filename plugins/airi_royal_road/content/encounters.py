ELEMENTS = ("火", "潮", "风", "光")


def _enemy(index: int, kind: str, turns: tuple[int, int]) -> dict:
    return {"enemy_id": f"{kind}_{index:03d}", "kind": kind, "hp": 30 + index % 40, "attack": 5 + index % 12, "defense": 2 + index % 8, "speed": 2 + index % 10, "weakness": ELEMENTS[index % 4], "telegraph_id": f"telegraph_{index % 12:02d}", "turn_range": turns, "reward": 100 + index % 151}


ORDINARY_ENEMIES = tuple(_enemy(index, "ordinary", (2, 3)) for index in range(1, 101))
ELITE_ENEMIES = tuple(_enemy(index, "elite", (3, 5)) for index in range(1, 31))
WEEKLY_BOSSES = tuple(_enemy(index, "weekly_boss", (3, 5)) for index in range(1, 23))
ACT_BOSSES = tuple(_enemy(index, "act_boss", (3, 5)) for index in range(1, 6))
ENCOUNTERS = {record["enemy_id"]: record for record in ORDINARY_ENEMIES + ELITE_ENEMIES + WEEKLY_BOSSES + ACT_BOSSES}
