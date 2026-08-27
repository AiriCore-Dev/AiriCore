from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import pickle
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from openai import AsyncOpenAI


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
MODEL_DOWN_TTL_SECS = 600
_MODEL_DOWN_MARKERS = ("model_not_found", "no available channel", "无可用渠道")
_MODEL_DOWN: dict[str, float] = {}
_MODEL_DOWN_SCOPE: dict[str, int] = {}
_CURRENT_GENERATION_SEQUENCE = 0

SOURCE_CHAT = "对话"
SOURCE_MECHANISM = "对话机制"
SOURCE_TURTLE_SOUP = "海龟汤"
SOURCE_WATER_METER = "水表"
SOURCE_WISH_BOTTLE = "心愿瓶审核"
SOURCE_RCON_TRANSLATION = "RCON翻译"
SOURCE_ORDER = (
    SOURCE_CHAT,
    SOURCE_MECHANISM,
    SOURCE_TURTLE_SOUP,
    SOURCE_WATER_METER,
    SOURCE_WISH_BOTTLE,
    SOURCE_RCON_TRANSLATION,
)

UTC_PLUS_8 = timezone(timedelta(hours=8))
_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "airi_llm"
_STATS_FILE = _DATA_DIR / "usage_stats.pk"
_FLUSH_INTERVAL = 15.0
_usage_lock = threading.Lock()
_stats: dict[str, dict[str, dict[str, int]]] = {}
_last_flush = 0.0
_dirty = False
_writer_stop = threading.Event()
_writer_thread: threading.Thread | None = None

CHAT_MAX_TOKENS = 8000
CHAT_TEMPERATURE = 1.0
CHAT_TOP_P = 0.9
CHAT_FREQUENCY_PENALTY = 0.3
CHAT_PRESENCE_PENALTY = 0.2
STRUCTURED_MAX_TOKENS = 4000
STRUCTURED_TEMPERATURE = 0.3


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


@dataclass
class _GenerationState:
    references: int = 0
    retired: bool = False
    closed: bool = False
    cooldown: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeGeneration:
    name: str
    profile: LLMProfile
    client: Any
    sequence: int
    _state: _GenerationState = field(default_factory=_GenerationState, compare=False, repr=False)

    @property
    def references(self) -> int:
        return self._state.references

    @property
    def retired(self) -> bool:
        return self._state.retired

    @property
    def closed(self) -> bool:
        return self._state.closed

    @property
    def cooldown(self) -> dict[str, float]:
        return self._state.cooldown


_active_generation: RuntimeGeneration | None = None
_runtime_profile_dir = PROFILE_DIR
_generation_sequence = 0
_retired_generations: dict[int, RuntimeGeneration] = {}
_switch_lock: asyncio.Lock | None = None
_switch_lock_loop: asyncio.AbstractEventLoop | None = None


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
    if profile_dir is None and _active_generation is not None:
        return _active_generation.profile
    return load_profile(read_active_name(profile_dir=profile_dir), profile_dir=profile_dir)


def inspect_active(profile_dir: str | Path | None = None) -> dict[str, object]:
    if profile_dir is None and _active_generation is not None:
        return _inspect_generation(_active_generation)
    return inspect_profile(read_active_name(profile_dir=profile_dir), profile_dir=profile_dir)


def _inspect_generation(generation: RuntimeGeneration) -> dict[str, object]:
    profile = generation.profile
    return {
        "name": generation.name,
        "base_url": profile.base_url,
        "token": mask_token(profile.token),
        "chat_model": profile.chat_model,
        "chat_text_model": profile.chat_text_model,
        "chat_fallback": list(profile.chat_fallback),
        "other_model": profile.other_model,
        "other_fallback": list(profile.other_fallback),
    }


def _get_switch_lock() -> asyncio.Lock:
    global _switch_lock, _switch_lock_loop
    loop = asyncio.get_running_loop()
    if _switch_lock is None or (_switch_lock_loop is not loop and not _switch_lock.locked()):
        _switch_lock = asyncio.Lock()
        _switch_lock_loop = loop
    return _switch_lock


def _new_generation(name: str, profile: LLMProfile) -> RuntimeGeneration:
    global _generation_sequence
    client = AsyncOpenAI(api_key=profile.token, base_url=profile.base_url)
    _generation_sequence += 1
    return RuntimeGeneration(name, profile, client, _generation_sequence)


async def _close_client(client: Any) -> None:
    try:
        result = client.close()
        if hasattr(result, "__await__"):
            await result
    except Exception as exc:
        logger.warning("LLM 客户端关闭失败: %s", exc)


async def _close_generation(generation: RuntimeGeneration) -> None:
    if generation._state.closed:
        return
    generation._state.closed = True
    _retired_generations.pop(generation.sequence, None)
    await _close_client(generation.client)


async def _retire_generation(generation: RuntimeGeneration | None) -> None:
    if generation is None or generation._state.retired:
        return
    generation._state.retired = True
    _retired_generations[generation.sequence] = generation
    if generation._state.references == 0:
        await _close_generation(generation)


class _GenerationLease:
    def __init__(self) -> None:
        self.generation: RuntimeGeneration | None = None

    async def __aenter__(self) -> RuntimeGeneration:
        generation = _active_generation
        if generation is None:
            raise RuntimeError("LLM 运行时尚未初始化")
        generation._state.references += 1
        self.generation = generation
        return generation

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        generation = self.generation
        self.generation = None
        if generation is None:
            return
        generation._state.references -= 1
        if generation._state.references < 0:
            generation._state.references = 0
        if generation._state.retired and generation._state.references == 0:
            await _close_generation(generation)


def acquire() -> _GenerationLease:
    return _GenerationLease()


async def initialize(profile_dir: str | Path | None = None) -> dict[str, object]:
    global _active_generation, _runtime_profile_dir, _CURRENT_GENERATION_SEQUENCE
    directory = _profile_path(profile_dir)
    async with _get_switch_lock():
        name = read_active_name(profile_dir=directory)
        profile = load_profile(name, profile_dir=directory)
        replacement = _new_generation(name, profile)
        previous = _active_generation
        _runtime_profile_dir = directory
        _active_generation = replacement
        _CURRENT_GENERATION_SEQUENCE = replacement.sequence
        _MODEL_DOWN.clear()
        _MODEL_DOWN_SCOPE.clear()
        await _retire_generation(previous)
        return _inspect_generation(replacement)


async def switch_profile(name: str, profile_dir: str | Path | None = None) -> dict[str, object]:
    global _active_generation, _runtime_profile_dir, _CURRENT_GENERATION_SEQUENCE
    async with _get_switch_lock():
        directory = _profile_path(profile_dir) if profile_dir is not None else _runtime_profile_dir
        stem = validate_profile_name(name)
        profile = load_profile(stem, profile_dir=directory)
        replacement = _new_generation(stem, profile)
        try:
            write_active_name(stem, profile_dir=directory)
        except Exception:
            await _close_generation(replacement)
            raise
        previous = _active_generation
        _runtime_profile_dir = directory
        _active_generation = replacement
        _CURRENT_GENERATION_SEQUENCE = replacement.sequence
        _MODEL_DOWN.clear()
        _MODEL_DOWN_SCOPE.clear()
        await _retire_generation(previous)
        return _inspect_generation(replacement)


def parse_model_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(model).strip() for model in raw if str(model).strip()]


def _purge_down(now: float | None = None, generation: int | None = None) -> None:
    current = now if now is not None else time.time()
    scope = _CURRENT_GENERATION_SEQUENCE if generation is None else generation
    expired = [
        model for model, started in _MODEL_DOWN.items()
        if _MODEL_DOWN_SCOPE.get(model, scope) != scope or current - started > MODEL_DOWN_TTL_SECS
    ]
    for model in expired:
        _MODEL_DOWN.pop(model, None)
        _MODEL_DOWN_SCOPE.pop(model, None)


def build_chain(primary: str, fallback: Any, generation: int | None = None) -> list[str]:
    chain = [primary] if primary else []
    for model in parse_model_list(fallback):
        if model not in chain:
            chain.append(model)
    if not chain:
        return []
    _purge_down(generation=generation)
    scope = _CURRENT_GENERATION_SEQUENCE if generation is None else generation
    available = [
        model for model in chain
        if model not in _MODEL_DOWN or _MODEL_DOWN_SCOPE.get(model, scope) != scope
    ]
    return available or chain


def mark_if_unavailable(model: str, error: Exception, generation: int | None = None) -> bool:
    text = str(error).lower()
    if not any(marker in text for marker in _MODEL_DOWN_MARKERS):
        return False
    scope = _CURRENT_GENERATION_SEQUENCE if generation is None else generation
    _MODEL_DOWN[model] = time.time()
    _MODEL_DOWN_SCOPE[model] = scope
    logger.warning("模型 %s 上游不可用，%s 分钟内改用备用模型", model, MODEL_DOWN_TTL_SECS // 60)
    return True


def log_attempt_failed(
    model: str,
    chain: list[str],
    index: int,
    error: Exception,
    tag: str = "",
    generation: int | None = None,
) -> None:
    mark_if_unavailable(model, error, generation=generation)
    prefix = f"[{tag}] " if tag else ""
    if index + 1 < len(chain):
        logger.warning("%s模型 %s 调用失败，切换到备用模型 %s：%s", prefix, model, chain[index + 1], error)
    else:
        logger.warning("%s模型 %s 调用失败，已无备用模型：%s", prefix, model, error)


def unavailable_model_snapshot() -> dict[str, float]:
    now = time.time()
    _purge_down(now)
    return {model: MODEL_DOWN_TTL_SECS - (now - started) for model, started in _MODEL_DOWN.items()}


def down_snapshot() -> dict[str, float]:
    return unavailable_model_snapshot()


def other_model_chain(profile: LLMProfile | None = None) -> list[str]:
    selected = profile or active_profile()
    return build_chain(selected.other_model, selected.other_fallback)


def _today() -> str:
    return datetime.now(UTC_PLUS_8).strftime("%Y-%m-%d")


def _usage_snapshot_unlocked() -> dict[str, dict[str, dict[str, int]]]:
    snapshot: dict[str, dict[str, dict[str, int]]] = {}
    for day, sources in _stats.items():
        if not isinstance(day, str) or not isinstance(sources, dict):
            continue
        clean_sources: dict[str, dict[str, int]] = {}
        for source, models in sources.items():
            if not isinstance(source, str) or not isinstance(models, dict):
                continue
            clean_models = {
                str(model): int(count)
                for model, count in models.items()
                if isinstance(model, str)
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
            }
            if clean_models:
                clean_sources[source] = clean_models
        if clean_sources:
            snapshot[day] = clean_sources
    return snapshot


def get_usage_snapshot() -> dict[str, dict[str, dict[str, int]]]:
    with _usage_lock:
        return _usage_snapshot_unlocked()


def get_snapshot() -> dict[str, dict[str, dict[str, int]]]:
    return get_usage_snapshot()


def record_success(source: str, model: str) -> None:
    global _dirty
    if not source or not model:
        return
    try:
        with _usage_lock:
            models = _stats.setdefault(_today(), {}).setdefault(str(source), {})
            model_name = str(model)
            models[model_name] = models.get(model_name, 0) + 1
            _dirty = True
    except Exception as exc:
        logger.warning("LLM 调用统计失败: %s", exc)


def _corrupt_usage_path() -> Path:
    return _STATS_FILE.with_name(f"{_STATS_FILE.name}.corrupt.{int(time.time())}")


def _load_usage() -> None:
    global _stats
    if not _STATS_FILE.is_file():
        _stats = {}
        return
    try:
        with _STATS_FILE.open("rb") as stream:
            loaded = pickle.load(stream)
        if not isinstance(loaded, dict):
            raise ValueError("统计文件结构无效")
        cleaned: dict[str, dict[str, dict[str, int]]] = {}
        for day, sources in loaded.items():
            if not isinstance(day, str) or not isinstance(sources, dict):
                continue
            clean_sources: dict[str, dict[str, int]] = {}
            for source, models in sources.items():
                if not isinstance(source, str) or not isinstance(models, dict):
                    continue
                clean_models: dict[str, int] = {}
                for model, count in models.items():
                    if not isinstance(model, str) or isinstance(count, bool):
                        continue
                    try:
                        value = int(count)
                    except (TypeError, ValueError, OverflowError):
                        continue
                    if value >= 0:
                        clean_models[model] = value
                if clean_models:
                    clean_sources[source] = clean_models
            if clean_sources:
                cleaned[day] = clean_sources
        _stats = cleaned
    except Exception as exc:
        try:
            _STATS_FILE.replace(_corrupt_usage_path())
        except Exception as move_error:
            logger.warning("LLM 调用统计损坏文件保留失败: %s", move_error)
        logger.warning("LLM 调用统计读取失败，已重置: %s", exc)
        _stats = {}


def _flush_usage(force: bool = False) -> None:
    global _dirty, _last_flush
    now = time.time()
    with _usage_lock:
        if not force and (not _dirty or now - _last_flush < _FLUSH_INTERVAL):
            return
        snapshot = _usage_snapshot_unlocked()
        _dirty = False
        _last_flush = now
    try:
        _STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = _STATS_FILE.with_suffix(_STATS_FILE.suffix + ".tmp")
        with temporary.open("wb") as stream:
            pickle.dump(snapshot, stream, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(_STATS_FILE)
    except Exception as exc:
        with _usage_lock:
            _dirty = True
        logger.warning("LLM 调用统计写入失败: %s", exc)


def flush_usage() -> None:
    _flush_usage(force=True)


def flush() -> None:
    flush_usage()


def _usage_writer_loop() -> None:
    while not _writer_stop.wait(_FLUSH_INTERVAL):
        try:
            _flush_usage()
        except Exception:
            continue


def _message_text(completion: Any) -> str:
    return (completion.choices[0].message.content or "").strip()


def _chat_content(user_input: str, images: list[str] | None) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": user_input}]
    for image in images or []:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})
    return content


async def call_chat(
    system_prompt: str,
    user_input: str,
    img_b64_list: list[str] | None = None,
) -> str:
    content = _chat_content(user_input, img_b64_list)
    last_error: Exception | None = None
    async with acquire() as generation:
        profile = generation.profile
        primary = profile.chat_model if img_b64_list else profile.chat_text_model
        chain = build_chain(primary, profile.chat_fallback, generation=generation.sequence)
        for index, model in enumerate(chain):
            try:
                completion = await generation.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ],
                    max_completion_tokens=CHAT_MAX_TOKENS,
                    temperature=CHAT_TEMPERATURE,
                    top_p=CHAT_TOP_P,
                    stream=False,
                    stop=None,
                    frequency_penalty=CHAT_FREQUENCY_PENALTY,
                    presence_penalty=CHAT_PRESENCE_PENALTY,
                )
                record_success(SOURCE_CHAT, model)
                text = _message_text(completion)
                if text:
                    return text
                last_error = RuntimeError("模型返回空内容")
                logger.warning("模型 %s 返回空内容，尝试下一个备用模型", model)
            except Exception as exc:
                last_error = exc
                log_attempt_failed(model, chain, index, exc, "airi_llm", generation=generation.sequence)
    logger.error("调用LLM失败，%s 个模型全部不可用: %s", len(chain), last_error)
    return ""


def loads_lenient(text: str) -> Any | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    stripped = text.strip().strip("`")
    if stripped.startswith("json"):
        stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass
    for opening, closing in (("{", "}"), ("[", "]")):
        start = text.find(opening)
        end = text.rfind(closing)
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                continue
    return None


async def _create_structured(
    generation: RuntimeGeneration,
    model: str,
    messages: list[dict[str, Any]],
    chain: list[str],
    index: int,
    use_response_format: bool,
    usage_source: str,
) -> str | None:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": STRUCTURED_MAX_TOKENS,
        "temperature": STRUCTURED_TEMPERATURE,
        "stream": False,
    }
    if use_response_format:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        completion = await generation.client.chat.completions.create(**kwargs)
        record_success(usage_source, model)
    except Exception as exc:
        if use_response_format:
            mark_if_unavailable(model, exc, generation=generation.sequence)
            logger.warning("结构化LLM调用失败(response_format=True): %s", exc)
        else:
            log_attempt_failed(model, chain, index, exc, "airi_llm", generation=generation.sequence)
        return None
    try:
        choice = completion.choices[0]
        message = choice.message
        text = (message.content or "").strip()
        if text:
            return text
        extra = getattr(message, "model_extra", None) or {}
        reasoning = (extra.get("reasoning_content") or "").strip()
        if reasoning:
            logger.info("content 为空，改用 reasoning_content 解析")
            return reasoning
        logger.warning("结构化输出内容为空 finish_reason=%s（可能被max_tokens截断或被拒）", choice.finish_reason)
        return None
    except Exception as exc:
        logger.warning("解析结构化响应失败: %s", exc)
        return None


async def call_structured(
    system_prompt: str,
    user_input: str,
    img_b64_list: list[str] | None = None,
    usage_source: str = SOURCE_MECHANISM,
) -> Any | None:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _chat_content(user_input, img_b64_list)},
    ]
    async with acquire() as generation:
        profile = generation.profile
        primary = profile.chat_model if img_b64_list else profile.chat_text_model
        chain = build_chain(primary, profile.chat_fallback, generation=generation.sequence)
        for index, model in enumerate(chain):
            text = await _create_structured(
                generation,
                model,
                messages,
                chain,
                index,
                True,
                usage_source,
            )
            if text is None:
                text = await _create_structured(
                    generation,
                    model,
                    messages,
                    chain,
                    index,
                    False,
                    usage_source,
                )
            if not text:
                continue
            parsed = loads_lenient(text)
            if parsed is not None:
                return parsed
            logger.warning("模型 %s 结构化输出无法解析为JSON，原文前200字: %r", model, text[:200])
    logger.error("结构化LLM调用失败，%s 个模型全部未拿到可用结果", len(chain))
    return None


async def call_auxiliary(
    messages: list[dict[str, Any]],
    chain: list[str] | None = None,
    tag: str = "",
    usage_source: str = "",
    validate: Callable[[str], Any] | None = None,
    **kwargs: Any,
) -> Any:
    async with acquire() as generation:
        models = list(chain) if chain is not None else build_chain(
            generation.profile.other_model,
            generation.profile.other_fallback,
            generation=generation.sequence,
        )
        if not models:
            logger.error("[%s] 未配置模型，无法调用", tag)
            raise RuntimeError("未配置模型")
        last_error: Exception | None = None
        prefix = f"[{tag}] " if tag else ""
        for index, model in enumerate(models):
            try:
                completion = await generation.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **kwargs,
                )
                if usage_source:
                    record_success(usage_source, model)
                text = _message_text(completion)
                if not text:
                    raise RuntimeError("返回内容为空")
            except Exception as exc:
                last_error = exc
                log_attempt_failed(model, models, index, exc, tag, generation=generation.sequence)
                continue
            if validate is None:
                return text
            try:
                return validate(text)
            except Exception as exc:
                last_error = exc
                if index + 1 < len(models):
                    suffix = f"，切换到备用模型 {models[index + 1]}"
                else:
                    suffix = "，已无备用模型"
                logger.warning("%s模型 %s 返回内容校验未通过%s：%s", prefix, model, suffix, exc)
        logger.error("[%s] %s 个模型全部调用失败: %s", tag, len(models), last_error)
        raise last_error if last_error else RuntimeError("调用失败")


async def call_with_fallback(
    messages: list[dict[str, Any]],
    chain: list[str] | None = None,
    tag: str = "",
    usage_source: str = "",
    validate: Callable[[str], Any] | None = None,
    **kwargs: Any,
) -> Any:
    return await call_auxiliary(
        messages,
        chain=chain,
        tag=tag,
        usage_source=usage_source,
        validate=validate,
        **kwargs,
    )


async def shutdown() -> None:
    global _active_generation
    _writer_stop.set()
    flush_usage()
    if _writer_thread is not None and _writer_thread.is_alive():
        _writer_thread.join(timeout=max(1.0, _FLUSH_INTERVAL))
    async with _get_switch_lock():
        generation = _active_generation
        _active_generation = None
        await _retire_generation(generation)
        closable = [item for item in _retired_generations.values() if item.references == 0]
        for item in closable:
            await _close_generation(item)


_load_usage()
_writer_thread = threading.Thread(target=_usage_writer_loop, daemon=True, name="llm_usage_writer")
_writer_thread.start()

try:
    from nonebot import get_driver as _get_driver

    @_get_driver().on_startup
    async def _initialize_on_startup() -> None:
        try:
            await initialize()
        except Exception:
            logger.exception("LLM 运行时初始化失败")
            raise

    @_get_driver().on_shutdown
    async def _shutdown_on_shutdown() -> None:
        try:
            await shutdown()
        except Exception:
            logger.exception("LLM 运行时关闭失败")
            raise
except Exception:
    logger.warning("LLM 运行时无法注册 NoneBot 生命周期钩子")
