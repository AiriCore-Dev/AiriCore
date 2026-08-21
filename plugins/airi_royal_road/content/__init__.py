from .chapters import ACTS, WEEKS, DATE_PACKAGES
from .characters import JOBS, MEMBERS
from .encounters import ENCOUNTERS
from .items import ITEMS
from .quests import QUESTS


def validate_catalog() -> None:
    if len(WEEKS) != 22 or len(DATE_PACKAGES) != 154 or len(ITEMS) != 180 or len(QUESTS) != 66:
        raise ValueError("王道征途内容目录数量不完整")
    if sorted(item["week_index"] for item in WEEKS) != list(range(22)):
        raise ValueError("王道征途周回目录不连续")
    if len({item["week_id"] for item in WEEKS}) != 22:
        raise ValueError("王道征途周回 ID 重复")


validate_catalog()
