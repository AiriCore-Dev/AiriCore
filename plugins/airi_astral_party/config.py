from dataclasses import dataclass
from pathlib import Path

import nonebot


@dataclass(frozen=True, slots=True)
class AstralConfig:
    backend_url: str
    backend_token: str
    backend_ca_file: str
    backend_timeout: float

    @property
    def enabled(self) -> bool:
        return bool(self.backend_url and self.backend_token)


def load_config() -> AstralConfig:
    source = nonebot.get_driver().config
    url = str(getattr(source, "astral_backend_url", "")).strip().rstrip("/")
    token = str(getattr(source, "astral_backend_token", "")).strip()
    ca_file = str(getattr(source, "astral_backend_ca_file", "")).strip()
    raw_timeout = getattr(source, "astral_backend_timeout", 30)
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError) as error:
        raise ValueError("astral_backend_timeout 必须是正数") from error
    if timeout <= 0:
        raise ValueError("astral_backend_timeout 必须是正数")
    if url and not url.lower().startswith("https://"):
        raise ValueError("astral_backend_url 必须使用 HTTPS")
    if ca_file and not Path(ca_file).is_file():
        raise ValueError("astral_backend_ca_file 不存在")
    return AstralConfig(url, token, ca_file, timeout)
