from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


ACTIVITY_TZ = ZoneInfo("Asia/Shanghai")
ACTIVITY_START = datetime(2026, 8, 31, 0, 0, 0, tzinfo=ACTIVITY_TZ)
ACTIVITY_END = datetime(2027, 1, 31, 23, 59, 59, tzinfo=ACTIVITY_TZ)
SETTLEMENT_START = datetime(2027, 2, 1, 0, 0, 0, tzinfo=ACTIVITY_TZ)
SETTLEMENT_END = datetime(2027, 2, 7, 23, 59, 59, tzinfo=ACTIVITY_TZ)
TOTAL_DAYS = 154
TOTAL_WEEKS = 22
EMBLEM_TO_CREDIT = 10
CREDIT_CAP = 10000
SCHEMA_VERSION = 2
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "airi_royal_road"
PERSONAL_DATA_FILE = DATA_DIR / "personal.pk"
WORLD_DATA_FILE = DATA_DIR / "world.pk"
PERSONAL_DATA_KEY = "personal"
WORLD_DATA_KEY = "world"
COMMAND_ADVENTURE = "王道征途"
COMMAND_MAP = "王道地图"
COMMAND_STATUS = "王道状态"
COMMAND_ARCHIVE = "王道图鉴"
COMMAND_HELP = "王道帮助"
COMMAND_VOTE = "王道投票"
COMMAND_SETTLEMENT = "王道结算"
COMMAND_PARTNER = "王道伙伴"
COMMAND_CHOICE_PATTERN = r"^征途\s+[1-9][0-9]*$"
COMMAND_VOTE_CHOICE_PATTERN = r"^王道投票\s+[1-9][0-9]*$"
COMMAND_RECALL_PATTERN = r"^王道回忆\s+\d{4}-\d{2}-\d{2}$"
