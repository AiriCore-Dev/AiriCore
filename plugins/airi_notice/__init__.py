import datetime
from nonebot import on_message, get_driver, logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

gr_name = {}

driver = get_driver()
notification_account = str(getattr(driver.config, "notification_account", "") or "").strip()

query_tmxx_status = on_message(priority=1, block=False)


async def _group_name(bot: Bot, group_id: int) -> str:
    cache = gr_name.setdefault(bot.self_id, {})
    if group_id in cache:
        return cache[group_id]
    try:
        info = await bot.get_group_info(group_id=group_id)
        name = info.get("group_name") or str(group_id)
    except Exception:
        name = str(group_id)
    cache[group_id] = name
    return name


@query_tmxx_status.handle()
async def query_tmxx_status_func(bot: Bot, ev: MessageEvent):
    if not notification_account:
        return
    msg = str(ev.message)
    keywords = ['tmxx',f'[CQ:at,qq={notification_account}]',"田麻小溪","葡萄柚"]
    if not any(k in msg for k in keywords):
        return
    if not isinstance(ev, GroupMessageEvent):
        return
    try:
        cur_time = datetime.datetime.now()
        qq_id = str(ev.user_id)
        group_id = int(ev.group_id)
        try:
            user_nick = await bot.get_group_member_info(group_id=group_id, user_id=int(qq_id))
            user_nick = user_nick.get("card") or user_nick.get("nickname") or qq_id
        except Exception:
            user_nick = qq_id
        group_name = await _group_name(bot, group_id)
        body = msg.replace(f"[CQ:at,qq={notification_account}]", "@葡萄柚🍇")
        mesg = "新消息提醒\n时间: {}\n发送者: {}({})\n群: {}({})\n内容: {}".format(
            str(cur_time)[:-7], user_nick, qq_id, group_name, group_id, body
        )
        await bot.send_private_msg(user_id=int(notification_account), message=mesg)
    except Exception as e:
        logger.warning(f"消息提醒转发失败: {e}")
