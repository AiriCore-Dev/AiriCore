import re

from nonebot import get_driver, logger, on_regex
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment

from .client import AstralBackendClient, BackendError
from .config import load_config


_config = load_config()
_client: AstralBackendClient | None = AstralBackendClient(_config) if _config.enabled else None
astral = on_regex(r"^\s*astral(?:\s+|$)", flags=re.IGNORECASE, priority=12, block=True)


@get_driver().on_shutdown
async def _shutdown() -> None:
    return None


@astral.handle()
async def _handle(bot: Bot, event: Event) -> None:
    if _client is None:
        await astral.finish("吉星派对查询后端尚未配置")
    command = event.get_plaintext().strip()
    user_id = str(getattr(event, "user_id", ""))
    try:
        _, response = await _client.command(user_id, command)
    except BackendError as error:
        await astral.finish(str(error))
    except Exception as error:
        logger.warning("Astral 查询响应处理失败: %s", type(error).__name__)
        await astral.finish("查询后端返回了无效响应")
    if response["type"] == "text" or not response["images"]:
        await astral.finish(response["text"])
    try:
        message = Message([MessageSegment.image("base64://" + image) for image in response["images"]])
        await astral.send(message)
    except Exception as error:
        logger.warning("Astral 图片发送失败: %s", type(error).__name__)
        await astral.finish(response["text"])
