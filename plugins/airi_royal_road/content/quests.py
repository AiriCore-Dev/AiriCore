QUESTS = {}
for week_index in range(22):
    for branch in range(3):
        quest_id = f"quest_{week_index + 1:02d}_{branch + 1}"
        QUESTS[quest_id] = {"quest_id": quest_id, "week_index": week_index, "fact_id": f"fact_{week_index + 1:02d}_{branch + 1}", "scene_id": f"quest_scene_{week_index + 1:02d}_{branch + 1}", "reward_source": "location"}
