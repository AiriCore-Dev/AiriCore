from pathlib import Path

import nonebot
from nonebot import logger
from pydantic import BaseModel, Extra


class PluginConfig(BaseModel, extra=Extra.ignore):
    tarot_path: Path = Path(__file__).resolve().parent / "resource"


driver = nonebot.get_driver()
tarot_config: PluginConfig = PluginConfig.parse_obj(
    driver.config.dict(exclude_unset=True))


class ResourceError(Exception):

    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return self.msg

    __repr__ = __str__


class EventNotSupport(Exception):
    pass


@driver.on_startup
async def tarot_resource_check() -> None:
    if not tarot_config.tarot_path.is_dir():
        logger.warning(f"塔罗牌图片资源目录缺失：{tarot_config.tarot_path}")
        raise ResourceError("缺少必要资源：塔罗牌图片目录！")

    tarot_json_path: Path = Path(__file__).resolve().parent / "tarot.json"
    if not tarot_json_path.exists():
        logger.warning("塔罗牌文本资源缺失，请检查！")
        raise ResourceError("缺少必要资源：tarot.json！")
