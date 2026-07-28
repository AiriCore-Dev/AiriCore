import time
from typing import Any, Callable, Dict, List, Optional

import nonebot

from utils.plugin_logger import get_logger

logger = get_logger("llm_fallback")

MODEL_DOWN_TTL_SECS = 600
_MODEL_DOWN_MARKERS = ("model_not_found", "no available channel", "无可用渠道")
_MODEL_DOWN: Dict[str, float] = {}


def _config(key, default=None):
    try:
        return getattr(nonebot.get_driver().config, key, default)
    except Exception:
        return default


def parse_model_list(raw) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(m).strip() for m in raw if str(m).strip()]


def build_chain(primary: str, fallback) -> List[str]:
    chain = [primary] if primary else []
    for m in parse_model_list(fallback):
        if m not in chain:
            chain.append(m)
    if not chain:
        return []
    now = time.time()
    _purge_down(now)
    alive = [m for m in chain if m not in _MODEL_DOWN]
    return alive or chain


def mark_if_unavailable(model: str, err: Exception) -> bool:
    text = str(err).lower()
    if any(k in text for k in _MODEL_DOWN_MARKERS):
        _MODEL_DOWN[model] = time.time()
        logger.warning(f"模型 {model} 上游不可用，{MODEL_DOWN_TTL_SECS // 60} 分钟内改用备用模型")
        return True
    return False


def log_attempt_failed(model: str, chain: List[str], idx: int, err: Exception, tag: str = "") -> None:
    mark_if_unavailable(model, err)
    prefix = f"[{tag}] " if tag else ""
    if idx + 1 < len(chain):
        logger.warning(f"{prefix}模型 {model} 调用失败，切换到备用模型 {chain[idx + 1]}：{err}")
    else:
        logger.warning(f"{prefix}模型 {model} 调用失败，已无备用模型：{err}")


def _purge_down(now: Optional[float] = None) -> None:
    now = now if now is not None else time.time()
    for m in [m for m, t in _MODEL_DOWN.items() if now - t > MODEL_DOWN_TTL_SECS]:
        _MODEL_DOWN.pop(m, None)


def down_snapshot() -> Dict[str, float]:
    now = time.time()
    _purge_down(now)
    return {m: MODEL_DOWN_TTL_SECS - (now - t) for m, t in _MODEL_DOWN.items()}


def other_model_chain() -> List[str]:
    return build_chain(
        _config("other_llm_model", "") or "",
        _config("other_llm_model_fallback", None),
    )


async def call_with_fallback(
    client,
    messages: List[Dict[str, Any]],
    chain: Optional[List[str]] = None,
    tag: str = "",
    validate: Optional[Callable[[str], Any]] = None,
    **kwargs,
) -> Any:
    models = chain if chain is not None else other_model_chain()
    if not models:
        logger.error(f"[{tag}] 未配置模型，无法调用")
        raise RuntimeError("未配置模型")
    last_err: Optional[Exception] = None
    prefix = f"[{tag}] " if tag else ""
    for idx, model in enumerate(models):
        try:
            completion = await client.chat.completions.create(
                model=model, messages=messages, **kwargs
            )
            text = (completion.choices[0].message.content or "").strip()
            if not text:
                raise RuntimeError("返回内容为空")
        except Exception as e:
            last_err = e
            log_attempt_failed(model, models, idx, e, tag)
            continue
        if validate is None:
            return text
        try:
            return validate(text)
        except Exception as e:
            last_err = e
            nxt = f"，切换到备用模型 {models[idx + 1]}" if idx + 1 < len(models) else "，已无备用模型"
            logger.warning(f"{prefix}模型 {model} 返回内容校验未通过{nxt}：{e}")
    logger.error(f"[{tag}] {len(models)} 个模型全部调用失败: {last_err}")
    raise last_err if last_err else RuntimeError("调用失败")
