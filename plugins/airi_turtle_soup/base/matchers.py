from nonebot import on_startswith
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.adapters.onebot.v11.permission import GROUP

from . import state


async def _in_active_game(event: GroupMessageEvent) -> bool:
    gid = str(event.group_id)
    return 'turtle' in state.data.get('group', {}).get(gid, {})


superuser_debug = on_startswith('tdebug ', priority=5, block=True, rule=to_me(), permission=SUPERUSER)
turtle_soup_on = on_startswith('海龟汤', priority=5, block=True, permission=GROUP)
query = on_startswith('提问', priority=5, block=True, permission=GROUP, rule=_in_active_game)
truth = on_startswith('猜汤底', priority=5, block=True, permission=GROUP, rule=_in_active_game)
history = on_startswith('历史', priority=5, block=True, permission=GROUP, rule=_in_active_game)
times_used = on_startswith('次数', priority=5, block=True, permission=GROUP, rule=_in_active_game)
force_end = on_startswith('结束海龟汤', priority=5, block=True, permission=GROUP)

matcher = turtle_soup_on
