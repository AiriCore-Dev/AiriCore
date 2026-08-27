import os
import re
import time
import pickle
import asyncio
from datetime import datetime, timezone, timedelta
from collections import deque
from dataclasses import dataclass, field, fields, MISSING
from typing import Any, Deque, Dict, List, Optional, Set

from . import llm_client
from .knowledge import KnowledgeEntry

from utils.observability import get_logger

logger = get_logger("airi_llm")

CST = timezone(timedelta(hours=8))

DATA_DIR = os.path.join("data", "airi_llm")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.pk")
GROUP_DIR = os.path.join(DATA_DIR, "group")

RAW_CONTEXT_MAX = 150
DISTILL_TRIGGER_COUNT = RAW_CONTEXT_MAX
DISTILL_CHUNK = RAW_CONTEXT_MAX
DISTILL_MIN_NEW = RAW_CONTEXT_MAX
DISTILL_KEEP_RECENT = 15
ROLLING_SUMMARY_MAX_CHARS = 150

MIN_ENTRIES_FOR_EXTRACTION = 30
ACTIVE_WINDOW_SECS = 2 * 3600
EXTRACTION_TOP_USERS = 5
USER_MIN_LINES = 3
INJECT_MEMORY_MAX_USERS = 8
GROUP_MEMORY_MAX_CHARS = 200
USER_MEMORY_MAX_CHARS = 120

MOOD_EMA_ALPHA = 0.5

STYLE_TTL_SECS = 27000
STYLE_MIN_ENTRIES = 20
STYLE_ANALYZE_ENTRIES = 40
STYLE_MAX_CHARS = 100

BOT_STATE_TTL_SECS = 3600
BOT_STATE_MIN_ENTRIES = 3
BOT_STATE_ANALYZE_ENTRIES = 10
BOT_MOOD_EMA_ALPHA = 0.4
BOT_AROUSAL_EMA_ALPHA = 0.4

MOOD_TOPIC_TTL_SECS = 4500
MOOD_TOPIC_MIN_ENTRIES = 5
MOOD_TOPIC_ANALYZE_ENTRIES = 15

AFFINITY_MAX = 2.0
AFFINITY_MIN = -1.0
AFFINITY_DECAY_DAYS = 14
AFFINITY_DECAY_PER_DAY = 0.04

RETRY_BACKOFF_SECS = 300

GROUP_STATE_TTL_SECS = 6 * 3600
GROUP_STATE_MIN_ENTRIES = 5
GROUP_STATE_ANALYZE_ENTRIES = 15

INACTIVE_GROUP_TTL_DAYS = 90
INACTIVE_USER_TTL_DAYS = 180
MAX_LOCK_DICT_SIZE = 500
RETRIEVAL_MAX_CANDIDATES = 16
RETRIEVAL_MAX_CONTENT_CHARS = 300

SCHEMA_VERSION = 1
_long_term_load_failed = False


@dataclass
class ContextEntry:
    ts: float
    user_id: str
    nickname: str
    content: str
    is_self: bool = False
    msg_id: Optional[str] = None
    reply_to_id: Optional[str] = None
    qq_nickname: Optional[str] = None


@dataclass
class GroupContext:
    entries: Deque[ContextEntry] = field(
        default_factory=lambda: deque(maxlen=RAW_CONTEXT_MAX)
    )
    rolling_summary: str = ""
    summary_updated_at: float = 0.0
    entries_since_summary: int = 0
    entries_since_extraction: int = 0
    last_activity_ts: float = 0.0
    mood: float = 0.0
    mood_topic_updated_at: float = 0.0
    speaking_style: str = ""
    style_updated_at: float = 0.0
    bot_mood: float = 0.0
    bot_arousal: float = 0.0
    bot_state_updated_at: float = 0.0
    active_topic: str = ""
    knowledge: List[KnowledgeEntry] = field(default_factory=list)
    knowledge_updated_at: float = 0.0
    knowledge_entry_count: int = 0

    def __post_init__(self):
        if not isinstance(self.entries, deque) or self.entries.maxlen != RAW_CONTEXT_MAX:
            self.entries = deque(self.entries, maxlen=RAW_CONTEXT_MAX)


@dataclass
class UserMemory:
    user_id: str
    nickname: str = ""
    card_name: str = ""
    group_alias: str = ""
    notes: str = ""
    updated_at: float = field(default_factory=time.time)
    affinity: float = 0.0
    affinity_updated_at: float = 0.0


@dataclass
class GroupMemory:
    group_id: str
    summary: str = ""
    updated_at: float = 0.0


@dataclass
class LongTermStore:
    users: Dict[str, UserMemory] = field(default_factory=dict)
    groups: Dict[str, GroupMemory] = field(default_factory=dict)
    missed_mentions: List[dict] = field(default_factory=list)
    version: int = SCHEMA_VERSION


def ensure_dirs() -> None:
    os.makedirs(GROUP_DIR, exist_ok=True)


def _normalize_dataclass(obj: Any) -> None:
    for f in fields(obj):
        if hasattr(obj, f.name):
            continue
        if f.default is not MISSING:
            setattr(obj, f.name, f.default)
        elif f.default_factory is not MISSING:
            setattr(obj, f.name, f.default_factory())
        else:
            setattr(obj, f.name, None)


def _normalize_group_ctx(ctx: "GroupContext") -> None:
    _normalize_dataclass(ctx)
    if not isinstance(ctx.entries, deque) or ctx.entries.maxlen != RAW_CONTEXT_MAX:
        ctx.entries = deque(ctx.entries or [], maxlen=RAW_CONTEXT_MAX)


def _write_bytes(path: str, data: bytes) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def load_all(state: Any) -> None:
    global _long_term_load_failed
    ensure_dirs()

    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "rb") as f:
                loaded = pickle.load(f)
            if isinstance(loaded, LongTermStore):
                _long_term_load_failed = False
                _normalize_dataclass(loaded)
                _now = time.time()
                for um in loaded.users.values():
                    _normalize_dataclass(um)
                    if not getattr(um, "updated_at", 0):
                        um.updated_at = _now
                for gm in loaded.groups.values():
                    _normalize_dataclass(gm)
                state.long_term = loaded
                if isinstance(getattr(loaded, "missed_mentions", None), list):
                    state.missed_mentions = [
                        m for m in loaded.missed_mentions if isinstance(m, dict)
                    ]
            else:
                logger.warning("memory.pk 类型异常，重新初始化")
                _long_term_load_failed = True
                state.long_term = LongTermStore()
        else:
            state.long_term = LongTermStore()
    except Exception as e:
        logger.error(f"加载长期记忆失败，重新初始化: {e}")
        _long_term_load_failed = True
        state.long_term = LongTermStore()

    state.group_ctx = {}
    try:
        for fname in os.listdir(GROUP_DIR):
            if not fname.endswith(".pk"):
                continue
            gid = fname[:-3]
            fpath = os.path.join(GROUP_DIR, fname)
            try:
                with open(fpath, "rb") as f:
                    ctx = pickle.load(f)
                if isinstance(ctx, GroupContext):
                    _normalize_group_ctx(ctx)
                    for e in ctx.entries:
                        _normalize_dataclass(e)
                    state.group_ctx[gid] = ctx
                else:
                    logger.warning(f"群上下文 {fname} 类型异常，跳过")
            except Exception as e:
                logger.warning(f"加载群上下文 {fname} 失败，跳过: {e}")
    except FileNotFoundError:
        pass

    logger.info(
        f"记忆加载完成：{len(state.long_term.users)} 用户 / "
        f"{len(state.long_term.groups)} 群印象 / {len(state.group_ctx)} 群上下文"
    )


async def save_long_term(state: Any) -> None:
    if _long_term_load_failed:
        logger.warning("长期记忆读取失败过，已跳过写入以保护原存档")
        return
    mm = getattr(state, "missed_mentions", None)
    if isinstance(mm, list):
        state.long_term.missed_mentions = list(mm)
    data = pickle.dumps(state.long_term)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write_bytes, MEMORY_FILE, data)


async def save_group(state: Any, gid: str) -> None:
    ctx = state.group_ctx.get(gid)
    if ctx is None:
        return
    data = pickle.dumps(ctx)
    loop = asyncio.get_event_loop()
    path = os.path.join(GROUP_DIR, f"{gid}.pk")
    await loop.run_in_executor(None, _write_bytes, path, data)


async def save_all(state: Any) -> None:
    ensure_dirs()
    dirty = set(getattr(state, "dirty", set()))
    state.dirty = set()
    failed: set = set()
    for gid in dirty:
        try:
            await save_group(state, gid)
        except Exception as e:
            logger.warning(f"保存群 {gid} 上下文失败: {e}")
            failed.add(gid)
    if failed:
        state.dirty.update(failed)
    try:
        await save_long_term(state)
    except Exception as e:
        logger.warning(f"保存长期记忆失败: {e}")


def get_ctx(state: Any, gid: str) -> GroupContext:
    ctx = state.group_ctx.get(gid)
    if ctx is None:
        ctx = GroupContext()
        state.group_ctx[gid] = ctx
    return ctx


def save_context_entry(state: Any, gid: str, entry: ContextEntry) -> None:
    ctx = get_ctx(state, gid)
    ctx.entries.append(entry)
    ctx.entries_since_summary += 1
    ctx.entries_since_extraction += 1
    ctx.last_activity_ts = entry.ts
    state.dirty.add(gid)


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, CST).strftime("%Y-%m-%d %H:%M:%S")


def _md_cell(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _entries_table(entries: List[ContextEntry]) -> str:
    id_map: Dict[str, ContextEntry] = {}
    for e in entries:
        if e.msg_id:
            id_map[e.msg_id] = e
    header = "| 消息ID | 时间 | 昵称 | 账号 | 内容 |\n| --- | --- | --- | --- | --- |"
    rows = []
    for e in entries:
        if e.is_self:
            nickname = "Airi已说"
        else:
            card = _md_cell(e.nickname)
            qq_nick = _md_cell(e.qq_nickname) if e.qq_nickname else ""
            if qq_nick and qq_nick != card:
                nickname = f"{card}（QQ：{qq_nick}）"
            else:
                nickname = card
        uid = "" if e.is_self else _md_cell(e.user_id)
        content = _md_cell(e.content)
        if e.reply_to_id:
            ref = id_map.get(e.reply_to_id)
            if ref:
                ref_nick = "Airi已说" if ref.is_self else ref.nickname
                ref_snip = ref.content[:20] + ("…" if len(ref.content) > 20 else "")
                content = f"[回复{ref_nick}：「{_md_cell(ref_snip)}」] {content}"
            else:
                content = f"[回复消息] {content}"
        mid = "" if e.is_self else _md_cell(e.msg_id or "")
        rows.append(f"| {mid} | {_fmt_time(e.ts)} | {nickname} | {uid} | {content} |")
    return header + "\n" + "\n".join(rows)


def replyable_msg_ids(state: Any, gid: str) -> Set[str]:
    ctx = get_ctx(state, gid)
    return {e.msg_id for e in ctx.entries if e.msg_id and not e.is_self}


def _retrieval_terms(text: str) -> Set[str]:
    terms: Set[str] = set()
    for token in re.findall(r"[0-9A-Za-z_]+|[\u4e00-\u9fff]{2,}", text.lower()):
        terms.add(token)
        if len(token) > 3 and all("\u4e00" <= char <= "\u9fff" for char in token):
            terms.update(token[index:index + 2] for index in range(len(token) - 1))
    return terms


def _retrieval_candidate(candidate_id: str, source: str, content: str, score: int = 0) -> dict:
    return {
        "id": candidate_id,
        "source": source,
        "content": str(content).strip()[:RETRIEVAL_MAX_CONTENT_CHARS],
        "score": score,
    }


def build_retrieval_candidates(
    state: Any,
    gid: str,
    query: str,
    user_id: str = "",
    exclude_msg_ids: Optional[Set[str]] = None,
) -> List[dict]:
    ctx = get_ctx(state, gid)
    query_terms = _retrieval_terms(query)
    excluded = exclude_msg_ids or set()
    candidates: List[dict] = []

    knowledge_pool = []
    for entry in ctx.knowledge:
        searchable = " ".join([entry.content, *(entry.tags or [])])
        score = len(query_terms & _retrieval_terms(searchable))
        knowledge_pool.append((score, entry.hit_count, entry.updated_at, entry))
    knowledge_pool.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    for score, hit_count, _, entry in knowledge_pool[:8]:
        candidates.append(_retrieval_candidate(
            f"knowledge:{entry.entry_id}", "knowledge", entry.content,
            score + min(hit_count, 3) + 3,
        ))

    recent_entries = [
        entry for entry in list(ctx.entries)[-12:]
        if not entry.msg_id or entry.msg_id not in excluded
    ]
    recent_user_ids = {entry.user_id for entry in recent_entries if not entry.is_self}
    for uid, umem in state.long_term.users.items():
        names = [umem.nickname, umem.card_name, umem.group_alias, umem.notes]
        searchable = " ".join(str(value or "") for value in names)
        score = len(query_terms & _retrieval_terms(searchable))
        if uid == user_id or uid in recent_user_ids or score:
            content = (
                f"昵称：{umem.nickname or uid}；群内称呼：{umem.group_alias or '无'}；"
                f"印象：{umem.notes or '无'}；关系：{_affinity_tag(_decayed_affinity(umem)) or '普通'}"
            )
            priority = 8 if uid == user_id else 4
            candidates.append(_retrieval_candidate(
                f"user_memory:{uid}", "user_memory", content, score + priority
            ))

    group_memory = state.long_term.groups.get(gid)
    if group_memory and group_memory.summary:
        score = len(query_terms & _retrieval_terms(group_memory.summary))
        candidates.append(_retrieval_candidate(f"group_memory:{gid}", "group_memory", group_memory.summary, score + 2))
    if ctx.rolling_summary:
        score = len(query_terms & _retrieval_terms(ctx.rolling_summary))
        candidates.append(_retrieval_candidate(f"rolling_summary:{gid}", "rolling_summary", ctx.rolling_summary, score + 2))

    for index, entry in enumerate(recent_entries):
        if entry.is_self:
            continue
        content = f"{entry.nickname}：{entry.content}"
        score = len(query_terms & _retrieval_terms(content))
        if entry.user_id == user_id:
            score += 6
        if entry.msg_id:
            candidate_id = f"recent_dialogue:{entry.msg_id}"
        else:
            candidate_id = f"recent_dialogue:{index}"
        candidates.append(_retrieval_candidate(candidate_id, "recent_dialogue", content, score + 5 + index))

    if ctx.active_topic:
        score = len(query_terms & _retrieval_terms(ctx.active_topic))
        candidates.append(_retrieval_candidate(f"active_topic:{gid}", "active_topic", ctx.active_topic, score + 1))
    if ctx.speaking_style:
        candidates.append(_retrieval_candidate(f"speaking_style:{gid}", "speaking_style", ctx.speaking_style, 0))
    bot_state = "；".join(filter(None, [_bot_mood_desc(ctx.bot_mood), _arousal_desc(ctx.bot_arousal)]))
    if bot_state:
        candidates.append(_retrieval_candidate(f"bot_state:{gid}", "bot_state", bot_state, 0))
    time_state = _time_state_hint()
    if time_state:
        candidates.append(_retrieval_candidate("time_state:current", "time_state", time_state, 0))

    candidates = [candidate for candidate in candidates if candidate["content"]]
    candidates.sort(key=lambda candidate: (candidate["score"], candidate["id"]), reverse=True)
    for candidate in candidates:
        candidate.pop("score", None)
    return candidates[:RETRIEVAL_MAX_CANDIDATES]


def render_context(
    state: Any,
    gid: str,
    knowledge_snippets: Optional[List[str]] = None,
    recall_snippet: Optional[str] = None,
    retrieval_candidates: Optional[List[dict]] = None,
    current_user_id: str = "",
    exclude_msg_ids: Optional[Set[str]] = None,
) -> str:
    ctx = get_ctx(state, gid)
    excluded = exclude_msg_ids or set()
    entries = [
        entry for entry in ctx.entries
        if not entry.msg_id or entry.msg_id not in excluded
    ]
    parts: List[str] = []
    background_parts: List[str] = []

    gmem = state.long_term.groups.get(gid)
    if gmem and gmem.summary:
        background_parts.append(f"群背景：{gmem.summary}")

    present: List[str] = []
    seen: Set[str] = set()
    for e in reversed(entries):
        if e.is_self or e.user_id in seen:
            continue
        seen.add(e.user_id)
        present.append(e.user_id)
        if len(present) >= INJECT_MEMORY_MAX_USERS:
            break
    mem_lines: List[str] = []
    for uid in present:
        umem = state.long_term.users.get(uid)
        sys_name = (umem.nickname if umem else None) or uid
        alias = (umem.group_alias if umem else "") or ""
        if alias and alias != sys_name:
            display_name = f"{alias}（{sys_name}）[{uid}]"
        else:
            display_name = f"{sys_name}[{uid}]"
        line_parts = []
        if umem and umem.notes:
            line_parts.append(umem.notes)
        if umem:
            aff_tag = _affinity_tag(_decayed_affinity(umem))
            if aff_tag:
                line_parts.append(aff_tag)
        if line_parts:
            mem_lines.append(f"{display_name}: {'；'.join(line_parts)}")
    if mem_lines:
        background_parts.append("成员信息：\n" + "\n".join(mem_lines))

    if ctx.rolling_summary:
        background_parts.append(f"较早记录：{ctx.rolling_summary}")
    if knowledge_snippets:
        background_parts.append("相关事实：" + "；".join(knowledge_snippets))
    if retrieval_candidates:
        candidate_lines = [
            f"[{item.get('id')}] {item.get('source')}: {item.get('content')}"
            for item in retrieval_candidates
            if item.get("id") and item.get("content")
        ]
        if candidate_lines:
            background_parts.append("候选背景（只在相关时使用）：\n" + "\n".join(candidate_lines))
    if background_parts:
        parts.append(
            "【只读背景，仅在当前消息直接相关时使用】\n"
            + "\n".join(background_parts)
        )

    if current_user_id:
        current_memory = state.long_term.users.get(current_user_id)
        current_name = (current_memory.nickname if current_memory else "") or current_user_id
        current_alias = current_memory.group_alias if current_memory else ""
        if current_alias and current_alias != current_name:
            current_name = f"{current_alias}（{current_name}）"
        parts.append(
            f"【当前发言者】{current_name}[{current_user_id}]；优先理解TA这次发言的具体意图和情绪"
        )

    expression_parts: List[str] = []
    if ctx.speaking_style:
        expression_parts.append(f"群内表达习惯：{ctx.speaking_style}")
    bot_mood_desc = _bot_mood_desc(ctx.bot_mood)
    arousal_desc = _arousal_desc(ctx.bot_arousal)
    if bot_mood_desc:
        expression_parts.append(bot_mood_desc)
    if arousal_desc:
        expression_parts.append(arousal_desc)
    time_hint = _time_state_hint()
    if time_hint:
        expression_parts.append(time_hint)
    if expression_parts:
        parts.append(
            "【只影响措辞，不得成为回复内容】\n"
            + "；".join(expression_parts)
        )

    if any(entry.is_self for entry in entries):
        parts.append(
            "【Airi已发送的历史回复】这些内容是已经发送过的内容，只用于了解上下文和避免重复，不是当前要回复的消息；除非对方明确追问或要求展开，不要重述其中的意思。"
        )

    if recall_snippet:
        parts.append("【待回应消息】\n" + recall_snippet)

    if entries:
        parts.append("【最近的群聊】\n" + _entries_table(entries))
        parts.append("【引用格式】要指明在回哪一条时，开头写 [回复:消息ID]，"
                     "消息ID 只能取自上表消息ID列；回最新那条或不需要指明时不写。")

    return "\n\n".join(parts)


def _bot_mood_desc(mood: float) -> str:
    if mood is None:
        return ""
    if mood >= 0.6:
        return "心情很好"
    if mood >= 0.2:
        return "心情不错"
    if mood > -0.2:
        return ""
    if mood > -0.6:
        return "心情低落"
    return "心情很低"


def _arousal_desc(arousal: float) -> str:
    if arousal is None:
        return ""
    if arousal >= 0.6:
        return "精力充沛"
    if arousal >= 0.2:
        return "精力活跃"
    if arousal > -0.2:
        return ""
    if arousal > -0.6:
        return "精力懒散"
    return "精力疲惫"


def _affinity_tag(affinity: float) -> str:
    if affinity is None:
        return ""
    if affinity >= 1.5:
        return "关系很好"
    if affinity >= 0.8:
        return "比较熟"
    if affinity >= 0.3:
        return "印象不错"
    if affinity <= -0.6:
        return "印象反感"
    if affinity <= -0.3:
        return "印象不佳"
    return ""


def _time_state_hint() -> str:
    from datetime import datetime
    h = datetime.now(CST).hour
    if 2 <= h < 6:
        return "深夜"
    if 6 <= h < 9:
        return "清晨"
    if 12 <= h < 14:
        return "午后"
    if 22 <= h or h < 2:
        return "夜晚"
    return ""


def _char_name(state: Any) -> str:
    return getattr(state, "char_name", "角色")


def _render_entries_plain(entries: List[ContextEntry]) -> str:
    return _entries_table(entries)


async def maybe_distill(state: Any, gid: str) -> None:
    ctx = get_ctx(state, gid)
    if len(ctx.entries) < DISTILL_TRIGGER_COUNT:
        return
    if ctx.entries_since_summary < DISTILL_MIN_NEW:
        return

    lock = _get_bg_lock(state, gid)
    if lock.locked():
        return
    async with lock:
        if len(ctx.entries) < DISTILL_TRIGGER_COUNT:
            return
        old = list(ctx.entries)[:DISTILL_CHUNK]
        if not old:
            return

        system_prompt = (
            "你在维护一个群聊的滚动记忆概要。把【已有概要】和【新的较早记录】"
            f"合并压缩成一段不超过{ROLLING_SUMMARY_MAX_CHARS}字的第三人称中文概要，"
            "保留谁做了什么、聊了什么话题、重要事实和情绪，丢弃寒暄和无意义内容。"
            '严格返回 JSON：{"summary": "概要文本"}'
        )
        user_input = (
            f"【已有概要】\n{ctx.rolling_summary or '（无）'}\n\n"
            f"【新的较早记录】\n{_render_entries_plain(old)}"
        )
        result = await llm_client.call_llm_json(system_prompt, user_input)
        if not isinstance(result, dict):
            logger.warning(f"群 {gid} 蒸馏失败，保留原始上下文")
            return
        summary = str(result.get("summary", "")).strip()
        if not summary:
            return

        ctx.rolling_summary = summary[:ROLLING_SUMMARY_MAX_CHARS]
        ctx.summary_updated_at = time.time()
        done = {id(e) for e in old}
        kept = old[-DISTILL_KEEP_RECENT:]
        new_entries = [e for e in ctx.entries if id(e) not in done]
        ctx.entries.clear()
        ctx.entries.extend(kept)
        ctx.entries.extend(new_entries)
        ctx.entries_since_summary = len(new_entries)
        state.dirty.add(gid)
        logger.info(f"群 {gid} 已蒸馏 {len(old)} 条为滚动概要")


async def maybe_refresh_mood_and_topic(state: Any, gid: str) -> None:
    ctx = get_ctx(state, gid)
    now = time.time()
    if now - ctx.mood_topic_updated_at < MOOD_TOPIC_TTL_SECS:
        return
    if len(ctx.entries) < MOOD_TOPIC_MIN_ENTRIES:
        return
    ctx.mood_topic_updated_at = now

    recent = list(ctx.entries)[-MOOD_TOPIC_ANALYZE_ENTRIES:]
    convo = _render_entries_plain(recent)
    result = await llm_client.analyze_mood_and_topic(convo)
    if result is None:
        ctx.mood_topic_updated_at = min(ctx.mood_topic_updated_at, now - MOOD_TOPIC_TTL_SECS + RETRY_BACKOFF_SECS)
        return
    mood_val = result.get("mood")
    if mood_val is not None:
        ctx.mood = round(MOOD_EMA_ALPHA * mood_val + (1 - MOOD_EMA_ALPHA) * ctx.mood, 3)
    topic = str(result.get("topic", "")).strip()
    ctx.active_topic = topic
    state.dirty.add(gid)


async def maybe_refresh_speaking_style(state: Any, gid: str) -> None:
    ctx = get_ctx(state, gid)
    now = time.time()
    if now - ctx.style_updated_at < STYLE_TTL_SECS:
        return
    if len(ctx.entries) < STYLE_MIN_ENTRIES:
        return
    recent = list(ctx.entries)[-STYLE_ANALYZE_ENTRIES:]
    user_entries = [e for e in recent if not e.is_self]
    if len(user_entries) < STYLE_MIN_ENTRIES // 2:
        return
    lock = _get_bg_lock(state, gid)
    if lock.locked():
        return
    ctx.style_updated_at = now
    async with lock:
        convo = _render_entries_plain(user_entries)
        style = await llm_client.analyze_speaking_style(convo)
        if style:
            ctx.speaking_style = style[:STYLE_MAX_CHARS]
            state.dirty.add(gid)
            logger.info(f"群 {gid} 说话风格已刷新")
        else:
            ctx.style_updated_at = min(ctx.style_updated_at, now - STYLE_TTL_SECS + RETRY_BACKOFF_SECS)


async def maybe_refresh_bot_state(state: Any, gid: str) -> None:
    ctx = get_ctx(state, gid)
    now = time.time()
    if now - ctx.bot_state_updated_at < BOT_STATE_TTL_SECS:
        return
    if len(ctx.entries) < BOT_STATE_MIN_ENTRIES:
        return
    ctx.bot_state_updated_at = now

    recent = list(ctx.entries)[-BOT_STATE_ANALYZE_ENTRIES:]
    convo = _render_entries_plain(recent)
    result = await llm_client.analyze_bot_state(convo, _char_name(state))
    if result is None:
        ctx.bot_state_updated_at = min(ctx.bot_state_updated_at, now - BOT_STATE_TTL_SECS + RETRY_BACKOFF_SECS)
        return
    mood_val = result.get("mood")
    arousal_val = result.get("arousal")
    if mood_val is not None:
        ctx.bot_mood = round(BOT_MOOD_EMA_ALPHA * mood_val + (1 - BOT_MOOD_EMA_ALPHA) * ctx.bot_mood, 3)
    if arousal_val is not None:
        ctx.bot_arousal = round(BOT_AROUSAL_EMA_ALPHA * arousal_val + (1 - BOT_AROUSAL_EMA_ALPHA) * ctx.bot_arousal, 3)
    state.dirty.add(gid)


async def maybe_refresh_group_state(state: Any, gid: str) -> None:
    ctx = get_ctx(state, gid)
    now = time.time()
    updated_at = max(ctx.mood_topic_updated_at, ctx.bot_state_updated_at)
    if now - updated_at < GROUP_STATE_TTL_SECS:
        return
    if len(ctx.entries) < GROUP_STATE_MIN_ENTRIES:
        return

    recent = list(ctx.entries)[-GROUP_STATE_ANALYZE_ENTRIES:]
    convo = _render_entries_plain(recent)
    ctx.mood_topic_updated_at = now
    ctx.bot_state_updated_at = now
    result = await llm_client.analyze_group_state(convo)
    if result is None:
        retry_at = now - GROUP_STATE_TTL_SECS + RETRY_BACKOFF_SECS
        ctx.mood_topic_updated_at = retry_at
        ctx.bot_state_updated_at = retry_at
        return

    mood_val = result.get("mood")
    if mood_val is not None:
        ctx.mood = round(MOOD_EMA_ALPHA * mood_val + (1 - MOOD_EMA_ALPHA) * ctx.mood, 3)
    topic = str(result.get("topic", "")).strip()
    ctx.active_topic = topic
    bot_mood = result.get("bot_mood")
    if bot_mood is not None:
        ctx.bot_mood = round(
            BOT_MOOD_EMA_ALPHA * bot_mood + (1 - BOT_MOOD_EMA_ALPHA) * ctx.bot_mood,
            3,
        )
    arousal = result.get("arousal")
    if arousal is not None:
        ctx.bot_arousal = round(
            BOT_AROUSAL_EMA_ALPHA * arousal + (1 - BOT_AROUSAL_EMA_ALPHA) * ctx.bot_arousal,
            3,
        )
    state.dirty.add(gid)


def _decayed_affinity(umem: "UserMemory") -> float:
    aff = umem.affinity or 0.0
    if umem.affinity_updated_at <= 0:
        return aff
    days_elapsed = (time.time() - umem.affinity_updated_at) / 86400
    if days_elapsed < 1:
        return aff
    decay = AFFINITY_DECAY_PER_DAY * days_elapsed
    if aff > 0:
        return max(0.0, aff - decay)
    if aff < 0:
        return min(0.0, aff + decay)
    return aff


def _decay_affinity(umem: "UserMemory") -> None:
    umem.affinity = round(_decayed_affinity(umem), 3)


def _lock_idle(lock: asyncio.Lock) -> bool:
    if lock.locked():
        return False
    waiters = getattr(lock, "_waiters", None)
    if waiters:
        return False
    return True


def _get_lock_from(locks: dict, gid: str) -> asyncio.Lock:
    lock = locks.get(gid)
    if lock is None:
        lock = asyncio.Lock()
        locks[gid] = lock
        if len(locks) > MAX_LOCK_DICT_SIZE:
            over = len(locks) - MAX_LOCK_DICT_SIZE
            to_remove = [k for k, v in locks.items() if k != gid and _lock_idle(v)][:over]
            for k in to_remove:
                locks.pop(k, None)
    return lock


def _get_lock(state: Any, gid: str) -> asyncio.Lock:
    return _get_lock_from(state.locks, gid)


def _get_bg_lock(state: Any, gid: str) -> asyncio.Lock:
    return _get_lock_from(state.bg_locks, gid)


async def cleanup_inactive_data(state: Any) -> None:
    now = time.time()
    inactive_group_cutoff = now - INACTIVE_GROUP_TTL_DAYS * 86400
    inactive_user_cutoff = now - INACTIVE_USER_TTL_DAYS * 86400

    removed_groups = 0
    for gid in list(state.group_ctx.keys()):
        ctx = state.group_ctx[gid]
        if ctx.last_activity_ts < inactive_group_cutoff:
            state.group_ctx.pop(gid, None)
            removed_groups += 1
            try:
                path = os.path.join(GROUP_DIR, f"{gid}.pk")
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    removed_users = 0
    for uid in list(state.long_term.users.keys()):
        umem = state.long_term.users[uid]
        if umem.updated_at < inactive_user_cutoff:
            state.long_term.users.pop(uid, None)
            removed_users += 1

    removed_group_mems = 0
    for gid in list(state.long_term.groups.keys()):
        gmem = state.long_term.groups[gid]
        if gmem.updated_at < inactive_group_cutoff:
            state.long_term.groups.pop(gid, None)
            removed_group_mems += 1

    live_gids = set(state.group_ctx.keys())
    for attr in ("passive_speaking_group_tamed", "last_speak_time_group", "negative_speaking_tokens"):
        d = getattr(state, attr, None)
        if not isinstance(d, dict):
            continue
        for gid in [g for g in d.keys() if g not in live_gids]:
            d.pop(gid, None)

    for attr in ("locks", "bg_locks"):
        d = getattr(state, attr, None)
        if not isinstance(d, dict):
            continue
        for gid in [g for g in d.keys() if g not in live_gids and _lock_idle(d[g])]:
            d.pop(gid, None)

    if removed_groups or removed_users or removed_group_mems:
        logger.info(
            f"内存清理：移除 {removed_groups} 个不活跃群上下文、"
            f"{removed_users} 个不活跃用户印象、{removed_group_mems} 个不活跃群印象"
        )


async def extraction(state: Any) -> None:
    now = time.time()
    for gid, ctx in list(state.group_ctx.items()):
        active = (
            ctx.entries_since_extraction >= MIN_ENTRIES_FOR_EXTRACTION
            and (now - ctx.last_activity_ts) < ACTIVE_WINDOW_SECS
        )
        if not active:
            continue
        lock = _get_bg_lock(state, gid)
        if lock.locked():
            continue
        async with lock:
            try:
                await _extract_one_group(state, gid, ctx)
                ctx.entries_since_extraction = 0
                state.dirty.add(gid)
            except Exception as e:
                logger.warning(f"群 {gid} 长期提炼失败: {e}")


async def _extract_one_group(state: Any, gid: str, ctx: GroupContext) -> None:
    entries = list(ctx.entries)
    if not entries:
        return
    convo = _render_entries_plain(entries)

    gmem = state.long_term.groups.get(gid) or GroupMemory(group_id=gid)
    counts: Dict[str, int] = {}
    names: Dict[str, str] = {}
    qq_names: Dict[str, str] = {}
    for e in entries:
        if e.is_self:
            continue
        counts[e.user_id] = counts.get(e.user_id, 0) + 1
        names[e.user_id] = e.nickname
        if e.qq_nickname:
            qq_names[e.user_id] = e.qq_nickname
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top = [uid for uid, c in top if c >= USER_MIN_LINES][:EXTRACTION_TOP_USERS]

    char_name = _char_name(state)
    prepared = []
    for uid in top:
        umem = state.long_term.users.get(uid) or UserMemory(user_id=uid)
        _decay_affinity(umem)
        user_entries = [e for e in entries if e.user_id == uid]
        prepared.append({
            "user_id": uid,
            "display": f"{names.get(uid, uid)}({uid})",
            "existing_notes": umem.notes,
            "existing_alias": umem.group_alias,
            "user_lines": _render_entries_plain(user_entries),
            "memory": umem,
        })

    analysis = await llm_client.analyze_group_memory(
        convo,
        gmem.summary,
        prepared,
        char_name,
    )

    if not isinstance(analysis, dict):
        return
    summary = str(analysis.get("group_summary", "")).strip()
    if summary:
        gmem.summary = summary[:GROUP_MEMORY_MAX_CHARS]
        gmem.updated_at = time.time()
        state.long_term.groups[gid] = gmem

    user_results = {
        str(item.get("user_id", "")): item
        for item in analysis.get("users", [])
        if isinstance(item, dict) and item.get("user_id")
    }
    for prepared_user in prepared:
        uid = prepared_user["user_id"]
        umem = prepared_user["memory"]
        u_res = user_results.get(uid)
        if not isinstance(u_res, dict):
            continue

        notes = str(u_res.get("notes", "")).strip()
        alias = str(u_res.get("alias", "")).strip()
        if notes:
            umem.notes = notes[:USER_MEMORY_MAX_CHARS]
        known_names = {names.get(uid, ""), qq_names.get(uid, ""), umem.nickname, umem.card_name}
        if alias and alias not in known_names:
            umem.group_alias = alias[:20]
        umem.card_name = names.get(uid, umem.card_name)
        umem.nickname = qq_names.get(uid) or umem.nickname or names.get(uid, "")
        umem.updated_at = time.time()

        try:
            aff_delta = float(u_res.get("affinity_delta", 0))
            aff_delta = max(-0.5, min(0.5, aff_delta))
            umem.affinity = round(
                max(AFFINITY_MIN, min(AFFINITY_MAX, umem.affinity + aff_delta)), 3
            )
            umem.affinity_updated_at = time.time()
        except (TypeError, ValueError):
            pass

        state.long_term.users[uid] = umem
        state.dirty.add(gid)


async def maybe_extract_knowledge(state: Any, gid: str) -> None:
    from . import knowledge as kb
    ctx = get_ctx(state, gid)
    await kb.extract_and_update(ctx, gid, state)


async def retrieve_knowledge(state: Any, gid: str, message_text: str) -> List[str]:
    from . import knowledge as kb
    ctx = get_ctx(state, gid)
    return await kb.retrieve_for_reply(ctx, gid, state, message_text)
