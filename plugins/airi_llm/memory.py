import os
import time
import pickle
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from collections import deque
from dataclasses import dataclass, field, fields, MISSING
from typing import Any, Deque, Dict, List, Optional, Set

from . import llm_client
from .knowledge import KnowledgeEntry

logger = logging.getLogger("airi_llm")

CST = timezone(timedelta(hours=8))

DATA_DIR = os.path.join("data", "airi_llm")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.pk")
GROUP_DIR = os.path.join(DATA_DIR, "group")

RAW_CONTEXT_MAX = 60
DISTILL_TRIGGER_COUNT = 45
DISTILL_CHUNK = 20
DISTILL_MIN_NEW = 15
ROLLING_SUMMARY_MAX_CHARS = 150

MIN_ENTRIES_FOR_EXTRACTION = 12
ACTIVE_WINDOW_SECS = 2 * 3600
EXTRACTION_TOP_USERS = 5
USER_MIN_LINES = 3
INJECT_MEMORY_MAX_USERS = 8
GROUP_MEMORY_MAX_CHARS = 200
USER_MEMORY_MAX_CHARS = 120

MOOD_TTL_SECS = 180
MOOD_MIN_ENTRIES = 4
MOOD_ANALYZE_ENTRIES = 15
MOOD_EMA_ALPHA = 0.5

STYLE_TTL_SECS = 1800
STYLE_MIN_ENTRIES = 20
STYLE_ANALYZE_ENTRIES = 40
STYLE_MAX_CHARS = 100

BOT_STATE_TTL_SECS = 240
BOT_STATE_MIN_ENTRIES = 3
BOT_STATE_ANALYZE_ENTRIES = 10
BOT_MOOD_EMA_ALPHA = 0.4
BOT_AROUSAL_EMA_ALPHA = 0.4

MOOD_TOPIC_TTL_SECS = 300
MOOD_TOPIC_MIN_ENTRIES = 5
MOOD_TOPIC_ANALYZE_ENTRIES = 15

AFFINITY_MAX = 2.0
AFFINITY_MIN = -1.0
AFFINITY_DECAY_DAYS = 14
AFFINITY_DECAY_PER_DAY = 0.04

PENDING_CALLBACK_TTL_SECS = 86400 * 3
PENDING_CALLBACK_MAX_PER_USER = 3
PENDING_CALLBACK_TRIGGER_PROB = 0.30
PENDING_CALLBACK_MIN_LINES = 3

INACTIVE_GROUP_TTL_DAYS = 90
INACTIVE_USER_TTL_DAYS = 180
MAX_LOCK_DICT_SIZE = 500

SCHEMA_VERSION = 1


@dataclass
class ContextEntry:
    ts: float
    user_id: str
    nickname: str
    content: str
    is_self: bool = False


@dataclass
class PendingCallback:
    user_id: str
    snippet: str
    created_at: float


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
    pending_callbacks: List[PendingCallback] = field(default_factory=list)
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
    group_alias: str = ""
    notes: str = ""
    updated_at: float = 0.0
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
    ensure_dirs()

    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "rb") as f:
                loaded = pickle.load(f)
            if isinstance(loaded, LongTermStore):
                _normalize_dataclass(loaded)
                for um in loaded.users.values():
                    _normalize_dataclass(um)
                for gm in loaded.groups.values():
                    _normalize_dataclass(gm)
                state.long_term = loaded
            else:
                logger.warning("memory.pk 类型异常，重新初始化")
                state.long_term = LongTermStore()
        else:
            state.long_term = LongTermStore()
    except Exception as e:
        logger.error(f"加载长期记忆失败，重新初始化: {e}")
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
    for gid in dirty:
        try:
            await save_group(state, gid)
        except Exception as e:
            logger.warning(f"保存群 {gid} 上下文失败: {e}")
    try:
        await save_long_term(state)
    except Exception as e:
        logger.warning(f"保存长期记忆失败: {e}")

    await cleanup_inactive_data(state)


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


def _now_str() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def _md_cell(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _entries_table(entries: List[ContextEntry]) -> str:
    header = "| 时间 | 昵称 | 账号 | 内容 |\n| --- | --- | --- | --- |"
    rows = []
    for e in entries:
        nickname = "你" if e.is_self else _md_cell(e.nickname)
        uid = "" if e.is_self else _md_cell(e.user_id)
        rows.append(f"| {_fmt_time(e.ts)} | {nickname} | {uid} | {_md_cell(e.content)} |")
    return header + "\n" + "\n".join(rows)


def render_context(
    state: Any,
    gid: str,
    callback_snippet: Optional[str] = None,
    knowledge_snippets: Optional[List[str]] = None,
) -> str:
    ctx = get_ctx(state, gid)
    entries = list(ctx.entries)
    parts: List[str] = []

    gmem = state.long_term.groups.get(gid)
    if gmem and gmem.summary:
        parts.append(f"【关于这个群】\n{gmem.summary}")

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
            display_name = f"{alias}（{sys_name}）"
        else:
            display_name = sys_name
        line_parts = []
        if umem and umem.notes:
            line_parts.append(umem.notes)
        if umem:
            aff_tag = _affinity_tag(umem.affinity)
            if aff_tag:
                line_parts.append(f"（{aff_tag}）")
        if line_parts:
            mem_lines.append(f"{display_name}: {''.join(line_parts)}")
    if mem_lines:
        parts.append("【你对在场成员的印象】\n" + "\n".join(mem_lines))

    if ctx.rolling_summary:
        parts.append(f"【较早对话概要】\n{ctx.rolling_summary}")

    if ctx.active_topic:
        parts.append(
            f"【当前话题】\n群里正{ctx.active_topic}"
            "\n（你可以顺着这个话题聊，也可以自然地转移话题）"
        )

    if ctx.speaking_style:
        parts.append(
            "【这个群的说话风格】\n" + ctx.speaking_style +
            "\n（轻度贴合这个群的用词和语气，但不要刻意模仿或丢掉你自己的性格）"
        )

    bot_mood_desc = _bot_mood_desc(ctx.bot_mood)
    arousal_desc = _arousal_desc(ctx.bot_arousal)
    state_parts = []
    if bot_mood_desc:
        state_parts.append(bot_mood_desc)
    if arousal_desc:
        state_parts.append(arousal_desc)
    if state_parts:
        parts.append(
            "【你现在的状态】\n" + "；".join(state_parts) +
            "\n（让状态自然影响你的语气、回话长短和积极度，不要直接说出来）"
        )

    if callback_snippet:
        parts.append(
            f"【你忽然想起一件事】\n{callback_snippet}"
            "\n（如果时机合适，可以自然地提起这件事，不要生硬插入）"
        )

    if knowledge_snippets:
        parts.append(
            "【相关背景知识】\n" + "\n".join(f"- {s}" for s in knowledge_snippets) +
            "\n（这是你掌握的相关信息，回答时可以自然利用，不必完整引用）"
        )

    if entries:
        parts.append("【最近的群聊】\n" + _entries_table(entries))

    directive_parts = [f"当前时间：{_now_str()}。"]
    ctx_ref = get_ctx(state, gid) if state else None
    time_hint = _time_state_hint()
    length_hint = _length_hint(ctx_ref.bot_arousal if ctx_ref else 0.0)
    if time_hint:
        directive_parts.append(time_hint + "。")
    if length_hint:
        directive_parts.append(length_hint + "。")
    directive_parts.append("现在轮到你发言。")
    parts.append("".join(directive_parts))
    return "\n\n".join(parts)


def _bot_mood_desc(mood: float) -> str:
    if mood is None:
        return ""
    if mood >= 0.6:
        return "心情很好，轻快、想接话、带点小雀跃"
    if mood >= 0.2:
        return "心情不错，放松、愿意搭话"
    if mood > -0.2:
        return ""
    if mood > -0.6:
        return "有点提不起劲，回得更懒更短，兴致一般"
    return "情绪偏低，话少、冷淡、不太想接话"


def _arousal_desc(arousal: float) -> str:
    if arousal is None:
        return ""
    if arousal >= 0.6:
        return "精力充沛、话很多、反应快"
    if arousal >= 0.2:
        return "状态不错，比较活跃"
    if arousal > -0.2:
        return ""
    if arousal > -0.6:
        return "有点懒懒的，回复偏短"
    return "很疲，能不说就不说，说也只说关键词"


def _affinity_tag(affinity: float) -> str:
    if affinity is None:
        return ""
    if affinity >= 1.5:
        return "关系很好，信任感高"
    if affinity >= 0.8:
        return "比较熟，有好感"
    if affinity >= 0.3:
        return "印象不错"
    if affinity <= -0.6:
        return "有些反感，不太想搭理"
    if affinity <= -0.3:
        return "有点不对付"
    return ""


def _time_state_hint() -> str:
    from datetime import datetime
    h = datetime.now(CST).hour
    if 2 <= h < 6:
        return "现在深夜困极了，极不想开口"
    if 6 <= h < 9:
        return "刚睡醒，还有些迷糊"
    if 12 <= h < 14:
        return "饭后有点犯困，回复偏懒"
    if 22 <= h or h < 2:
        return "夜深了，话少一些"
    return ""


def _length_hint(arousal: float) -> str:
    if arousal is None:
        arousal = 0.0
    if arousal <= -0.5:
        return "现在没什么精力，只说最关键的，一两句即可"
    if arousal <= -0.2:
        return "状态一般，回复简短一点"
    if arousal >= 0.6:
        return ""
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
        for _ in range(min(DISTILL_CHUNK, len(ctx.entries))):
            ctx.entries.popleft()
        ctx.entries_since_summary = 0
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
    ctx.style_updated_at = now

    lock = _get_bg_lock(state, gid)
    if lock.locked():
        return
    async with lock:
        recent = list(ctx.entries)[-STYLE_ANALYZE_ENTRIES:]
        user_entries = [e for e in recent if not e.is_self]
        if len(user_entries) < STYLE_MIN_ENTRIES // 2:
            return
        convo = _render_entries_plain(user_entries)
        style = await llm_client.analyze_speaking_style(convo)
        if style:
            ctx.speaking_style = style[:STYLE_MAX_CHARS]
            state.dirty.add(gid)
            logger.info(f"群 {gid} 说话风格已刷新")


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
        return
    mood_val = result.get("mood")
    arousal_val = result.get("arousal")
    if mood_val is not None:
        ctx.bot_mood = round(BOT_MOOD_EMA_ALPHA * mood_val + (1 - BOT_MOOD_EMA_ALPHA) * ctx.bot_mood, 3)
    if arousal_val is not None:
        ctx.bot_arousal = round(BOT_AROUSAL_EMA_ALPHA * arousal_val + (1 - BOT_AROUSAL_EMA_ALPHA) * ctx.bot_arousal, 3)
    state.dirty.add(gid)


def pop_pending_callback(state: Any, gid: str, user_id: str) -> Optional[str]:
    import random as _random
    ctx = get_ctx(state, gid)
    now = time.time()
    ctx.pending_callbacks = [
        cb for cb in ctx.pending_callbacks
        if now - cb.created_at < PENDING_CALLBACK_TTL_SECS
    ]
    candidates = [cb for cb in ctx.pending_callbacks if cb.user_id == user_id]
    if not candidates:
        return None
    if _random.random() >= PENDING_CALLBACK_TRIGGER_PROB:
        return None
    chosen = _random.choice(candidates)
    ctx.pending_callbacks = [cb for cb in ctx.pending_callbacks if cb is not chosen]
    state.dirty.add(gid)
    return chosen.snippet


def _decay_affinity(umem: "UserMemory") -> None:
    now = time.time()
    if umem.affinity_updated_at <= 0:
        return
    days_elapsed = (now - umem.affinity_updated_at) / 86400
    if days_elapsed < 1:
        return
    decay = AFFINITY_DECAY_PER_DAY * days_elapsed
    if umem.affinity > 0:
        umem.affinity = max(0.0, umem.affinity - decay)
    elif umem.affinity < 0:
        umem.affinity = min(0.0, umem.affinity + decay)


def _get_lock(state: Any, gid: str) -> asyncio.Lock:
    locks = state.locks
    lock = locks.get(gid)
    if lock is None:
        lock = asyncio.Lock()
        locks[gid] = lock
        if len(locks) > MAX_LOCK_DICT_SIZE:
            to_remove = [k for k, v in locks.items() if not v.locked()][:len(locks) - MAX_LOCK_DICT_SIZE]
            for k in to_remove:
                locks.pop(k, None)
    return lock


def _get_bg_lock(state: Any, gid: str) -> asyncio.Lock:
    locks = state.bg_locks
    lock = locks.get(gid)
    if lock is None:
        lock = asyncio.Lock()
        locks[gid] = lock
        if len(locks) > MAX_LOCK_DICT_SIZE:
            to_remove = [k for k, v in locks.items() if not v.locked()][:len(locks) - MAX_LOCK_DICT_SIZE]
            for k in to_remove:
                locks.pop(k, None)
    return lock


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
        for gid in [g for g in d.keys() if g not in live_gids and not d[g].locked()]:
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
    g_sys = (
        "你在维护对一个群的长期印象。结合【已有印象】和【最近对话】，"
        f"更新这个群的印象（常聊话题、氛围、常客、群内的梗），不超过{GROUP_MEMORY_MAX_CHARS}字。"
        "没有新信息就基本保留原印象。"
        '严格返回 JSON：{"summary": "印象文本"}'
    )
    g_user = f"【已有印象】\n{gmem.summary or '（无）'}\n\n【最近对话】\n{convo}"
    g_res = await llm_client.call_llm_json(g_sys, g_user)
    if isinstance(g_res, dict):
        s = str(g_res.get("summary", "")).strip()
        if s:
            gmem.summary = s[:GROUP_MEMORY_MAX_CHARS]
            gmem.updated_at = time.time()
            state.long_term.groups[gid] = gmem

    counts: Dict[str, int] = {}
    names: Dict[str, str] = {}
    for e in entries:
        if e.is_self:
            continue
        counts[e.user_id] = counts.get(e.user_id, 0) + 1
        names[e.user_id] = e.nickname
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top = [uid for uid, c in top if c >= USER_MIN_LINES][:EXTRACTION_TOP_USERS]

    for uid in top:
        umem = state.long_term.users.get(uid) or UserMemory(user_id=uid)
        user_entries = [e for e in entries if e.user_id == uid]
        user_lines = _render_entries_plain(user_entries)
        char_name = _char_name(state)
        user_display = f"{names.get(uid, uid)}({uid})"

        _decay_affinity(umem)
        u_res = await llm_client.analyze_user_full(
            user_lines=user_lines,
            full_convo=convo,
            user_display=user_display,
            existing_notes=umem.notes,
            existing_alias=umem.group_alias,
            char_name=char_name,
        )
        if not isinstance(u_res, dict):
            continue

        notes = str(u_res.get("notes", "")).strip()
        alias = str(u_res.get("alias", "")).strip()
        if notes:
            umem.notes = notes[:USER_MEMORY_MAX_CHARS]
        if alias and alias != names.get(uid, uid):
            umem.group_alias = alias[:20]
        umem.nickname = names.get(uid, umem.nickname)
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

        callback = str(u_res.get("callback", "")).strip()
        if callback and len(user_entries) >= PENDING_CALLBACK_MIN_LINES:
            ctx = get_ctx(state, gid)
            ctx.pending_callbacks = [
                cb for cb in ctx.pending_callbacks if cb.user_id != uid or cb.snippet != callback
            ]
            ctx.pending_callbacks.append(PendingCallback(
                user_id=uid, snippet=callback, created_at=time.time()
            ))
            if len(ctx.pending_callbacks) > PENDING_CALLBACK_MAX_PER_USER * 10:
                ctx.pending_callbacks = ctx.pending_callbacks[-PENDING_CALLBACK_MAX_PER_USER * 10:]

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
