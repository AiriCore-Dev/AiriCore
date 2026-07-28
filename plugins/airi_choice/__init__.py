import random
from nonebot import on_regex, on_fullmatch
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent

airi_choice_p1 = on_regex(".+[^还]是.+还是.+", rule=to_me(), block=True, priority=10)
airi_choice = on_regex(".+还是.+", rule=to_me(), block=False, priority=10)
airi_choice_help = on_fullmatch('choicehelp', block=False)


def _dedup(items):
    seen = set()
    out = []
    for i in items:
        i = i.strip()
        if not i or i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out


def _parse_options(raw_parts):
    param = _dedup(raw_parts)
    detailed = 0
    for i in range(len(param)):
        if param[i].endswith('/详细'):
            param[i] = param[i][:-3].strip()
            detailed = 1
            break
    param = _dedup(param)
    return param, detailed


def _roll(param, extras):
    for extra in extras:
        if extra not in param and random.randint(0, 1):
            param.append(extra)
    times = random.randint(2, len(param) * 2)
    res = {i: 0 for i in param}
    for _ in range(times):
        res[random.choice(param)] += 1
    top = max(res.values())
    candidates = [i for i in param if res[i] == top]
    if len(candidates) == 1:
        max_word = candidates[0]
    else:
        times += 1
        max_word = random.choice(candidates)
        res[max_word] += 1
    detail = 'Airi在 ' + '，'.join(param)
    detail += ' 这{}个选项中随机抽了{}次\n以下是每个选项随到的次数：\n'.format(len(param), times)
    for i in param:
        detail += i + '：' + str(res[i]) + '次\n'
    return max_word, detail


@airi_choice_p1.handle()
async def _(bot: Bot, ev: MessageEvent):
    raw = ev.get_plaintext().split("是", 1)
    if len(raw) < 2:
        return
    name1 = raw[0].strip()
    param, detailed = _parse_options(raw[1].split('还是'))
    if not param:
        return
    max_word, detail = _roll(param, ('都是', '都不是'))
    tail = max_word if max_word in ('都是', '都不是') else '是' + max_word
    if detailed:
        output = detail + f'\n根据少数服从多数的原则，{name1}{tail}'
    else:
        output = f'{name1}{tail}'
    await airi_choice_p1.finish(output, reply_message=True)


@airi_choice.handle()
async def _(bot: Bot, ev: MessageEvent):
    param, detailed = _parse_options(ev.get_plaintext().split("还是"))
    if not param:
        return
    max_word, detail = _roll(param, ('都要', '都不要'))
    if detailed:
        output = detail + '\n根据少数服从多数的原则，Airi建议你选择{}'.format(max_word)
    else:
        output = '{}'.format(max_word)
    await airi_choice.finish(output, reply_message=True)


@airi_choice_help.handle()
async def _(bot: Bot, ev: MessageEvent):
    await airi_choice_help.finish(
        '用法：\n\n'
        '- @Airi A还是B（还是C……）（可无限续杯）：从罗列的元素中随机挑出一个\n\n'
        '- 上述命令后面加参数“(空格)/详细”：显示详细的抽取过程',
        reply_message=True,
    )
