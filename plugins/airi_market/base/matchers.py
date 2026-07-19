from nonebot import on_startswith, on_fullmatch
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER

airimarket = on_startswith("airimarket", priority=5, block=True, permission=SUPERUSER)
airimarketlist = on_fullmatch("airimarketlist", priority=4, block=True, permission=SUPERUSER)
airimarkettest = on_startswith("airimarkettest", priority=4, block=True, permission=SUPERUSER)
airimarketcancel = on_startswith("airimarketcancel", priority=4, block=True, permission=SUPERUSER)
airimarketboost = on_startswith("airimarketboost", priority=4, block=True, permission=SUPERUSER)
airimarketsdebug = on_startswith("sdebug ", priority=5, block=True, rule=to_me(), permission=SUPERUSER)
