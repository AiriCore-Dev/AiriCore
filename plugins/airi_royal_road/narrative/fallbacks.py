from .schema import SceneScript


def fallback_scene(event_id: str, frame_kind: str = "journal") -> SceneScript:
    mood = ("bright", "tense", "tender", "resolute", "quiet")[sum(ord(char) for char in event_id) % 5]
    return SceneScript(f"fallback_{event_id}", frame_kind if frame_kind in {"route", "combat", "loot", "partner", "journal", "vote", "weekly", "final"} else "journal", (), "wide", (), "叙事画面暂时采用预制脚本", mood, "none", "规则结果已保存，旅途仍会继续")
