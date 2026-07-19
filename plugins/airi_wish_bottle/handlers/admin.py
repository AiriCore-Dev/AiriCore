from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from ..base import state
from ..base.matchers import btshenhe, plshenhe, jbshenhe, pdbt, pdpl, pdjb, superuser_debug
from ..base.helpers import generate_unique_id, send_email, nxcr
from ..base.email_template import render_bottle_result, render_comment_result, render_report_result


@pdbt.handle()
async def _(bot: Bot, ev: MessageEvent):
    res = ''
    for unique_id in state.data['pending_bottles'].keys():
        res += f'ID：{unique_id}\n来源：{state.data["pending_bottles"][unique_id]["owner"]}_{state.data["pending_bottles"][unique_id]["owner_id"]}\n内容：{state.data["pending_bottles"][unique_id]["content"]}\n\n'
    res = res.strip()
    if not len(res): res = "暂无"
    await superuser_debug.finish(res, reply_message=True)


@pdpl.handle()
async def _(bot: Bot, ev: MessageEvent):
    res = ''
    for unique_id in state.data['pending_comment'].keys():
        res += f'评论来源ID：{state.data["pending_comment"][unique_id]["comment_to"]}\n评论人QQ：{state.data["pending_comment"][unique_id]["from"]}\n评论内容：{state.data["pending_comment"][unique_id]["content"]}\n\n'
    res = res.strip()
    if not len(res): res = "暂无"
    await superuser_debug.finish(res, reply_message=True)


@pdjb.handle()
async def _(bot: Bot, ev: MessageEvent):
    res = ''
    for unique_id in state.data['pending_jb'].keys():
        res += f'举报人：{state.data["pending_jb"][unique_id]["jbr"]}\n举报ID：{state.data["pending_jb"][unique_id]["unique_id"]}\n举报理由：{state.data["pending_jb"][unique_id]["comment"]}\n\n'
    res = res.strip()
    if not len(res): res = "暂无"
    await superuser_debug.finish(res, reply_message=True)


@btshenhe.handle()
async def _(bot: Bot, ev: MessageEvent):
    from ..base.matchers import jxyp
    src = str(ev.message).split()
    if len(src) != 2:
        await jxyp.finish('格式错误', reply_message=True)
    else:
        unique_id = src[1].strip()
    if src[0] == 'btapprove' and unique_id == 'all':
        pd_bt = list(state.data["pending_bottles"].keys())
        for unique_id in pd_bt:
            if unique_id in state.data["bottles"].keys():
                if state.data["bottles"][unique_id]['owner_id'] == state.data["pending_bottles"][unique_id]['owner_id']:
                    state.data["bottles"][unique_id] = state.data["pending_bottles"][unique_id]
                else:
                    unique_id_tmp = await generate_unique_id(state.data["pending_bottles"][unique_id]["content"])
                    state.data["bottles"][unique_id_tmp] = state.data["pending_bottles"][unique_id]
                    unique_id = unique_id_tmp
            else:
                state.data["bottles"][unique_id] = state.data["pending_bottles"][unique_id]
            try:
                state.data['collections'][state.data["pending_bottles"][unique_id]['owner_id']]
            except:
                state.data['collections'][state.data["pending_bottles"][unique_id]['owner_id']] = []
            state.data['collections'][state.data["pending_bottles"][unique_id]['owner_id']].append(unique_id)
            subj, plain, html_body = render_bottle_result(state.data["bottles"][unique_id]["owner"], state.data["bottles"][unique_id]["content"], unique_id, True)
            send_email(f'{state.data["bottles"][unique_id]["owner_id"]}@qq.com', subj, plain, html_body)
            del state.data["pending_bottles"][unique_id]
    elif src[0] == 'btreject' and unique_id == 'all':
        for unique_id in state.data['pending_bottles'].keys():
            subj, plain, html_body = render_bottle_result(state.data["pending_bottles"][unique_id]["owner"], state.data["pending_bottles"][unique_id]["content"], unique_id, False)
            send_email(f'{state.data["pending_bottles"][unique_id]["owner_id"]}@qq.com', subj, plain, html_body)
        state.data["pending_bottles"] = {}
    elif unique_id not in state.data["pending_bottles"].keys():
        await jxyp.finish(f'编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    elif src[0] == 'btapprove':
        if unique_id in state.data["bottles"].keys():
            if state.data["bottles"][unique_id]['owner_id'] == state.data["pending_bottles"][unique_id]['owner_id']:
                state.data["bottles"][unique_id] = state.data["pending_bottles"][unique_id]
            else:
                unique_id_tmp = unique_id
                while unique_id_tmp in state.data["bottles"].keys():
                    unique_id_tmp = nxcr(unique_id_tmp)
                state.data["bottles"][unique_id_tmp] = state.data["pending_bottles"][unique_id]
                unique_id = unique_id_tmp
        else:
            state.data["bottles"][unique_id] = state.data["pending_bottles"][unique_id]
        try:
            state.data['collections'][state.data["pending_bottles"][unique_id]['owner_id']]
        except:
            state.data['collections'][state.data["pending_bottles"][unique_id]['owner_id']] = []
        state.data['collections'][state.data["pending_bottles"][unique_id]['owner_id']].append(unique_id)
        subj, plain, html_body = render_bottle_result(state.data["bottles"][unique_id]["owner"], state.data["bottles"][unique_id]["content"], unique_id, True)
        send_email(f'{state.data["bottles"][unique_id]["owner_id"]}@qq.com', subj, plain, html_body)
        del state.data["pending_bottles"][unique_id]
    elif src[0] == 'btreject':
        subj, plain, html_body = render_bottle_result(state.data["pending_bottles"][unique_id]["owner"], state.data["pending_bottles"][unique_id]["content"], unique_id, False)
        send_email(f'{state.data["pending_bottles"][unique_id]["owner_id"]}@qq.com', subj, plain, html_body)
        del state.data["pending_bottles"][unique_id]
    await jxyp.finish('操作成功', reply_message=True)


@plshenhe.handle()
async def _(bot: Bot, ev: MessageEvent):
    from ..base.matchers import jxyp
    src = str(ev.message).split()
    if len(src) != 2:
        await jxyp.finish('格式错误', reply_message=True)
    else:
        unique_id = src[1].strip()
    if src[0] == 'plapprove' and unique_id == 'all':
        pd_pl = list(state.data["pending_comment"].keys())
        for unique_id in pd_pl:
            state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments'].append(state.data["pending_comment"][unique_id]["content"])
            if len(state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments']) > 30:
                state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments'].pop(0)
            subj, plain, html_body = render_comment_result(state.data["pending_comment"][unique_id]["from"].split("_")[0], state.data["pending_comment"][unique_id]["content"], unique_id[-8:], True)
            send_email(f'{state.data["pending_comment"][unique_id]["from"].split("_")[1]}@qq.com', subj, plain, html_body)
            del state.data["pending_comment"][unique_id]
    elif src[0] == 'plreject' and unique_id == 'all':
        for unique_id in state.data["pending_comment"].keys():
            subj, plain, html_body = render_comment_result(state.data["pending_comment"][unique_id]["from"].split("_")[0], state.data["pending_comment"][unique_id]["content"], unique_id[-8:], False)
            send_email(f'{state.data["pending_comment"][unique_id]["from"].split("_")[1]}@qq.com', subj, plain, html_body)
        state.data["pending_comment"] = {}
    elif unique_id not in state.data["pending_comment"].keys():
        await jxyp.finish(f'编号错误', reply_message=True)
    elif src[0] == 'plapprove':
        state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments'].append(state.data["pending_comment"][unique_id]["content"])
        if len(state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments']) > 30:
            state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments'].pop(0)
        subj, plain, html_body = render_comment_result(state.data["pending_comment"][unique_id]["from"].split("_")[0], state.data["pending_comment"][unique_id]["content"], unique_id[-8:], True)
        send_email(f'{state.data["pending_comment"][unique_id]["from"].split("_")[1]}@qq.com', subj, plain, html_body)
        del state.data["pending_comment"][unique_id]
    elif src[0] == 'plreject':
        subj, plain, html_body = render_comment_result(state.data["pending_comment"][unique_id]["from"].split("_")[0], state.data["pending_comment"][unique_id]["content"], unique_id[-8:], False)
        send_email(f'{state.data["pending_comment"][unique_id]["from"].split("_")[1]}@qq.com', subj, plain, html_body)
        del state.data["pending_comment"][unique_id]
    await jxyp.finish('操作成功', reply_message=True)


@jbshenhe.handle()
async def _(bot: Bot, ev: MessageEvent):
    from ..base.matchers import jxyp
    src = str(ev.message).split()
    if len(src) != 2:
        await jxyp.finish('格式错误', reply_message=True)
    else:
        unique_id = src[1].strip()
    if src[0] == 'jbapprove' and unique_id == 'all':
        pd_jb = list(state.data["pending_jb"].keys())
        for unique_id in pd_jb:
            subj, plain, html_body = render_report_result(state.data["pending_jb"][unique_id]["jbr"].split("_")[0], unique_id[-8:], state.data["pending_jb"][unique_id]["unique_id"], True)
            send_email(f'{state.data["pending_jb"][unique_id]["jbr"].split("_")[1]}@qq.com', subj, plain, html_body)
            del state.data["pending_jb"][unique_id]
    elif src[0] == 'jbreject' and unique_id == 'all':
        for unique_id in state.data["pending_jb"].keys():
            subj, plain, html_body = render_report_result(state.data["pending_jb"][unique_id]["jbr"].split("_")[0], unique_id[-8:], state.data["pending_jb"][unique_id]["unique_id"], False)
            send_email(f'{state.data["pending_jb"][unique_id]["jbr"].split("_")[1]}@qq.com', subj, plain, html_body)
        state.data["pending_jb"] = {}
    elif unique_id not in state.data["pending_jb"].keys():
        await jxyp.finish(f'编号错误', reply_message=True)
    elif src[0] == 'jbapprove':
        subj, plain, html_body = render_report_result(state.data["pending_jb"][unique_id]["jbr"].split("_")[0], unique_id[-8:], state.data["pending_jb"][unique_id]["unique_id"], True)
        send_email(f'{state.data["pending_jb"][unique_id]["jbr"].split("_")[1]}@qq.com', subj, plain, html_body)
        del state.data["pending_jb"][unique_id]
    elif src[0] == 'jbreject':
        subj, plain, html_body = render_report_result(state.data["pending_jb"][unique_id]["jbr"].split("_")[0], unique_id[-8:], state.data["pending_jb"][unique_id]["unique_id"], False)
        send_email(f'{state.data["pending_jb"][unique_id]["jbr"].split("_")[1]}@qq.com', subj, plain, html_body)
        del state.data["pending_jb"][unique_id]
    await jxyp.finish('操作成功', reply_message=True)
