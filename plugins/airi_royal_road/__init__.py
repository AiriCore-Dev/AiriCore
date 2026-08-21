from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from .base.persistence import personal_store, world_store
from .base import matchers
from .handlers import adventure, settlement, status, vote


__plugin_meta__ = PluginMetadata(
    name="王道征途",
    description="Airi 的限时王道征途活动",
    usage="王道征途",
    type="application",
)

driver = get_driver()


@driver.on_startup
async def _on_startup():
    await personal_store.initialize({})
    await world_store.initialize({})
    await personal_store.load()
    await world_store.load()


@driver.on_shutdown
async def _on_shutdown():
    await personal_store.flush()
    await world_store.flush()
