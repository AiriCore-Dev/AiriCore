from nonebot import on_startswith
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER

matcher = on_startswith('通用matcher')
superuser_debug = on_startswith('tdebug ', priority=5, block=True, rule=to_me(), permission=SUPERUSER)
turtle_soup_on = on_startswith('海龟汤', priority=5, block=True)
query = on_startswith('提问', priority=5, block=True)
truth = on_startswith('猜汤底', priority=5, block=True)
history = on_startswith('历史', priority=5, block=True)
times_used = on_startswith('次数', priority=5, block=True)
force_end = on_startswith('结束海龟汤', priority=5, block=True)
