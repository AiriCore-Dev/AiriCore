import datetime
from nonebot import on_message, get_driver, logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent

from utils.onebot_query import event_nickname, group_name
from utils.messaging import get_notification_bot

driver = get_driver()
notification_account = str(getattr(driver.config, "notification_account", "") or "").strip()

query_tmxx_status = on_message(priority=1, block=False)

BLACKLIST_GROUP = [428328396]

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
        if group_id in BLACKLIST_GROUP:
            return
        user_nick = event_nickname(ev)
        current_group_name = await group_name(bot, group_id)
        body = msg.replace(f"[CQ:at,qq={notification_account}]", "@你")
        mesg = "📢 新消息提醒\n时间: {}\n发送者: {}({})\n群: {}({})\n内容: {}".format(
            str(cur_time)[:-7], user_nick, qq_id, current_group_name, group_id, body
        )
        notify_bot = get_notification_bot(bot)
        if notify_bot is None:
            logger.warning("消息提醒发送失败：没有可用的通知 Bot")
            return
        await notify_bot.send_private_msg(user_id=int(notification_account), message=mesg)
    except Exception as e:
        logger.warning(f"消息提醒转发失败: {e}")
