from typing import Any, List, Optional

from utils import llm
from utils.observability import get_logger

logger = get_logger("airi_llm")

LLM_MAX_TOKENS = 8000
LLM_TEMPERATURE = 1.0
LLM_TOP_P = 0.9
LLM_FREQ_PENALTY = 0.3
LLM_PRESENCE_PENALTY = 0.2

BG_MAX_TOKENS = 4000
BG_TEMPERATURE = 0.3

_MODEL_DOWN = llm._MODEL_DOWN
MODEL_DOWN_TTL_SECS = llm.MODEL_DOWN_TTL_SECS


def _pick_model(img_b64_list: Optional[List[str]]) -> str:
    profile = llm.active_profile()
    return profile.chat_model if img_b64_list else profile.chat_text_model


def _model_chain(img_b64_list: Optional[List[str]]) -> List[str]:
    profile = llm.active_profile()
    primary = profile.chat_model if img_b64_list else profile.chat_text_model
    return llm.build_chain(primary, profile.chat_fallback)


def _mark_if_unavailable(model: str, err: Exception) -> bool:
    return llm.mark_if_unavailable(model, err)


def _log_attempt_failed(model: str, chain: List[str], idx: int, err: Exception) -> None:
    llm.log_attempt_failed(model, chain, idx, err, "airi_llm")

async def call_llm(
    system_prompt: str,
    user_input: str,
    img_b64_list: Optional[List[str]] = None,
) -> str:
    return await llm.call_chat(system_prompt, user_input, img_b64_list)


async def call_llm_json(
    system_prompt: str,
    user_input: str,
    img_b64_list: Optional[List[str]] = None,
) -> Optional[Any]:
    return await llm.call_structured(system_prompt, user_input, img_b64_list)


def normalize_dialogue_result(result: Any) -> Optional[dict]:
    if not isinstance(result, dict) or not isinstance(result.get("addressed"), bool):
        return None
    addressed_reply = result.get("addressed_reply")
    passive_reply = result.get("passive_reply")
    if not isinstance(addressed_reply, str) or not isinstance(passive_reply, str):
        return None

    def normalize_reply_to(value: Any) -> Optional[str]:
        if value is None:
            return ""
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, str):
            return value.strip()
        return None

    addressed_reply_to = normalize_reply_to(result.get("addressed_reply_to", ""))
    passive_reply_to = normalize_reply_to(result.get("passive_reply_to", ""))
    if addressed_reply_to is None or passive_reply_to is None:
        return None
    used_context = result.get("used_context", [])
    if not isinstance(used_context, list):
        return None
    if any(not isinstance(item, str) for item in used_context):
        return None
    return {
        "addressed": result["addressed"],
        "addressed_reply": addressed_reply.strip()[:1000],
        "addressed_reply_to": addressed_reply_to,
        "passive_reply": passive_reply.strip()[:1000],
        "passive_reply_to": passive_reply_to,
        "used_context": [item.strip() for item in used_context if item.strip()],
    }


async def generate_dialogue(
    system_prompt: str,
    user_input: str,
    img_b64_list: Optional[List[str]] = None,
) -> Optional[dict]:
    result = await llm.call_structured(
        system_prompt,
        user_input,
        img_b64_list,
        usage_source=llm.SOURCE_CHAT,
    )
    return normalize_dialogue_result(result)


def _loads_lenient(text: str) -> Optional[Any]:
    return llm.loads_lenient(text)


def _clamp_valence(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(-1.0, min(1.0, f))


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
        "你是群聊风格分析器。分析这个群成员们的说话习惯特征，"
        "提炼语气风格、表达方式、标点习惯等整体特点，"
        "用简短的描述总结（不超过100字），只描述风格特征，不要列举具体常用词或口头禅。"
        '严格返回 JSON：{"style": "风格描述"}。只返回 JSON。'
    )
    result = await call_llm_json(system_prompt, f"【群聊记录】\n{convo_text}")
    if isinstance(result, dict):
        style = str(result.get("style", "")).strip()
        return style if style else None
    return None


async def extract_knowledge(convo_text: str, existing_summary: str) -> Optional[List[dict]]:
    if not convo_text.strip():
        return None
    system_prompt = (
        "你是知识提取助手。从群聊中提取对以后对话有价值的事实性知识，"
        "包括：群成员信息和关系、群规/活动规律、特定术语或缩写的含义、群内梗或典故、"
        "常提到的地点/人名/事件等。"
        "只提取客观事实，不提取主观观点、临时状态或纯闲聊。"
        "不要提取与『你』自己有关的信息（你的名字、别人怎么称呼你、别人对你的评价），"
        "也不要提取表格格式、时间戳这类无意义内容。"
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
        f"你是{char_name}，同时完成对一个群友的三项分析：\n"
        f"1. notes：更新你对TA的印象（性格/喜好/和你的关系），不超过{120}字，用第二人称；没新信息就原样返回。\n"
        "2. alias：从完整对话中观察群里其他人怎么叫TA，记录最常用的称呼；若与系统昵称相同或无特别称呼则留空。\n"
        f"3. affinity_delta：这段互动让{char_name}对TA的好感变化（-0.5 到 0.5），被夸/聊得开心为正，被怼/无视为负，普通为接近0。\n"
        '严格返回 JSON：{"notes": "...", "alias": "...", "affinity_delta": 数值}'
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
