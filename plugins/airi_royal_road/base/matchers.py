from nonebot import on_fullmatch, on_regex
from nonebot.adapters.onebot.v11.permission import GROUP
from nonebot.rule import to_me

from .constants import (
    COMMAND_ADVENTURE,
    COMMAND_ARCHIVE,
    COMMAND_CHOICE_PATTERN,
    COMMAND_HELP,
    COMMAND_MAP,
    COMMAND_SETTLEMENT,
    COMMAND_PARTNER,
    COMMAND_VOTE_CHOICE_PATTERN,
    COMMAND_RECALL_PATTERN,
    COMMAND_STATUS,
    COMMAND_VOTE,
)


def _fullmatch(command: str):
    return on_fullmatch(command, priority=12, block=True, permission=GROUP)


adventure = _fullmatch(COMMAND_ADVENTURE)
map_view = _fullmatch(COMMAND_MAP)
status = _fullmatch(COMMAND_STATUS)
archive = _fullmatch(COMMAND_ARCHIVE)
help = _fullmatch(COMMAND_HELP)
vote = _fullmatch(COMMAND_VOTE)
settlement = _fullmatch(COMMAND_SETTLEMENT)
partner = on_regex(r"^王道伙伴\s+.+$", priority=12, block=True, permission=GROUP)
vote_choice = on_regex(COMMAND_VOTE_CHOICE_PATTERN, priority=12, block=True, permission=GROUP)
recall = on_regex(COMMAND_RECALL_PATTERN, priority=12, block=True, permission=GROUP)
choice = on_regex(COMMAND_CHOICE_PATTERN, priority=12, rule=to_me(), block=True, permission=GROUP)
