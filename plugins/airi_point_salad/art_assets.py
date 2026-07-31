from pathlib import Path

from .models import Character

ASSET_DIR = Path(__file__).parent / "assets"
GENERATED_DIR = ASSET_DIR / "generated"
TITLE_PATH = GENERATED_DIR / "title.png"
FRONT_BASE_PATH = GENERATED_DIR / "front_base.png"
BACK_BASE_PATH = GENERATED_DIR / "back_base.png"
NAMEPLATE_PATH = GENERATED_DIR / "nameplate.png"


def portrait_path(character: Character) -> Path:
    return GENERATED_DIR / "portraits" / f"{character.value}.png"


def chibi_path(character: Character) -> Path:
    return GENERATED_DIR / "chibi" / f"{character.value}.png"
