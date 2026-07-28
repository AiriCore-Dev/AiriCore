from nonebot import on_regex, on_startswith, on_fullmatch
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.permission import GROUP

qiandao = on_fullmatch('签到', priority=10, block=True, permission=GROUP)
qiandaohelp = on_fullmatch(('签到帮助', '收藏帮助'), priority=10, block=True, permission=GROUP)
xinxi = on_fullmatch('收藏信息', priority=10, block=True, permission=GROUP)
shoucang = on_startswith('查看收藏', priority=10, block=True, permission=GROUP)
chouka = on_startswith('收藏抽卡', priority=10, block=True, permission=GROUP)
yincang17 = on_fullmatch('给我隐藏收藏品', priority=10, rule=to_me(), block=True, permission=GROUP)
transcation = on_regex(r'转给.+\d+[个]?积分', priority=10, rule=to_me(), block=True, permission=GROUP)
reborn = on_startswith('重生', priority=10, rule=to_me(), block=True, permission=GROUP)
theme_manage = on_startswith('收藏主题', priority=10, block=True, permission=GROUP)
superuser_debug = on_startswith('qdebug ', priority=10, block=True, rule=to_me(), permission=SUPERUSER)
daily_challenge = on_fullmatch(('每日挑战', '今日挑战'), priority=10, block=True, permission=GROUP)
flag_submit = on_regex(r'flag{.+}', priority=10, rule=to_me(), block=True, permission=GROUP)
buy_tip = on_fullmatch('购买提示', priority=10, block=True, permission=GROUP)
jrys = on_fullmatch(('jrys', '今日运势', '运势'), priority=10, block=True, permission=GROUP)
