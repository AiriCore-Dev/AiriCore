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


async def analyze_speaking_style(convo_text: str) -> Optional[str]:
    if not convo_text.strip():
        return None
    system_prompt = (
        "你是群聊风格分析器。分析这个群成员们的说话习惯，"
        "提炼他们的用词特点、语气风格、常用口头禅或梗、标点习惯等，"
        "用简短的描述总结（不超过100字），只描述风格特征，不要评价好坏。"
        '严格返回 JSON：{"style": "风格描述"}。只返回 JSON。'
    )
    result = await call_llm_json(system_prompt, f"【群聊记录】\n{convo_text}")
    if isinstance(result, dict):
        style = str(result.get("style", "")).strip()
        return style if style else None
    return None


async def analyze_bot_mood(convo_text: str, char_name: str = "角色") -> Optional[float]:
    if not convo_text.strip():
        return None
    system_prompt = (
        f"你是{char_name}的心情分析器。阅读最近的对话（表格中'你'就是{char_name}自己），"
        f"根据上下文判断{char_name}此刻应该是什么心情：被夸奖、被关心、聊得开心就偏正面；"
        "被忽视、被怼、话题无聊、氛围冷清就偏负面；正常聊天是中性。"
        '严格返回 JSON：{"mood": 数值}，数值范围 -1 到 1，'
        "-1=很不高兴/无聊/冷淡，0=平常心，1=开心/有活力。只返回 JSON。"
    )
    result = await call_llm_json(system_prompt, f"【最近对话】\n{convo_text}")
    if isinstance(result, dict):
        return _clamp_valence(result.get("mood"))
    return None


async def analyze_active_topic(convo_text: str) -> Optional[str]:
    if not convo_text.strip():
        return None
    system_prompt = (
        "你是群聊话题提取器。阅读最近群聊，提炼当前正在聊的核心话题，"
        "用不超过15字的短语描述（如「在讨论游戏攻略」、「互相分享美食照片」）。"
        "如果没有明确话题或群聊已沉寂，返回空字符串。"
        '严格返回 JSON：{"topic": "话题描述或空字符串"}。只返回 JSON。'
    )
    result = await call_llm_json(system_prompt, f"【最近群聊】\n{convo_text}")
    if isinstance(result, dict):
        t = str(result.get("topic", "")).strip()
        return t if t else None
    return None


async def extract_pending_callback(user_lines: str, char_name: str = "角色") -> Optional[str]:
    if not user_lines.strip():
        return None
    system_prompt = (
        f"你是{char_name}，一个细心记事的人。阅读这个用户最近的发言，"
        "判断TA是否明确提到了某件'之后会发生''打算去做''等一下要做'的具体小事，"
        "例如今天要去某地、打算买某东西、下次会带某物等。"
        "如果有，用不超过20字第三人称记录这件事。如果没有，返回空字符串。"
        '严格返回 JSON：{"callback": "待记事项或空字符串"}。只返回 JSON。'
    )
    result = await call_llm_json(system_prompt, f"【用户发言】\n{user_lines}")
    if isinstance(result, dict):
        cb = str(result.get("callback", "")).strip()
        return cb if cb else None
    return None


async def analyze_affinity_delta(interaction_lines: str, char_name: str = "角色") -> Optional[float]:
    if not interaction_lines.strip():
        return None
    system_prompt = (
        f"你是{char_name}的好感度分析器。根据这段和某用户的最近互动，"
        f"判断这段互动会让{char_name}对TA的好感产生多大变化。"
        "被夸/聊得开心/被关心返回正数；被怼/无视/说粗话返回负数；普通聊天接近0。"
        '严格返回 JSON：{"delta": 数值}，范围 -0.5 到 0.5。只返回 JSON。'
    )
    result = await call_llm_json(system_prompt, f"【互动记录】\n{interaction_lines}")
    if isinstance(result, dict):
        try:
            v = float(result.get("delta", 0))
            return max(-0.5, min(0.5, v))
        except (TypeError, ValueError):
            return None
    return None


async def analyze_bot_arousal(convo_text: str, char_name: str = "角色") -> Optional[float]:
    if not convo_text.strip():
        return None
    system_prompt = (
        f"你是{char_name}的活跃度分析器。阅读最近的对话，"
        f"判断{char_name}现在的精力和话欲如何。"
        "话题有趣/被频繁点名/群里热闹返回高分；话题无聊/冷场/刚聊了很久返回低分。"
        '严格返回 JSON：{"arousal": 数值}，范围 -1 到 1，'
        "-1=很疲惫/不想说话，0=正常，1=精力充沛/很想聊。只返回 JSON。"
    )
    result = await call_llm_json(system_prompt, f"【最近对话】\n{convo_text}")
    if isinstance(result, dict):
        return _clamp_valence(result.get("arousal"))
    return None


async def extract_knowledge(convo_text: str, existing_summary: str) -> Optional[List[dict]]:
    if not convo_text.strip():
        return None
    system_prompt = (
        "你是知识提取助手。从群聊中提取对以后对话有价值的事实性知识，"
        "包括：群成员信息和关系、群规/活动规律、特定术语或缩写的含义、群内梗或典故、"
        "常提到的地点/人名/事件等。"
        "只提取客观事实，不提取主观观点、临时状态或纯闲聊。"
        "如果新信息与已有知识矛盾，用 action=update 给出修正；"
        "如果某条已有知识被明确否定，用 action=delete。"
        "无可提取时返回空列表。"
        '严格返回 JSON：{"items": [{"action": "add"|"update"|"delete", '
        '"content": "知识内容，不超过80字", '
        '"tags": ["关键词1",...最多5个], '
        '"entry_id": "仅update/delete时填写已有条目ID"}]}'
    )
    user_input = (
        f"【已有知识条目（供参考，勿重复添加）】\n{existing_summary or '（无）'}\n\n"
        f"【最新群聊记录】\n{convo_text}"
    )
    result = await call_llm_json(system_prompt, user_input)
    if isinstance(result, dict):
        items = result.get("items")
        if isinstance(items, list):
            return items
    return None


async def score_knowledge_relevance(query: str, candidates: List[str]) -> List[int]:
    if not candidates or not query.strip():
        return []
    n = len(candidates)
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(candidates))
    system_prompt = (
        "你是知识检索助手。判断下面哪些知识条目与查询内容相关，"
        "能帮助回答问题或提供有用背景信息。只选真正有帮助的。"
        f'严格返回 JSON：{{"relevant": [相关条目编号列表，从1开始，如[1,3]]}}，'
        "没有相关条目则返回空列表。只返回 JSON。"
    )
    user_input = f"【查询内容】{query}\n\n【知识条目】\n{numbered}"
    result = await call_llm_json(system_prompt, user_input)
    if isinstance(result, dict):
        raw = result.get("relevant")
        if isinstance(raw, list):
            return [int(i) - 1 for i in raw if isinstance(i, (int, float)) and 1 <= int(i) <= n]
    return []


async def analyze_bot_state(convo_text: str, char_name: str = "角色") -> Optional[dict]:
    if not convo_text.strip():
        return None
    system_prompt = (
        f"你是{char_name}的状态分析器。阅读最近的对话（表格中'你'就是{char_name}自己），"
        f"同时判断两件事：\n"
        f"1. {char_name}此刻的心情（mood）：被夸/被关心/聊得开心偏正面；被怼/冷场/无聊偏负面。\n"
        f"2. {char_name}此刻的精力/话欲（arousal）：话题有趣/被频繁提及/热闹偏高；无聊/冷场/刚聊很久偏低。\n"
        '严格返回 JSON：{"mood": 数值, "arousal": 数值}，两个数值范围均为 -1 到 1。只返回 JSON。'
    )
    result = await call_llm_json(system_prompt, f"【最近对话】\n{convo_text}")
    if isinstance(result, dict):
        mood = _clamp_valence(result.get("mood"))
        arousal = _clamp_valence(result.get("arousal"))
        if mood is not None or arousal is not None:
            return {"mood": mood, "arousal": arousal}
    return None


async def analyze_mood_and_topic(convo_text: str) -> Optional[dict]:
    if not convo_text.strip():
        return None
    system_prompt = (
        "你是群聊分析器。阅读最近群聊，同时完成两件事：\n"
        "1. 判断整体话题氛围的情绪倾向（mood）：活泼积极热闹偏高，消极沉重冷清偏低。\n"
        "2. 提炼当前正在聊的核心话题（topic）：不超过15字短语，没有明确话题则留空字符串。\n"
        '严格返回 JSON：{"mood": 数值, "topic": "话题描述或空字符串"}，mood 范围 -1 到 1。只返回 JSON。'
    )
    result = await call_llm_json(system_prompt, f"【最近群聊】\n{convo_text}")
    if isinstance(result, dict):
        mood = _clamp_valence(result.get("mood"))
        topic = str(result.get("topic", "")).strip()
        return {"mood": mood, "topic": topic}
    return None


async def analyze_user_full(
    user_lines: str,
    full_convo: str,
    user_display: str,
    existing_notes: str,
    existing_alias: str,
    char_name: str = "角色",
) -> Optional[dict]:
    if not user_lines.strip():
        return None
    system_prompt = (
        f"你是{char_name}，同时完成对一个群友的四项分析：\n"
        f"1. notes：更新你对TA的印象（性格/喜好/和你的关系），不超过{120}字，用第二人称；没新信息就原样返回。\n"
        "2. alias：从完整对话中观察群里其他人怎么叫TA，记录最常用的称呼；若与系统昵称相同或无特别称呼则留空。\n"
        f"3. affinity_delta：这段互动让{char_name}对TA的好感变化（-0.5 到 0.5），被夸/聊得开心为正，被怼/无视为负，普通为接近0。\n"
        "4. callback：TA是否明确提到了某件「之后会发生/打算做」的具体小事（不超过20字第三人称）；没有则留空。\n"
        '严格返回 JSON：{"notes": "...", "alias": "...", "affinity_delta": 数值, "callback": "..."}'
    )
    user_input = (
        f"【这个人】{user_display}\n"
        f"【已有印象】\n{existing_notes or '（无）'}\n"
        f"【已知称呼】{existing_alias or '（未知）'}\n\n"
        f"【TA的发言】\n{user_lines}\n\n"
        f"【完整对话（含别人对TA的称呼）】\n{full_convo}"
    )
    result = await call_llm_json(system_prompt, user_input)
    if isinstance(result, dict):
        return result
    return None

