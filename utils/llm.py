from __future__ import annotations

import csv
import io
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger("utils.llm")
PROFILE_DIR = Path(__file__).resolve().parents[1] / "data" / "LLM"
_KNOWN_KEYS = {
    "base_url",
    "token",
    "chat_model",
    "chat_text_model",
    "chat_fallback",
    "other_model",
    "other_fallback",
}
_PROFILE_NAME_RE = re.compile(r"^[\w\u0080-\uffff .-]+$", re.UNICODE)


@dataclass(frozen=True)
class LLMProfile:
    base_url: str
    token: str
    chat_model: str
    chat_text_model: str
    chat_fallback: tuple[str, ...] = ()
    other_model: str = ""
    other_fallback: tuple[str, ...] = ()

    @property
    def api_key(self) -> str:
        return self.token


Profile = LLMProfile


def _profile_path(directory: str | Path | None = None) -> Path:
    return Path(directory) if directory is not None else PROFILE_DIR


def profile_directory(directory: str | Path | None = None) -> Path:
    return _profile_path(directory)


def validate_profile_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("配置档名称必须是字符串")
    value = name.strip()
    if value.endswith(".conf"):
        value = value[:-5]
    if not value or value in {".", ".."}:
        raise ValueError("配置档名称无效")
    if "/" in value or "\\" in value or not _PROFILE_NAME_RE.fullmatch(value):
        raise ValueError("配置档名称包含非法字符")
    return value


def _strip_comment(value: str) -> str:
    quote = ""
    for index, char in enumerate(value):
        if char in "'\"":
            if quote == char:
                quote = ""
            elif not quote:
                quote = char
        elif char in "#;" and not quote:
            return value[:index].rstrip()
    return value.strip()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _parse_list(value: str) -> tuple[str, ...]:
    value = _unquote(value.strip())
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip()
    if not value:
        return ()
    try:
        values = next(csv.reader(io.StringIO(value), skipinitialspace=True))
    except (csv.Error, StopIteration):
        values = value.split(",")
    return tuple(item for item in (_unquote(item).strip() for item in values) if item)


def parse_profile_text(text: str) -> LLMProfile:
    values: dict[str, str | tuple[str, ...]] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        if "=" not in line:
            raise ValueError(f"第 {line_number} 行缺少等号")
        key, raw_value = line.split("=", 1)
        key = key.strip().lower()
        raw_value = _strip_comment(raw_value)
        if key not in _KNOWN_KEYS:
            logger.warning("未知配置项: %s", key)
            continue
        if key.endswith("fallback"):
            values[key] = _parse_list(raw_value)
        else:
            values[key] = _unquote(raw_value).strip()
    required = ("base_url", "token", "chat_model")
    missing = [key for key in required if not str(values.get(key, "")).strip()]
    if missing:
        raise ValueError("缺少必填配置项: " + ", ".join(missing))
    return LLMProfile(
        base_url=str(values["base_url"]),
        token=str(values["token"]),
        chat_model=str(values["chat_model"]),
        chat_text_model=str(values.get("chat_text_model") or values["chat_model"]),
        chat_fallback=tuple(values.get("chat_fallback", ())),
        other_model=str(values.get("other_model", "")),
        other_fallback=tuple(values.get("other_fallback", ())),
    )


def _ensure_default(directory: Path) -> Path:
    default_path = directory / "default.conf"
    if not default_path.exists():
        example_path = directory / "example.conf"
        if not example_path.exists():
            raise FileNotFoundError("缺少 data/LLM/example.conf")
        directory.mkdir(parents=True, exist_ok=True)
        with example_path.open("rb") as source, default_path.open("wb") as target:
            target.write(source.read())
    return default_path


def profile_path(name: str, profile_dir: str | Path | None = None) -> Path:
    directory = _profile_path(profile_dir)
    return directory / f"{validate_profile_name(name)}.conf"


def load_profile(name: str = "default", profile_dir: str | Path | None = None) -> LLMProfile:
    directory = _profile_path(profile_dir)
    stem = validate_profile_name(name)
    path = _ensure_default(directory) if stem == "default" else profile_path(stem, profile_dir=directory)
    if not path.is_file():
        raise FileNotFoundError(f"找不到配置档: {stem}")
    return parse_profile_text(path.read_text(encoding="utf-8"))


def list_profiles(profile_dir: str | Path | None = None) -> list[str]:
    directory = _profile_path(profile_dir)
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.conf") if path.stem != "example")


def read_active_name(profile_dir: str | Path | None = None) -> str:
    path = _profile_path(profile_dir) / "active"
    if not path.exists():
        return "default"
    value = path.read_text(encoding="utf-8").strip()
    return validate_profile_name(value) if value else "default"


def write_active_name(name: str, profile_dir: str | Path | None = None) -> None:
    stem = validate_profile_name(name)
    directory = _profile_path(profile_dir)
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".active.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(stem + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / "active")
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 6:
        return "*" * len(token)
    return token[:4] + "*" * max(3, len(token) - 6) + token[-2:]


def inspect_profile(name: str = "default", profile_dir: str | Path | None = None) -> dict[str, object]:
    profile = load_profile(name, profile_dir=profile_dir)
    return {
        "name": validate_profile_name(name),
        "base_url": profile.base_url,
        "token": mask_token(profile.token),
        "chat_model": profile.chat_model,
        "chat_text_model": profile.chat_text_model,
        "chat_fallback": list(profile.chat_fallback),
        "other_model": profile.other_model,
        "other_fallback": list(profile.other_fallback),
    }


def active_profile(profile_dir: str | Path | None = None) -> LLMProfile:
    return load_profile(read_active_name(profile_dir=profile_dir), profile_dir=profile_dir)


def inspect_active(profile_dir: str | Path | None = None) -> dict[str, object]:
    return inspect_profile(read_active_name(profile_dir=profile_dir), profile_dir=profile_dir)
