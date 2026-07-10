from nonebot import on_startswith, on_fullmatch
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER

bottlehelp = on_fullmatch(('心愿瓶帮助','心愿瓶help'),priority=5,block=True)
superuser_debug = on_startswith('bdebug ',priority=5,block=True,rule=to_me(),permission=SUPERUSER)
rxyp = on_startswith('扔心愿瓶',priority=5,block=True)
jxyp = on_startswith('捡心愿瓶',priority=5,block=True)
plxyp = on_startswith('评论心愿瓶',priority=5,block=True)
wdxyp = on_fullmatch('我的心愿瓶',priority=5,block=True)
xgxyp = on_startswith('修改心愿瓶',priority=5,block=True)
zyxyp = on_startswith('转移心愿瓶',priority=5,block=True)
xhxyp = on_startswith('销毁心愿瓶',priority=5,block=True)
jbxyp = on_startswith('举报心愿瓶',priority=5,block=True)
btshenhe = on_startswith(('btapprove ','btreject '),priority=5,block=True,permission=SUPERUSER)
plshenhe = on_startswith(('plapprove ','plreject '),priority=5,block=True,permission=SUPERUSER)
jbshenhe = on_startswith(('jbapprove ','jbreject '),priority=5,block=True,permission=SUPERUSER)
pdbt = on_startswith('pending_bottle',priority=5,block=True,permission=SUPERUSER)
pdpl = on_startswith('pending_comment',priority=5,block=True,permission=SUPERUSER)
pdjb = on_fullmatch('pending_jb',priority=5,block=True,permission=SUPERUSER)
