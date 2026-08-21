JOBS = {
    "先锋": {"job_id": "vanguard", "skills": ("guard", "counter", "provoke"), "element": "光", "stats": {"hp": 40, "attack": 4, "defense": 8, "speed": 2}},
    "游侠": {"job_id": "ranger", "skills": ("aim", "weakness", "scout"), "element": "风", "stats": {"hp": 28, "attack": 8, "defense": 3, "speed": 8}},
    "术士": {"job_id": "arcanist", "skills": ("flare", "tide", "hex"), "element": "火", "stats": {"hp": 24, "attack": 10, "defense": 2, "speed": 5}},
    "诗旅者": {"job_id": "bard", "skills": ("heal", "cheer", "harmony"), "element": "潮", "stats": {"hp": 30, "attack": 5, "defense": 4, "speed": 6}},
}
MEMBERS = {
    "minori": {"name": "花里实乃理", "element": "光", "outfits": ("stage", "travel", "winter"), "expressions": tuple(f"minori_expression_{index:02d}" for index in range(1, 13)), "reaction_ids": ("minori_reaction_support", "minori_reaction_vote", "minori_reaction_boss")},
    "haruka": {"name": "桐谷遥", "element": "潮", "outfits": ("stage", "travel", "winter"), "expressions": tuple(f"haruka_expression_{index:02d}" for index in range(1, 13)), "reaction_ids": ("haruka_reaction_support", "haruka_reaction_vote", "haruka_reaction_boss")},
    "airi": {"name": "桃井爱莉", "element": "火", "outfits": ("stage", "travel", "winter"), "expressions": tuple(f"airi_expression_{index:02d}" for index in range(1, 13)), "reaction_ids": ("airi_reaction_support", "airi_reaction_vote", "airi_reaction_boss")},
    "shizuku": {"name": "日野森雫", "element": "风", "outfits": ("stage", "travel", "winter"), "expressions": tuple(f"shizuku_expression_{index:02d}" for index in range(1, 13)), "reaction_ids": ("shizuku_reaction_support", "shizuku_reaction_vote", "shizuku_reaction_boss")},
}
