import re
import gc
import random
from nonebot import on_regex, on_fullmatch
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

airi_choice_p1 = on_regex(".+[^还]是.+还是.+", rule = to_me(), block = True, priority=10)
airi_choice = on_regex(".+还是.+", rule = to_me(), block = False, priority=99)
airi_choice_help = on_fullmatch('choicehelp', block = False)

@airi_choice_p1.handle()
async def main(bot: Bot, ev: MessageEvent):
    param = ev.get_plaintext().split("是",1)
    name1 = param[0]
    param = list(set(param[1].split('还是')))
    detailed = 0
    for i in range(len(param)):
        if param[i][-4:] == ' /详细':
            param[i] = param[i][:-4]
            detailed = 1
            break
    if random.randint(0,1): param.append('都是')
    if random.randint(0,1): param.append('都不是')
    #await airi_choice.finish(str(param))
    times = random.randint(2, len(param)*2)
    res = {}
    for i in param: res[i] = 0
    for i in range(0, times):
        res[random.choice(param)] += 1
    tmp = -1
    max_word_tmp = []
    for i in param:
        if tmp < res[i]:
            tmp = res[i]
    for i in param:
        if res[i] == tmp:
            max_word_tmp.append(i)
    if len(max_word_tmp) == 1:
        max_word = max_word_tmp[0]
    else:
        times += 1
        max_word = random.choice(max_word_tmp)
        res[max_word] += 1  
    output = '爱莉在 '
    for i in param: output += i + '，'
    output = output[:-1]
    output += ' 这{}个选项中随机抽了{}次\n以下是每个选项随到的次数：\n'.format(len(param), times)
    for i in param: 
        output += i + '：' + str(res[i]) + '次\n'
    if detailed:
        output += f'\n根据少数服从多数的原则，{name1}{"是"+max_word if max_word not in ["都是","都不是"] else max_word}'
    else:
        output = f'{name1}{"是"+max_word if max_word not in ["都是","都不是"] else max_word}'
    del res, param, times, max_word, max_word_tmp
    gc.collect()
    await airi_choice_p1.finish(output, reply_message = True)
    
@airi_choice.handle()
async def main(bot: Bot, ev: MessageEvent):
    param = list(set(ev.get_plaintext().split("还是")))
    detailed = 0
    for i in range(len(param)):
        if param[i][-4:] == ' /详细':
            param[i] = param[i][:-4]
            detailed = 1
            break
    if random.randint(0,1): param.append('都要')
    if random.randint(0,1): param.append('都不要')
    #await airi_choice.finish(str(param))
    times = random.randint(2, len(param)*2)
    res = {}
    for i in param: res[i] = 0
    for i in range(0, times):
        res[random.choice(param)] += 1
    tmp = -1
    max_word_tmp = []
    for i in param:
        if tmp < res[i]:
            tmp = res[i]
    for i in param:
        if res[i] == tmp:
            max_word_tmp.append(i)
    if len(max_word_tmp) == 1:
        max_word = max_word_tmp[0]
    else:
        times += 1
        max_word = random.choice(max_word_tmp)
        res[max_word] += 1  
    output = '爱莉在 '
    for i in param: output += i + '，'
    output = output[:-1]
    output += ' 这{}个选项中随机抽了{}次\n以下是每个选项随到的次数：\n'.format(len(param), times)
    for i in param: 
        output += i + '：' + str(res[i]) + '次\n'
    if detailed:
        output += '\n根据少数服从多数的原则，爱莉建议你选择{}'.format(max_word)
    else:
        output = '{}'.format(max_word)
    del res, param, times, max_word, max_word_tmp
    gc.collect()
    await airi_choice.finish(output, reply_message = True)
    
@airi_choice_help.handle()
async def main(bot: Bot, ev: MessageEvent):
    await airi_choice_help.finish('⚜️ 用法：\n\n☑️ @爱莉 A还是B（还是C……）（可无限续杯）：从罗列的元素中随机挑出一个\n\n☑️ 上述命令后面加参数“(空格)/详细”：显示详细的抽取过程', reply_message = True)
