from nonebot import on_startswith
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment


calculator_power = on_startswith(("计算倍率", "倍率计算","倍率"))
calculator_together_score = on_startswith(("协力pt", "协力PT"))
calculator_solo_score = on_startswith(("单人pt", "单人PT"))
calculator_challenge_score = on_startswith(("挑战pt", "挑战PT"))



@calculator_power.handle()
async def calculate_multiplier(event: GroupMessageEvent):

    raw_msg = event.get_plaintext().strip()
    if raw_msg.startswith('倍率'): raw_msg = raw_msg[2:]
    if raw_msg.startswith('计算'): raw_msg = raw_msg[2:]
    if raw_msg.startswith('倍率'): raw_msg = raw_msg[2:]

    args_part = " ".join(raw_msg.split())

    if not args_part:
        await calculator_power.finish("用法：计算倍率 (五个数字)", reply_message=True)

    args = args_part.split()
    if len(args) != 5:
        await calculator_power.finish(f"需要五个数字，当前给到了{len(args)}个，请重新输入……", reply_message=True)

    try:
        a, b, c, d, e = map(float, args)
    except ValueError:
        await calculator_power.finish("用法：计算倍率 (五个数字)", reply_message=True)

    total = a + b + c + d + e
    avg_part = (b + c + d + e) / 5
    multiplier = (a + avg_part) / 100 + 1
    actual_value = a + avg_part

    result_msg = (
        f"🎮📊 模拟卡组分析 📊🎮\n"
        f"• 队长加成: {a}\n"
        f"• 综合加成: {total}\n"
        f"• 最终倍率: {multiplier:.2f}\n"
        f"• 技能效果值: {actual_value}%"
    )

    await calculator_power.finish(result_msg, reply_message=True)


@calculator_together_score.handle()
async def calculate_multiplier(event: GroupMessageEvent):

    raw_msg = event.get_plaintext().strip()[4:]

    args_part = " ".join(raw_msg.split())

    if not args_part:
        await calculator_together_score.finish("用法：协力pt (四个数字)\n四个数字先后为个人分数、歌曲加成、卡组加成、消耗加成，队友平均分默认为110w", reply_message=True)

    args = args_part.split()

    if len(args) != 4:
        await calculator_together_score.finish(f"需要四个数字，当前给到了{len(args)}个，请重新输入……", reply_message=True)

    try:
        a, c, d, e = map(float, args)
    except ValueError:
         await calculator_together_score.finish("用法：协力pt (四个数字)\n四个数字先后为个人分数、歌曲加成、卡组加成、消耗加成，队友平均分默认为110w", reply_message=True)

    b = 1100000
    pt_score = round(((114+a/17500+b/100000)*c*(d/100+1))*e)


    result_msg = (
        f"🎮📊 协力模拟PT计算 📊🎮\n"
        f"• 活动协力pt: {pt_score}"
    )

    await calculator_together_score.finish(result_msg, reply_message=True)


@calculator_solo_score.handle()
async def calculate_multiplier(event: GroupMessageEvent):

    raw_msg = event.get_plaintext().strip()[4:]

    args_part = " ".join(raw_msg.split())

    if not args_part:
        await calculator_solo_score.finish("用法：单人pt (四个数字)\n四个数字先后为个人分数、歌曲加成、卡组加成、消耗加成", reply_message=True)

    args = args_part.split()

    if len(args) != 4:
        await calculator_solo_score.finish(f"需要四个数字，当前给到了{len(args)}个，请重新输入……", reply_message=True)

    try:
        a, b, c, d = map(float, args)
    except ValueError:
        await calculator_solo_score.finish("用法：单人pt (四个数字)\n四个数字先后为个人分数、歌曲加成、卡组加成、消耗加成", reply_message=True)

    pt_score = round(((100+a/20000)*b*(c/100+1))*d)

    result_msg = (
        f"🎮📊 单人模拟PT计算 📊🎮\n"
        f"• 活动单人pt: {pt_score}"
    )

    await calculator_solo_score.finish(result_msg, reply_message=True)


@calculator_challenge_score.handle()
async def calculate_multiplier(event: GroupMessageEvent):

    raw_msg = event.get_plaintext().strip()[4:]

    args_part = " ".join(raw_msg.split())

    if not args_part:
        await calculator_challenge_score.finish("用法：挑战pt (个人分数)", reply_message=True)

    args = args_part.split()

    if len(args) > 1:
        await calculator_challenge_score.finish(f"需要一个数字，当前给到了{len(args)}个，请重新输入……", reply_message=True)

    try:
        a = float(args[0])
    except ValueError:
        await calculator_challenge_score.finish("用法：挑战pt (个人分数)", reply_message=True)

    pt_score = round((100+a/20000)*120)

    result_msg = (
        f"🎮📊 挑战模拟PT计算 📊🎮\n"
        f"• 活动挑战pt: {pt_score}"
    )

    await calculator_challenge_score.finish(result_msg, reply_message=True)
