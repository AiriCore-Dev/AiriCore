import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from nonebot import get_driver

logger = logging.getLogger("airi_llm")

driver = get_driver()

LLM_MODEL_VISION = getattr(driver.config, "chat_llm_model", "")
LLM_MODEL_TEXT = getattr(driver.config, "chat_llm_model_text", "") or LLM_MODEL_VISION
LLM_MODEL = LLM_MODEL_VISION


def _pick_model(img_b64_list: Optional[List[str]]) -> str:
    return LLM_MODEL_VISION if img_b64_list else LLM_MODEL_TEXT


LLM_MAX_TOKENS = 8000
LLM_TEMPERATURE = 1.0
LLM_TOP_P = 0.9
LLM_FREQ_PENALTY = 0.3
LLM_PRESENCE_PENALTY = 0.2

BG_MAX_TOKENS = 4000
BG_TEMPERATURE = 0.3

client = AsyncOpenAI(
    api_key=getattr(driver.config, "llm_api_key", ""),
    base_url=getattr(driver.config, "llm_base_url", ""),
)


async def call_llm(
    system_prompt: str,
    user_input: str,
    img_b64_list: Optional[List[str]] = None,
) -> str:
    content: List[Dict[str, Any]] = [{"type": "text", "text": user_input}]
    for img_b64 in (img_b64_list or []):
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
        })

    try:
        completion = await client.chat.completions.create(
            model=_pick_model(img_b64_list),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            max_completion_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
            top_p=LLM_TOP_P,
            stream=False,
            stop=None,
            frequency_penalty=LLM_FREQ_PENALTY,
            presence_penalty=LLM_PRESENCE_PENALTY,
        )
        reply = json.loads(completion.model_dump_json())
        return (reply["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:
        logger.error(f"调用LLM失败: {e}")
        return ""


async def call_llm_json(
    system_prompt: str,
    user_input: str,
    img_b64_list: Optional[List[str]] = None,
) -> Optional[Any]:
    content: List[Dict[str, Any]] = [{"type": "text", "text": user_input}]
    for img_b64 in (img_b64_list or []):
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
        })
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]
    model = _pick_model(img_b64_list)

    text = await _create_json(model, messages, use_response_format=True)
    if text is None:
        text = await _create_json(model, messages, use_response_format=False)
    if not text:
        return None
    parsed = _loads_lenient(text)
    if parsed is None:
        logger.warning(f"结构化输出无法解析为JSON，原文前200字: {text[:200]!r}")
    return parsed


async def _create_json(model, messages, use_response_format):
    kwargs = dict(
        model=model,
        messages=messages,
        max_completion_tokens=BG_MAX_TOKENS,
        temperature=BG_TEMPERATURE,
        stream=False,
    )
    if use_response_format:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        completion = await client.chat.completions.create(**kwargs)
    except Exception as e:
        logger.warning(f"结构化LLM调用失败(response_format={use_response_format}): {e}")
        return None
    try:
        reply = json.loads(completion.model_dump_json())
        choice = reply["choices"][0]
        msg = choice.get("message", {})
        text = (msg.get("content") or "").strip()
        finish = choice.get("finish_reason")
        if not text:
            # 思维模型可能把内容放在 reasoning_content，或因 max_tokens 截断
            reasoning = (msg.get("reasoning_content") or "").strip()
            if reasoning:
                logger.info("content 为空，改用 reasoning_content 解析")
                return reasoning
            logger.warning(f"结构化输出内容为空 finish_reason={finish}（可能被max_tokens截断或被拒）")
            return None
        return text
    except Exception as e:
        logger.warning(f"解析结构化响应失败: {e}")
        return None


def _loads_lenient(text: str) -> Optional[Any]:
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
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                continue
    return None


async def caption_images(img_b64_list: List[str]) -> List[str]:
    n = len(img_b64_list)
    if n == 0:
        return []

    system_prompt = (
        "你是图片描述助手。逐张用不超过10个字的中文短语描述图片主要内容，"
        "只描述看到的东西，不要评价、不要编号、不要多余的话。"
        '严格返回 JSON：{"captions": ["描述1", "描述2", ...]}，'
        "数组长度必须和图片张数一致，顺序对应。"
    )
    user_input = f"共有 {n} 张图片，请依次描述。"

    result = await call_llm_json(system_prompt, user_input, img_b64_list)
    captions: List[str] = []
    if isinstance(result, dict):
        raw = result.get("captions")
        if isinstance(raw, list):
            captions = [str(c).strip() for c in raw if str(c).strip()]

    if len(captions) < n:
        captions += ["图片"] * (n - len(captions))
    return captions[:n]


def _clamp_valence(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(-1.0, min(1.0, f))


async def analyze_group_mood(convo_text: str) -> Optional[float]:
    if not convo_text.strip():
        return None
    system_prompt = (
        "你是群聊气氛分析器。阅读最近的群聊，判断当前整体话题氛围的情绪倾向。"
        "越活泼、积极、向上、热闹给越高的分；越悲观、消极、沉重、负面、冷清给越低的分。"
        '严格返回 JSON：{"mood": 数值}，数值范围 -1 到 1，'
        "-1=极度消极，0=中性平淡，1=非常活泼积极。只返回 JSON。"
    )
    result = await call_llm_json(system_prompt, f"【最近群聊】\n{convo_text}")
    if isinstance(result, dict):
        return _clamp_valence(result.get("mood"))
    return None


async def classify_reply_emotion(reply_text: str) -> Optional[float]:
    if not reply_text.strip():
        return None
    system_prompt = (
        "你是情绪打分器。给下面这句话所表达的情绪打一个分数。"
        "开心、兴奋、得意、温柔偏正面（越强越接近1）；"
        "生气、伤心、失落、无奈偏负面（越强越接近-1）；平静就是0。"
        '严格返回 JSON：{"emotion": 数值}，范围 -1 到 1。只返回 JSON。'
    )
    result = await call_llm_json(system_prompt, f"【这句话】{reply_text}")
    if isinstance(result, dict):
        return _clamp_valence(result.get("emotion"))
    return None


async def classify_image_emotions(img_b64_list: List[str]) -> List[Optional[float]]:
    n = len(img_b64_list)
    if n == 0:
        return []
    system_prompt = (
        "你是表情包情绪打分器。逐张判断这张表情包主要传达的情绪，打一个分数。"
        "开心、搞笑、可爱、得意等正面越强越接近1；"
        "生气、难过、委屈、无语等负面越强越接近-1；中性=0。"
        '严格返回 JSON：{"emotions": [数值, ...]}，'
        "数组长度必须和图片张数一致，顺序对应，每个数在 -1 到 1 之间。"
    )
    user_input = f"共有 {n} 张表情包，请依次打分。"
    result = await call_llm_json(system_prompt, user_input, img_b64_list)
    out: List[Optional[float]] = []
    if isinstance(result, dict):
        raw = result.get("emotions")
        if isinstance(raw, list):
            out = [_clamp_valence(v) for v in raw]
    if len(out) < n:
        out += [None] * (n - len(out))
    return out[:n]

