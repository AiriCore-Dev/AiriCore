from nonebot import on_startswith, on_fullmatch
from nonebot.rule import to_me
from utils.superuser_2fa import SUPERUSER_2FA

airimarket = on_startswith("airimarket", priority=5, block=True, permission=SUPERUSER_2FA)
airimarketlist = on_fullmatch("airimarketlist", priority=4, block=True, permission=SUPERUSER_2FA)
airimarkettest = on_startswith("airimarkettest", priority=4, block=True, permission=SUPERUSER_2FA)
airimarketcancel = on_startswith("airimarketcancel", priority=4, block=True, permission=SUPERUSER_2FA)
airimarketboost = on_startswith("airimarketboost", priority=4, block=True, permission=SUPERUSER_2FA)
airimarketsdebug = on_startswith("sdebug ", priority=5, block=True, rule=to_me(), permission=SUPERUSER_2FA)
