LAYOUTS = {
    "cover": {"size": (960, 540), "slots": {"background": (0, 0, 960, 540), "title": (54, 42, 852, 90), "bubble": (120, 390, 720, 110)}},
    "route": {"size": (960, 540), "slots": {"background": (0, 0, 960, 540), "map": (40, 80, 880, 300), "bubble": (120, 390, 720, 110)}},
    "combat": {"size": (960, 540), "slots": {"background": (0, 0, 960, 540), "enemy": (570, 100, 320, 260), "status": (40, 60, 420, 100), "bubble": (120, 390, 720, 110)}},
    "loot": {"size": (960, 540), "slots": {"background": (0, 0, 960, 540), "loot": (120, 130, 720, 230), "bubble": (120, 390, 720, 110)}},
    "partner": {"size": (960, 540), "slots": {"background": (0, 0, 960, 540), "character": (360, 60, 320, 360), "bubble": (120, 390, 720, 110)}},
    "journal": {"size": (960, 540), "slots": {"background": (0, 0, 960, 540), "journal": (110, 90, 740, 320)}},
    "weekly": {"size": (960, 540), "slots": {"background": (0, 0, 960, 540), "report": (80, 70, 800, 350)}},
    "final": {"size": (960, 540), "slots": {"background": (0, 0, 960, 540), "memorial": (80, 70, 800, 350)}}
}


def layout(name: str) -> dict:
    if name not in LAYOUTS:
        raise ValueError("未知画面布局")
    return LAYOUTS[name]
