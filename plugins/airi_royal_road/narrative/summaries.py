from __future__ import annotations


def fact_summary(facts: dict) -> dict:
    allowed = ("locations", "decisions", "injuries", "bond_changes", "world_outcomes", "ending_flags")
    result = {}
    for key in allowed:
        value = facts.get(key, [])
        if not isinstance(value, list):
            raise TypeError("事实摘要字段必须是列表")
        result[key] = list(value[:32])
    return result
