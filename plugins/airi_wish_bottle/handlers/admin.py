from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from ..base import state
from ..base.matchers import btshenhe, plshenhe, jbshenhe, pdbt, pdpl, pdjb, superuser_debug
from ..base.helpers import generate_unique_id, send_email, nxcr


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
            send_email(f'{state.data["bottles"][unique_id]["owner_id"]}@qq.com', f'您的心愿瓶{unique_id}已通过审核', f'尊敬的{state.data["bottles"][unique_id]["owner"]}：\n    您的心愿瓶“{state.data["bottles"][unique_id]["content"][:20]+("......" if len(state.data["bottles"][unique_id]["content"])>20 else "")}”已通过人工审核，编号为 {unique_id} ，感谢使用Airi心愿瓶。\n\n此致，\nAiriCore Dev.')
            del state.data["pending_bottles"][unique_id]
    elif src[0] == 'btreject' and unique_id == 'all':
        for unique_id in state.data['pending_bottles'].keys():
            send_email(f'{state.data["pending_bottles"][unique_id]["owner_id"]}@qq.com', f'您的心愿瓶{unique_id}未通过审核', f'尊敬的{state.data["pending_bottles"][unique_id]["owner"]}：\n    您的心愿瓶“{state.data["pending_bottles"][unique_id]["content"][:20]+("......" if len(state.data["pending_bottles"][unique_id]["content"])>20 else "")}”未通过人工审核。如果对审核结果有异议，可于收到该邮件发送邮件至saki@saki.ln.cn申请复核。\n\n此致，\nAiriCore Dev.')
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
        send_email(f'{state.data["bottles"][unique_id]["owner_id"]}@qq.com', f'您的心愿瓶{unique_id}已通过审核', f'尊敬的{state.data["bottles"][unique_id]["owner"]}：\n    您的心愿瓶“{state.data["bottles"][unique_id]["content"][:20]+("......" if len(state.data["bottles"][unique_id]["content"])>20 else "")}”已通过人工审核，编号为 {unique_id} ，感谢使用Airi心愿瓶。\n\n此致，\nAiriCore Dev.')
        del state.data["pending_bottles"][unique_id]
    elif src[0] == 'btreject':
        send_email(f'{state.data["pending_bottles"][unique_id]["owner_id"]}@qq.com', f'您的心愿瓶{unique_id}未通过审核', f'尊敬的{state.data["pending_bottles"][unique_id]["owner"]}：\n    您的心愿瓶“{state.data["pending_bottles"][unique_id]["content"][:20]+("......" if len(state.data["pending_bottles"][unique_id]["content"])>20 else "")}”未通过人工审核。如果对审核结果有异议，可于收到该邮件三日内发送邮件至saki@saki.ln.cn申请复核。\n\n此致，\nAiriCore Dev.')
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
            send_email(f'{state.data["pending_comment"][unique_id]["from"].split("_")[1]}@qq.com', f'您的评论{unique_id[-8:]}已通过审核', f'尊敬的{state.data["pending_comment"][unique_id]["from"].split("_")[0]}：\n    您的评论“{state.data["pending_comment"][unique_id]["content"]}”已通过人工审核，感谢使用Airi心愿瓶。\n\n此致，\nAiriCore Dev.')
            del state.data["pending_comment"][unique_id]
    elif src[0] == 'plreject' and unique_id == 'all':
        for unique_id in state.data["pending_comment"].keys():
            send_email(f'{state.data["pending_comment"][unique_id]["from"].split("_")[1]}@qq.com', f'您的评论{unique_id[-8:]}未通过审核', f'尊敬的{state.data["pending_comment"][unique_id]["from"].split("_")[0]}：\n    您的评论“{state.data["pending_comment"][unique_id]["content"]}”未通过人工审核。如果对审核结果有异议，可于收到该邮件三日内发送邮件至saki@saki.ln.cn申请复核。\n\n此致，\nAiriCore Dev.')
        state.data["pending_comment"] = {}
    elif unique_id not in state.data["pending_comment"].keys():
        await jxyp.finish(f'编号错误', reply_message=True)
    elif src[0] == 'plapprove':
        state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments'].append(state.data["pending_comment"][unique_id]["content"])
        if len(state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments']) > 30:
            state.data['bottles'][state.data["pending_comment"][unique_id]["comment_to"]]['comments'].pop(0)
        send_email(f'{state.data["pending_comment"][unique_id]["from"].split("_")[1]}@qq.com', f'您的评论{unique_id[-8:]}已通过审核', f'尊敬的{state.data["pending_comment"][unique_id]["from"].split("_")[0]}：\n    您的评论“{state.data["pending_comment"][unique_id]["content"]}”已通过人工审核，感谢使用Airi心愿瓶。\n\n此致，\nAiriCore Dev.')
        del state.data["pending_comment"][unique_id]
    elif src[0] == 'plreject':
        send_email(f'{state.data["pending_comment"][unique_id]["from"].split("_")[1]}@qq.com', f'您的评论{unique_id[-8:]}未通过审核', f'尊敬的{state.data["pending_comment"][unique_id]["from"].split("_")[0]}：\n    您的评论“{state.data["pending_comment"][unique_id]["content"]}”未通过人工审核。如果对审核结果有异议，可于收到该邮件三日内发送邮件至saki@saki.ln.cn申请复核。\n\n此致，\nAiriCore Dev.')
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
            send_email(f'{state.data["pending_jb"][unique_id]["jbr"].split("_")[1]}@qq.com', f'您的举报{unique_id[-8:]}已通过审核', f'尊敬的{state.data["pending_jb"][unique_id]["jbr"].split("_")[0]}：\n    您举报的编号为 {state.data["pending_jb"][unique_id]["unique_id"]} 的心愿瓶经核实，违规情况成立，目前开发团队已依规处理该心愿瓶。感谢您为AiriCore做出的贡献。\n    凭该邮件可申领自定义编号心愿瓶一个，请联系saki@saki.ln.cn。\n\n此致，\nAiriCore Dev.')
            del state.data["pending_jb"][unique_id]
    elif src[0] == 'jbreject' and unique_id == 'all':
        for unique_id in state.data["pending_jb"].keys():
            send_email(f'{state.data["pending_jb"][unique_id]["jbr"].split("_")[1]}@qq.com', f'您的举报{unique_id[-8:]}未通过审核', f'尊敬的{state.data["pending_jb"][unique_id]["jbr"].split("_")[0]}：\n    您举报的编号为 {state.data["pending_jb"][unique_id]["unique_id"]} 的心愿瓶经核实，未发现违规情况，请谅解。如果对审核结果有异议，可于收到该邮件三日内发送邮件至saki@saki.ln.cn申请复核。\n\n此致，\nAiriCore Dev.')
        state.data["pending_jb"] = {}
    elif unique_id not in state.data["pending_jb"].keys():
        await jxyp.finish(f'编号错误', reply_message=True)
    elif src[0] == 'jbapprove':
        send_email(f'{state.data["pending_jb"][unique_id]["jbr"].split("_")[1]}@qq.com', f'您的举报{unique_id[-8:]}已通过审核', f'尊敬的{state.data["pending_jb"][unique_id]["jbr"].split("_")[0]}：\n    您举报的编号为 {state.data["pending_jb"][unique_id]["unique_id"]} 的心愿瓶经核实，违规情况成立，目前开发团队已依规处理该心愿瓶。感谢您为AiriCore做出的贡献。\n    凭该邮件可申领自定义编号心愿瓶一个，请联系saki@saki.ln.cn。\n\n此致，\nAiriCore Dev.')
        del state.data["pending_jb"][unique_id]
    elif src[0] == 'jbreject':
        send_email(f'{state.data["pending_jb"][unique_id]["jbr"].split("_")[1]}@qq.com', f'您的举报{unique_id[-8:]}未通过审核', f'尊敬的{state.data["pending_jb"][unique_id]["jbr"].split("_")[0]}：\n    您举报的编号为 {state.data["pending_jb"][unique_id]["unique_id"]} 的心愿瓶经核实，未发现违规情况，请谅解。如果对审核结果有异议，可于收到该邮件三日内发送邮件至saki@saki.ln.cn申请复核。\n\n此致，\nAiriCore Dev.')
        del state.data["pending_jb"][unique_id]
    await jxyp.finish('操作成功', reply_message=True)
