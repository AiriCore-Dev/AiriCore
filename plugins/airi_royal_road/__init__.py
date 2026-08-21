from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from .base.persistence import personal_store, world_store
from .base.models import PersonalState, WorldState
from .base.state import all_personal, get_world, replace_personal, set_world
from .base import matchers
from .handlers import adventure, settlement, status, vote


__plugin_meta__ = PluginMetadata(
    name="王道征途",
    description="Airi 的限时王道征途活动",
    usage="王道征途",
    type="application",
)

try:
    driver = get_driver()
except ValueError:
    driver = None


if driver is not None:
    from . import scheduler

    @driver.on_startup
    async def _on_startup():
        await personal_store.initialize({})
        await world_store.initialize({})
        personal_payload = await personal_store.load()
        world_payload = await world_store.load()
        replace_personal({key: PersonalState.from_dict(value) for key, value in personal_payload.items()})
        if world_payload:
            set_world(WorldState.from_dict(world_payload))


    @driver.on_shutdown
    async def _on_shutdown():
        await personal_store.save({key: value.to_dict() for key, value in all_personal().items()})
        await world_store.save(get_world().to_dict())
