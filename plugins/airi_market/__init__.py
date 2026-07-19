import os
import asyncio

import nonebot
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot

from .base import state
from .base.matchers import *
from .base.persistence import load_data, on_shutdown, save_data, timings, _send_single
from . import handlers


@state.driver.on_bot_connect
async def _on_bot_connect(bot: Bot):
    asyncio.create_task(_send_invite_if_new(bot))


async def _send_invite_if_new(bot: Bot):
    await asyncio.sleep(3)
    bot_qq = str(bot.self_id)
    notified = state.data.setdefault("bot_notified", [])
    if bot_qq in notified:
        return

    invite_path = os.path.join(state.TEMPLATES_DIR, "airicore_invite_email.html")
    if not os.path.isfile(invite_path):
        logger.warning(f"airi_market: invite email template not found: {invite_path}")
        return

    with open(invite_path, "r", encoding="utf-8") as f:
        html_body = f.read()

    subject = "诚邀您加入 AiriCore 开发者交流群"
    plain = (
        "诚邀您加入 AiriCore 开发者交流群。\n\n"
        "您的 Bot 已成功连接到 AiriCore 框架。\n"
        "加入开发交流群：https://qm.qq.com/q/34GPhJ30nC\n\n"
        "此致，\nAiriCore Dev."
    )
    dest = f"{bot_qq}@qq.com"

    result = await _send_single(dest, subject, plain, html_body)
    if result is True:
        notified.append(bot_qq)
        await save_data()
        logger.info(f"airi_market: sent invite email to {dest}")
    else:
        pending = state.data.setdefault("pending_sends", [])
        pending.append({"dest": dest, "subject": subject, "plain": plain, "html": html_body, "bot_qq": bot_qq})
        await save_data()
        logger.warning(f"airi_market: invite email to {dest} queued for retry")
