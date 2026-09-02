from nonebot import on_startswith, on_fullmatch
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11.permission import GROUP
from utils.superuser_2fa import SUPERUSER_2FA

bottlehelp = on_fullmatch(('心愿瓶帮助','心愿瓶help'),priority=5,block=True)
superuser_debug = on_startswith('bdebug ',priority=5,block=True,rule=to_me(),permission=SUPERUSER_2FA)
rxyp = on_startswith('扔心愿瓶',priority=5,block=True,permission=GROUP)
jxyp = on_startswith('捡心愿瓶',priority=5,block=True,permission=GROUP)
plxyp = on_startswith('评论心愿瓶',priority=5,block=True,permission=GROUP)
wdxyp = on_fullmatch('我的心愿瓶',priority=5,block=True,permission=GROUP)
xgxyp = on_startswith('修改心愿瓶',priority=5,block=True,permission=GROUP)
zyxyp = on_startswith('转移心愿瓶',priority=5,block=True,permission=GROUP)
xhxyp = on_startswith('销毁心愿瓶',priority=5,block=True,permission=GROUP)
jbxyp = on_startswith('举报心愿瓶',priority=5,block=True,permission=GROUP)
btshenhe = on_startswith(('btapprove ','btreject '),priority=5,block=True,permission=SUPERUSER_2FA)
plshenhe = on_startswith(('plapprove ','plreject '),priority=5,block=True,permission=SUPERUSER_2FA)
jbshenhe = on_startswith(('jbapprove ','jbreject '),priority=5,block=True,permission=SUPERUSER_2FA)
pdbt = on_startswith('pending_bottle',priority=5,block=True,permission=SUPERUSER_2FA)
pdpl = on_startswith('pending_comment',priority=5,block=True,permission=SUPERUSER_2FA)
pdjb = on_fullmatch('pending_jb',priority=5,block=True,permission=SUPERUSER_2FA)
