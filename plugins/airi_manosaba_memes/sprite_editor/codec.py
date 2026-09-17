import json
import re
import threading
from pathlib import Path

from ..runtime import session_file
from .legacy_codec import LegacyRecipeCodec
from .state import (
    CHARACTER_PREFIXES,
    SHORT_CODE_PATTERN,
    SCHEMA_VERSION,
    SessionStore,
    SpriteRecipe,
    SpriteSessionData,
    StoredSprite,
    canonical_recipe,
    parse_ref,
)


_LOCK = threading.RLock()


class RecipeCodec:
    def __init__(self, catalog, prefab_loader, *, storage_path=None):
        self.catalog = catalog
        self.legacy = LegacyRecipeCodec(catalog, prefab_loader)
        self.storage_path = Path(storage_path) if storage_path is not None else None
        self._official = self._load_official()
        self._by_preset = {sprite.recipe.base_preset: code for code, sprite in self._official.items()}

    def _load_official(self):
        path = self.catalog.path.with_name("sprite_shortcodes.json")
        owners = {preset.id: character for character, presets in self.catalog.data.characters.items() for preset in presets}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload["schema_version"] != 1 or not isinstance(payload["presets"], dict):
                raise ValueError
            mapping = payload["presets"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ValueError("官方立绘短码目录无法读取，请恢复短码资源文件") from error
        entries = {}
        seen = set()
        for code, preset in mapping.items():
            if not isinstance(preset, str):
                raise ValueError("官方立绘短码目录无效")
            character = owners.get(preset)
            if (character is None or preset in seen or re.fullmatch(SHORT_CODE_PATTERN, code) is None
                    or code[:-3] != CHARACTER_PREFIXES[character]):
                raise ValueError("官方立绘短码目录无效，请同步预设和短码资源")
            seen.add(preset)
            entries[code] = StoredSprite(character=character, recipe=SpriteRecipe(base_preset=preset))
        if seen != set(owners):
            raise ValueError("官方立绘短码目录缺少预设，请同步短码资源")
        return entries

    def _store(self):
        path = self.storage_path if self.storage_path is not None else session_file("sprite_shortcodes.json")
        return SessionStore(path)

    def _load_custom(self, store):
        if not store.path.exists():
            return SpriteSessionData()
        try:
            payload = json.loads(store.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
                raise ValueError
            if not isinstance(payload.get("sprites"), dict):
                raise ValueError
            data = SpriteSessionData.model_validate(payload)
            for code, sprite in data.sprites.items():
                if (re.fullmatch(SHORT_CODE_PATTERN, code) is None or code in self._official
                        or code[:-3] != CHARACTER_PREFIXES.get(sprite.character)
                        or sprite.recipe.base_preset not in self._by_preset
                        or self._official[self._by_preset[sprite.recipe.base_preset]].character != sprite.character):
                    raise ValueError
            return data
        except (OSError, ValueError, TypeError) as error:
            raise ValueError("自定义立绘短码记录无法读取，已保留原文件，请修复或恢复备份") from error

    def encode(self, character, recipe):
        canonical = canonical_recipe(recipe)
        code = self._by_preset.get(canonical.base_preset)
        if code is None or self._official[code].character != character:
            raise ValueError("角色与官方立绘预设不匹配")
        if not canonical.overrides:
            return code
        try:
            self.legacy.encode(character, canonical)
        except (ValueError, RuntimeError) as error:
            raise ValueError("立绘配方无效，无法生成短码") from error
        sprite = StoredSprite(character=character, recipe=canonical)
        with _LOCK:
            store = self._store()
            data = self._load_custom(store)
            for existing_code, existing in data.sprites.items():
                if existing == sprite:
                    return existing_code
            prefix = CHARACTER_PREFIXES[character]
            code = next((f"{prefix}{number:03d}" for number in range(1, 1000)
                         if f"{prefix}{number:03d}" not in self._official
                         and f"{prefix}{number:03d}" not in data.sprites), None)
            if code is None:
                raise ValueError("该角色的 999 个立绘短码已用满，无法保存新的组合；已有短码仍可使用")
            data.sprites[code] = sprite
            try:
                store._write_atomic(data.model_dump_json(indent=2))
            except OSError as error:
                raise ValueError("自定义立绘短码保存失败，请稍后重试") from error
            return code

    def decode(self, value):
        code = parse_ref(value)
        if code is None:
            return None
        if re.fullmatch(SHORT_CODE_PATTERN, code) is None:
            return self.legacy.decode(code)
        sprite = self._official.get(code)
        if sprite is None:
            with _LOCK:
                sprite = self._load_custom(self._store()).sprites.get(code)
        if sprite is None:
            return None
        return sprite.character, sprite.recipe.model_copy(deep=True)
