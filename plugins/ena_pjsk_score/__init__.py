from nonebot import on_startswith
from nonebot.adapters.onebot.v11 import GroupMessageEvent

POWER_PREFIXES = ("计算倍率", "倍率计算")
TOGETHER_PREFIXES = ("协力pt", "协力PT")
SOLO_PREFIXES = ("单人pt", "单人PT")
CHALLENGE_PREFIXES = ("挑战pt", "挑战PT")

calculator_power = on_startswith(POWER_PREFIXES, priority=10)
calculator_together_score = on_startswith(TOGETHER_PREFIXES, priority=10)
calculator_solo_score = on_startswith(SOLO_PREFIXES, priority=10)
calculator_challenge_score = on_startswith(CHALLENGE_PREFIXES, priority=10)


def _strip_prefix(text: str, prefixes) -> str:
    text = text.strip()
    for p in prefixes:
        if text.startswith(p):
            return text[len(p):].strip()
    return text


def _args(text: str, prefixes):
    return _strip_prefix(text, prefixes).split()


@calculator_power.handle()
async def handle_power(event: GroupMessageEvent):
    usage = "用法：计算倍率 (五个数字)"
    args = _args(event.get_plaintext(), POWER_PREFIXES)

    if not args:
        await calculator_power.finish(usage, reply_message=True)

    if len(args) != 5:
        await calculator_power.finish(f"需要五个数字，当前给到了{len(args)}个，请重新输入……", reply_message=True)

    try:
        a, b, c, d, e = map(float, args)
    except ValueError:
        await calculator_power.finish(usage, reply_message=True)

    total = a + b + c + d + e
    avg_part = (b + c + d + e) / 5
    multiplier = (a + avg_part) / 100 + 1
    actual_value = a + avg_part

    result_msg = (
        f"模拟卡组分析\n"
        f"- 队长加成: {a}\n"
        f"- 综合加成: {total}\n"
        f"- 最终倍率: {multiplier:.2f}\n"
        f"- 技能效果值: {actual_value}%"
    )

    await calculator_power.finish(result_msg, reply_message=True)


@calculator_together_score.handle()
async def handle_together(event: GroupMessageEvent):
    usage = "用法：协力pt (四个数字)\n四个数字先后为个人分数、歌曲加成、卡组加成、消耗加成，队友平均分默认为110w"
    args = _args(event.get_plaintext(), TOGETHER_PREFIXES)

    if not args:
        await calculator_together_score.finish(usage, reply_message=True)

    if len(args) != 4:
        await calculator_together_score.finish(f"需要四个数字，当前给到了{len(args)}个，请重新输入……", reply_message=True)

    try:
        a, c, d, e = map(float, args)
    except ValueError:
        await calculator_together_score.finish(usage, reply_message=True)

    b = 1100000
    pt_score = round(((114 + a / 17500 + b / 100000) * c * (d / 100 + 1)) * e)

    await calculator_together_score.finish(
        f"协力模拟PT计算\n- 活动协力pt: {pt_score}", reply_message=True
    )


@calculator_solo_score.handle()
async def handle_solo(event: GroupMessageEvent):
    usage = "用法：单人pt (四个数字)\n四个数字先后为个人分数、歌曲加成、卡组加成、消耗加成"
    args = _args(event.get_plaintext(), SOLO_PREFIXES)

    if not args:
        await calculator_solo_score.finish(usage, reply_message=True)

    if len(args) != 4:
        await calculator_solo_score.finish(f"需要四个数字，当前给到了{len(args)}个，请重新输入……", reply_message=True)

    try:
        a, b, c, d = map(float, args)
    except ValueError:
        await calculator_solo_score.finish(usage, reply_message=True)

    pt_score = round(((100 + a / 20000) * b * (c / 100 + 1)) * d)

    await calculator_solo_score.finish(
        f"单人模拟PT计算\n- 活动单人pt: {pt_score}", reply_message=True
    )


@calculator_challenge_score.handle()
async def handle_challenge(event: GroupMessageEvent):
    usage = "用法：挑战pt (个人分数)"
    args = _args(event.get_plaintext(), CHALLENGE_PREFIXES)

    if not args:
        await calculator_challenge_score.finish(usage, reply_message=True)

    if len(args) > 1:
        await calculator_challenge_score.finish(f"需要一个数字，当前给到了{len(args)}个，请重新输入……", reply_message=True)

    try:
        a = float(args[0])
    except ValueError:
        await calculator_challenge_score.finish(usage, reply_message=True)

    pt_score = round((100 + a / 20000) * 120)

    await calculator_challenge_score.finish(
        f"挑战模拟PT计算\n- 活动挑战pt: {pt_score}", reply_message=True
    )
