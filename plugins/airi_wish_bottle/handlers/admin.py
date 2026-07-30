from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from nonebot import logger

from ..base import state
from ..base.matchers import btshenhe, plshenhe, jbshenhe, pdbt, pdpl, pdjb, superuser_debug
from ..base.helpers import generate_unique_id, send_email, nxcr, add_bottle, delete_bottle
from ..base.image_store import delete_image_refs, record_image_refs
from ..base.email_template import render_bottle_result, render_comment_result, render_report_result
from ..base.constants import MAX_COMMENTS_PER_BOTTLE


async def _approve_bottle(pending_key: str) -> None:
    pending = state.data.get("pending_bottles", {}).get(pending_key)
    if pending is None:
        return

    bottles = state.data.setdefault("bottles", {})
    target_id = pending_key
    existing = bottles.get(pending_key)
    if existing is not None and str(existing.get('owner_id')) != str(pending.get('owner_id')):
        target_id = pending_key
        while target_id in bottles:
            target_id = nxcr(target_id)
    old_active_refs = record_image_refs(bottles.get(target_id))

    try:
        add_bottle(
            target_id,
            pending.get("owner", ""),
            pending.get("owner_id", ""),
            pending.get("content", ""),
            pending.get("comments", []),
            pending.get("times", 0),
            pending.get("images", []),
            pending.get("segments", -1),
        )
    except Exception as e:
        logger.warning(f"心愿瓶过审写入失败 {pending_key}: {e}")
        return

    bottle = bottles[target_id]
    subj, plain, html_body = render_bottle_result(
        bottle["owner"], bottle["content"], target_id, True
    )
    send_email(f'{bottle["owner_id"]}@qq.com', subj, plain, html_body)
    state.data["pending_bottles"].pop(pending_key, None)
    await delete_image_refs(old_active_refs - record_image_refs(bottle))


@pdbt.handle()
async def _(bot: Bot, ev: MessageEvent):
    res = ''
    for unique_id in state.data.get('pending_bottles', {}).keys():
        res += f'ID：{unique_id}\n来源：{state.data["pending_bottles"][unique_id]["owner"]}_{state.data["pending_bottles"][unique_id]["owner_id"]}\n内容：{state.data["pending_bottles"][unique_id]["content"]}\n\n'
    res = res.strip()
    if not len(res): res = "暂无"
    await superuser_debug.finish(res, reply_message=True)


@pdpl.handle()
async def _(bot: Bot, ev: MessageEvent):
    res = ''
    for unique_id in state.data.get('pending_comment', {}).keys():
        res += f'评论来源ID：{state.data["pending_comment"][unique_id]["comment_to"]}\n评论人QQ：{state.data["pending_comment"][unique_id]["from"]}\n评论内容：{state.data["pending_comment"][unique_id]["content"]}\n\n'
    res = res.strip()
    if not len(res): res = "暂无"
    await superuser_debug.finish(res, reply_message=True)


@pdjb.handle()
async def _(bot: Bot, ev: MessageEvent):
    res = ''
    for unique_id in state.data.get('pending_jb', {}).keys():
        res += f'举报人：{state.data["pending_jb"][unique_id]["jbr"]}\n举报ID：{state.data["pending_jb"][unique_id]["unique_id"]}\n举报理由：{state.data["pending_jb"][unique_id]["comment"]}\n\n'
    res = res.strip()
    if not len(res): res = "暂无"
    await superuser_debug.finish(res, reply_message=True)


@btshenhe.handle()
async def _(bot: Bot, ev: MessageEvent):
    from ..base.matchers import jxyp
    src = str(ev.message).split()
    if len(src) != 2:
        await btshenhe.finish('格式错误', reply_message=True)
    else:
        unique_id = src[1].strip()
    if src[0] == 'btapprove' and unique_id == 'all':
        for pending_key in list(state.data["pending_bottles"].keys()):
            await _approve_bottle(pending_key)
    elif src[0] == 'btreject' and unique_id == 'all':
        for pending_key in list(state.data['pending_bottles'].keys()):
            pending = state.data["pending_bottles"][pending_key]
            refs = record_image_refs(pending)
            subj, plain, html_body = render_bottle_result(pending["owner"], pending["content"], pending_key, False)
            send_email(f'{pending["owner_id"]}@qq.com', subj, plain, html_body)
            state.data["pending_bottles"].pop(pending_key, None)
            await delete_image_refs(refs)
    elif unique_id not in state.data["pending_bottles"].keys():
        await btshenhe.finish(f'编号为{unique_id}的心愿瓶不存在！', reply_message=True)
    elif src[0] == 'btapprove':
        await _approve_bottle(unique_id)
    elif src[0] == 'btreject':
        pending = state.data["pending_bottles"][unique_id]
        refs = record_image_refs(pending)
        subj, plain, html_body = render_bottle_result(pending["owner"], pending["content"], unique_id, False)
        send_email(f'{pending["owner_id"]}@qq.com', subj, plain, html_body)
        del state.data["pending_bottles"][unique_id]
        await delete_image_refs(refs)
    await btshenhe.finish('操作成功', reply_message=True)


@plshenhe.handle()
async def _(bot: Bot, ev: MessageEvent):
    from ..base.matchers import jxyp
    src = str(ev.message).split()
    if len(src) != 2:
        await plshenhe.finish('格式错误', reply_message=True)
    else:
        unique_id = src[1].strip()
    if src[0] == 'plapprove' and unique_id == 'all':
        pd_pl = list(state.data["pending_comment"].keys())
        for unique_id in pd_pl:
            comment_to = state.data["pending_comment"][unique_id]["comment_to"]
            if comment_to not in state.data.get('bottles', {}):
                logger.warning(f"评论审核：目标瓶子 {comment_to} 不存在，跳过评论 {unique_id}")
                del state.data["pending_comment"][unique_id]
                continue
            state.data['bottles'][comment_to]['comments'].append(state.data["pending_comment"][unique_id]["content"])
            if len(state.data['bottles'][comment_to]['comments']) > MAX_COMMENTS_PER_BOTTLE:
                state.data['bottles'][comment_to]['comments'].pop(0)
            subj, plain, html_body = render_comment_result(state.data["pending_comment"][unique_id]["from"].rsplit("_", 1)[0], state.data["pending_comment"][unique_id]["content"], unique_id[-8:], True)
            send_email(f'{state.data["pending_comment"][unique_id]["from"].rsplit("_", 1)[1]}@qq.com', subj, plain, html_body)
            del state.data["pending_comment"][unique_id]
    elif src[0] == 'plreject' and unique_id == 'all':
        for unique_id in state.data["pending_comment"].keys():
            subj, plain, html_body = render_comment_result(state.data["pending_comment"][unique_id]["from"].rsplit("_", 1)[0], state.data["pending_comment"][unique_id]["content"], unique_id[-8:], False)
            send_email(f'{state.data["pending_comment"][unique_id]["from"].rsplit("_", 1)[1]}@qq.com', subj, plain, html_body)
        state.data["pending_comment"] = {}
    elif unique_id not in state.data["pending_comment"].keys():
        await plshenhe.finish(f'编号错误', reply_message=True)
    elif src[0] == 'plapprove':
        comment_to = state.data["pending_comment"][unique_id]["comment_to"]
        if comment_to not in state.data.get('bottles', {}):
            logger.warning(f"评论审核：目标瓶子 {comment_to} 不存在，已删除评论 {unique_id}")
            del state.data["pending_comment"][unique_id]
            await plshenhe.finish(f'目标心愿瓶已不存在，评论已删除', reply_message=True)
        state.data['bottles'][comment_to]['comments'].append(state.data["pending_comment"][unique_id]["content"])
        if len(state.data['bottles'][comment_to]['comments']) > MAX_COMMENTS_PER_BOTTLE:
            state.data['bottles'][comment_to]['comments'].pop(0)
        subj, plain, html_body = render_comment_result(state.data["pending_comment"][unique_id]["from"].rsplit("_", 1)[0], state.data["pending_comment"][unique_id]["content"], unique_id[-8:], True)
        send_email(f'{state.data["pending_comment"][unique_id]["from"].rsplit("_", 1)[1]}@qq.com', subj, plain, html_body)
        del state.data["pending_comment"][unique_id]
    elif src[0] == 'plreject':
        subj, plain, html_body = render_comment_result(state.data["pending_comment"][unique_id]["from"].rsplit("_", 1)[0], state.data["pending_comment"][unique_id]["content"], unique_id[-8:], False)
        send_email(f'{state.data["pending_comment"][unique_id]["from"].rsplit("_", 1)[1]}@qq.com', subj, plain, html_body)
        del state.data["pending_comment"][unique_id]
    await plshenhe.finish('操作成功', reply_message=True)


@jbshenhe.handle()
async def _(bot: Bot, ev: MessageEvent):
    from ..base.matchers import jxyp
    src = str(ev.message).split()
    if len(src) != 2:
        await jbshenhe.finish('格式错误', reply_message=True)
    else:
        unique_id = src[1].strip()
    if src[0] == 'jbapprove' and unique_id == 'all':
        pd_jb = list(state.data["pending_jb"].keys())
        for unique_id in pd_jb:
            target_bottle_id = state.data["pending_jb"][unique_id]["unique_id"]
            await delete_bottle(target_bottle_id)
            subj, plain, html_body = render_report_result(state.data["pending_jb"][unique_id]["jbr"].rsplit("_", 1)[0], unique_id[-8:], target_bottle_id, True)
            send_email(f'{state.data["pending_jb"][unique_id]["jbr"].rsplit("_", 1)[1]}@qq.com', subj, plain, html_body)
            del state.data["pending_jb"][unique_id]
    elif src[0] == 'jbreject' and unique_id == 'all':
        for unique_id in state.data["pending_jb"].keys():
            subj, plain, html_body = render_report_result(state.data["pending_jb"][unique_id]["jbr"].rsplit("_", 1)[0], unique_id[-8:], state.data["pending_jb"][unique_id]["unique_id"], False)
            send_email(f'{state.data["pending_jb"][unique_id]["jbr"].rsplit("_", 1)[1]}@qq.com', subj, plain, html_body)
        state.data["pending_jb"] = {}
    elif unique_id not in state.data["pending_jb"].keys():
        await jbshenhe.finish(f'编号错误', reply_message=True)
    elif src[0] == 'jbapprove':
        target_bottle_id = state.data["pending_jb"][unique_id]["unique_id"]
        await delete_bottle(target_bottle_id)
        subj, plain, html_body = render_report_result(state.data["pending_jb"][unique_id]["jbr"].rsplit("_", 1)[0], unique_id[-8:], target_bottle_id, True)
        send_email(f'{state.data["pending_jb"][unique_id]["jbr"].rsplit("_", 1)[1]}@qq.com', subj, plain, html_body)
        del state.data["pending_jb"][unique_id]
    elif src[0] == 'jbreject':
        subj, plain, html_body = render_report_result(state.data["pending_jb"][unique_id]["jbr"].rsplit("_", 1)[0], unique_id[-8:], state.data["pending_jb"][unique_id]["unique_id"], False)
        send_email(f'{state.data["pending_jb"][unique_id]["jbr"].rsplit("_", 1)[1]}@qq.com', subj, plain, html_body)
        del state.data["pending_jb"][unique_id]
    await jbshenhe.finish('操作成功', reply_message=True)
