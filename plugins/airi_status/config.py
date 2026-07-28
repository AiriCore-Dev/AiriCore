from pydantic import Field, BaseModel


class ScopedConfig(BaseModel):
    only_superuser: bool = Field(default=False)
    """是否只能由 SUPERUSER 触发指令"""
    to_me: bool = Field(default=True)
    """触发指令是否需要 @Bot"""


class Config(BaseModel):
    status: ScopedConfig = Field(default_factory=ScopedConfig)
    """Kawaii Status Config"""


def _load() -> ScopedConfig:
    try:
        import nonebot

        raw = getattr(nonebot.get_driver().config, "status", None)
        if isinstance(raw, ScopedConfig):
            return raw
        if isinstance(raw, dict):
            return ScopedConfig(**raw)
    except Exception:
        pass
    return ScopedConfig()


config: ScopedConfig = _load()
