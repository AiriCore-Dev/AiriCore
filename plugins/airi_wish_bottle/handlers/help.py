import gc

from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent

from ..base.matchers import bottlehelp


@bottlehelp.handle()
async def _(bot: Bot, ev: MessageEvent):
    msg = []
    res = '“セカイ”それは、『本当の想い』を見つけられる場所——初音 ミク\n\
「世界」，那是一个能找到“真正的心愿”的地方。——初音未来\n\n\
心愿，是心灵的信使，载着未曾言说的困惑、隐秘的期待或温柔的故事，穿越茫茫人海，飘扬在充满希望的「世界」中。何不抛却身份束缚，匿名书写真实自我，或许下一秒，就有陌生灵魂拾起你的心愿，以文字共鸣，开启一场不期而遇的治愈对话。\n\n\
💫 欢迎使用 Airi心愿瓶\n\
（Momoi Airi Wish Bottle）'
    msg.append({"type": "node", "data": {"name": "Momoi Airi Wish Bottle", "uin": bot.self_id, "content": res}})
    res = '📒 指令列表：\n\
 -扔心愿瓶 [内容]：记下你的心愿并装入具有唯一编号的心愿瓶内，等待有缘人的开启。\n\
 -捡心愿瓶：随机捡起一个心愿瓶阅读。\n\
 -捡心愿瓶 [编号]：捡起特定编号的心愿瓶阅读。\n\
 -评论心愿瓶 [编号] [评论内容]：在特定编号的心愿瓶里写下你的评论。\n\
 -我的心愿瓶：查看本人持有的心愿瓶情况。\n\
 -修改心愿瓶 [编号] [内容]：修改本人持有的特定编号心愿瓶里的心愿内容。\n\
 -转移心愿瓶 [编号] [@...]：将你所持有的特定编号的心愿瓶转交给你@的人。\n\
 -销毁心愿瓶 [编号]：将你所持有的特定编号的心愿瓶销毁。\n\
 -举报心愿瓶 [编号] [举报理由]：如果你发现特定编号的心愿瓶中存在违规内容，举报一下！（奖励见下）\n\n\
*注意：参数之间请使用空格隔开！\n\
正确示范：捡心愿瓶 xxx\n\
错误示范：捡心愿瓶xxx'
    msg.append({"type": "node", "data": {"name": "指令列表", "uin": bot.self_id, "content": res}})

    res = '☑️ 游戏玩法：\n\
类似于漂流瓶。\n\
相较于普通漂流瓶，Airi心愿瓶的提供了更多有趣的玩法。'
    msg.append({"type": "node", "data": {"name": "游戏玩法", "uin": bot.self_id, "content": res}})

    res = '☑️ 心愿上限为500字，支持图片（最多9张）。\n\
每人每天可发表十条评论，单条评论上限为20字，一条心愿最多保留30条评论。'
    msg.append({"type": "node", "data": {"name": "一些限制", "uin": bot.self_id, "content": res}})

    res = '☑️ 任何心愿瓶的内容及评论都需经过多道审核工序。\n\
如果当场通过机器审核，心愿瓶编号会当场发放。如果未通过机器审核转人工，会在审核之后决定是否发放。\n\
举报心愿瓶，经核实情况属实，奖励举报人还未被其他人持有的特定编号心愿瓶一个（编号由你决定）。多次恶意举报或多次投放恶意内容者，奖励Airi永久黑名单特权。'
    msg.append({"type": "node", "data": {"name": "内容审核", "uin": bot.self_id, "content": res}})

    res = '☑️ 这一栏介绍扔心愿瓶时，唯一编号的生成算法。\n\
Airi会将心愿内容过一遍md5哈希，得到一段32位长的0-f字符串。取前12位用base64编码，得到对应的8位心愿瓶编号。如果编号已经存在，就自然往后挪动一位，直到找到可用编号为止。\n\
有本事的话，用你的技术力去争夺属于你的唯一编号吧。'
    msg.append({"type": "node", "data": {"name": "心愿瓶编号的生成算法", "uin": bot.self_id, "content": res}})

    msg.append({"type": "node", "data": {"name": "版权信息", "uin": bot.self_id, "content": 'Powered By AiriCore Dev.'}})
    await bot.send_group_forward_msg(group_id=ev.group_id, messages=msg)
    del msg, res
    gc.collect()
