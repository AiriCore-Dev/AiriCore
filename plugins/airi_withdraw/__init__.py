from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.log import logger
from utils.superuser_2fa import SUPERUSER_2FA

withdraw = on_fullmatch(
    ("撤回",),
    permission=SUPERUSER_2FA,
    priority=5,
    block=True,
)


@withdraw.handle()
async def handle_withdraw(bot: Bot, event: MessageEvent):
    if event.reply is None:
        await withdraw.finish("请引用一条需要撤回的消息后再发「撤回」。")

    try:
        await bot.delete_msg(message_id=event.reply.message_id)
    except ActionFailed as e:
        logger.opt(exception=e).warning(
            f"撤回被引用消息失败: message_id={event.reply.message_id}"
        )

    try:
        await bot.delete_msg(message_id=event.message_id)
    except ActionFailed as e:
        logger.opt(exception=e).warning(f"撤回指令消息失败: message_id={event.message_id}")
