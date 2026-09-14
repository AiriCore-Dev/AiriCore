from dataclasses import dataclass
from pathlib import Path

from ..models import Character

PREFAB_ROOT = Path(__file__).resolve().parent.parent / "assets" / "prefabs"
REQUIRED_CHARACTERS = frozenset(character.value for character in Character)


def prefab_asset_root() -> Path:

    return PREFAB_ROOT


def _character_is_complete(path: Path) -> bool:
    return (
        (path / "character.json").is_file()
        and (path / "composition.json").is_file()
        and (path / "sprites").is_dir()
    )


@dataclass(frozen=True)
class PrefabAssetStatus:
    root: Path
    missing_characters: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.missing_characters


def prefab_asset_status(root: Path | None = None) -> PrefabAssetStatus:
    root = root or prefab_asset_root()
    missing = tuple(
        sorted(
            character
            for character in REQUIRED_CHARACTERS
            if not _character_is_complete(root / character)
        )
    )
    return PrefabAssetStatus(root=root, missing_characters=missing)


def prefab_unavailable_message(status: PrefabAssetStatus | None = None) -> str:
    status = status or prefab_asset_status()
    missing = "、".join(status.missing_characters)
    return (
        "立绘功能未启用：内置角色资源缺失或不完整。\n"
        f"缺少：{missing}\n"
        "请重新安装包含完整 assets/prefabs 资源目录的插件。\n"
        f"资源目录：{status.root}"
    )
