from nonebot import on_fullmatch
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.log import logger

# 管理员引用一条消息并发送“撤回”，机器人尝试撤回被引用的消息，
# 同时撤回管理员自己发送的“撤回”指令消息。
withdraw = on_fullmatch(
    ("撤回",),
    permission=SUPERUSER,
    priority=5,
    block=True,
)


@withdraw.handle()
async def handle_withdraw(bot: Bot, event: MessageEvent):
    if event.reply is None:
        return

    # 1. 撤回被引用的消息
    try:
        await bot.delete_msg(message_id=event.reply.message_id)
    except ActionFailed as e:
        logger.opt(exception=e).warning(
            f"撤回被引用消息失败: message_id={event.reply.message_id}"
        )

    # 2. 撤回管理员自己发送的“撤回”指令消息
    try:
        await bot.delete_msg(message_id=event.message_id)
    except ActionFailed as e:
        logger.opt(exception=e).warning(f"撤回指令消息失败: message_id={event.message_id}")
