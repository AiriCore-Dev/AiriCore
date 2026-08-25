import os
import re
import time
import random
import base64
import asyncio
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Set, Tuple

import nonebot
from utils import cache as asset_cache
from utils.onebot_query import member_name
from utils.totp_2fa import totp_verify
from nonebot import (
    get_driver,
    on_message,
    require,
    on_startswith,
)
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageSegment,
    MessageEvent,
)

from . import memory
from . import llm_client
from . import knowledge

driver = get_driver()
from utils.observability import get_logger
from utils.network import download_public_bytes

logger = get_logger("airi_llm")

timings = require("nonebot_plugin_apscheduler").scheduler

SUPERUSERS = set(str(uid) for uid in driver.config.superusers)

NEGATIVE_SPEAK_TOKENS_INIT = 50
NEGATIVE_SPEAK_TOKENS_DEDUCT = 5
ADDRESSED_TOKENS_BONUS = 2

BASE_SPEAK_PROB = 1 / 120
REPLY_MENTION_PROB = 0.4
ADDRESSED_PROB = 0.9
HARD_COOLDOWN_SECS = 25
MOMENTUM_WINDOW_SECS = 150
MOMENTUM_MULT = 5.0
TRAFFIC_WINDOW_SECS = 90
TRAFFIC_REF_MSGS = 6
TRAFFIC_MULT_CAP = 2.0
MAX_UNADDRESSED_PROB = 0.15

PASSIVE_SPEAK_DELAY_RANGE = (301, 7200)
PASSIVE_SPEAK_TRIGGER_PROB = 1 / 400
PASSIVE_SPEAK_MIN_GAP = 300
AMBIENT_DIALOGUE_PROBE_PROB = 1 / 8

EMOJI_RANDOM_PROB = 1 / 10
FINAL_EMOJI_PROB = 1 / 5
EMOJI_MOOD_TOLERANCE = 0.35
EMOJI_MOOD_SOFTNESS = 0.25

TRANSITION_SPLIT_RE = re.compile(
    r'(?<=[^\s])(?=对了|话说|不过|然后|而且|还有|哦对|诶对|对哦|哦哦|另外|说起来|对吧|诶|哦)'
)
SEGMENT_MAX_LEN = 28
PARENTHETICAL_RE = re.compile(r"[(（](.+?)[)）]")
CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")

MISSED_MENTION_SAVE_PROB = 0.45
MISSED_MENTION_MIN_DELAY = 480
MISSED_MENTION_MAX_DELAY = 2400
MISSED_MENTION_EXPIRY = 4 * 3600
MISSED_MENTION_MAX_PER_GROUP = 2

TYPING_CHARS_PER_SEC_BASE = 3.5
TYPING_CHARS_PER_SEC_JITTER = 1.2
TYPING_MAX_SECS = 18.0
TYPING_MIN_SECS = 1.8
MESSAGE_BATCH_WAIT_SECS = 10.0

PROJECT_DIR = os.path.dirname(__file__)
ROLE_SETUP_FILE = os.path.join(PROJECT_DIR, "prompt.md")
EMOJI_DIR = os.path.join(PROJECT_DIR, "emoji")
EMOJI_MOOD_FILE = os.path.join(PROJECT_DIR, "emoji_moods.json")

CHAR_NAME = (getattr(driver.config, "airi_char_name", "") or "").strip() or "Airi"
_raw_aliases = getattr(driver.config, "airi_char_aliases", None)
if isinstance(_raw_aliases, str):
    _raw_aliases = [a.strip() for a in _raw_aliases.split(",")]
CHAR_ALIASES = [a.strip().lower() for a in (_raw_aliases or ["airi", "爱莉"]) if a and a.strip()]

_raw_excludes = getattr(driver.config, "airi_char_alias_excludes", None)
if isinstance(_raw_excludes, str):
    _raw_excludes = [w.strip() for w in _raw_excludes.split(",")]
ALIAS_EXCLUDES = [w.strip().lower() for w in (_raw_excludes or ["爱莉希雅"]) if w and w.strip()]

_ASCII_ALIAS_RE = {
    a: re.compile(r"(?<![0-9a-z])" + re.escape(a) + r"(?![0-9a-z])")
    for a in CHAR_ALIASES if a.isascii()
}


def _strip_chinese_parentheticals(text: str) -> str:
    return PARENTHETICAL_RE.sub(
        lambda match: "" if CHINESE_CHAR_RE.search(match.group(1)) else match.group(0),
        text,
    )


def _alias_mentioned(text: str) -> bool:
    low = text.lower()
    for ex in ALIAS_EXCLUDES:
        if ex and ex in low:
            low = low.replace(ex, "")
    for alias in CHAR_ALIASES:
        pat = _ASCII_ALIAS_RE.get(alias)
        if pat is not None:
            if pat.search(low):
                return True
        elif alias in low:
            return True
    return False


def _at_self(ev: MessageEvent, self_id: str) -> bool:
    if getattr(ev, "to_me", False):
        return True
    try:
        for seg in ev.original_message or ev.message:
            if seg.type == "at" and str(seg.data.get("qq", "")) == str(self_id):
                return True
    except Exception:
        pass
    return False


def _reply_to_self(ev: MessageEvent, self_id: str) -> bool:
    reply = getattr(ev, "reply", None)
    return bool(reply and str(reply.sender.user_id) == str(self_id))

_raw_whitelist_bot = getattr(driver.config, "airi_llm_whitelist_bot", None)
if isinstance(_raw_whitelist_bot, str):
    _raw_whitelist_bot = [b.strip() for b in _raw_whitelist_bot.split(",")]
WHITELIST_BOT = set(_raw_whitelist_bot) if _raw_whitelist_bot else set()

_raw_blacklist_group = getattr(driver.config, "airi_llm_blacklist_group", None)
if isinstance(_raw_blacklist_group, str):
    _raw_blacklist_group = [g.strip() for g in _raw_blacklist_group.split(",")]
BLACKLIST_GROUP = set(
    str(g).strip() for g in (_raw_blacklist_group or []) if str(g).strip()
)
if BLACKLIST_GROUP:
    logger.info(f"LLM 群黑名单已启用，屏蔽 {len(BLACKLIST_GROUP)} 个群")


class AiriState:
    def __init__(self):
        self.role_setup: str = ""
        self.char_name: str = CHAR_NAME
        self.char_aliases: List[str] = CHAR_ALIASES
        self.emoji_list: List[str] = []
        self.emoji_moods: Dict[str, float] = {}

        self.group_ctx: Dict[str, memory.GroupContext] = {}
        self.long_term: memory.LongTermStore = memory.LongTermStore()
        self.dirty: set = set()
        self.locks: Dict[str, asyncio.Lock] = {}
        self.bg_locks: Dict[str, asyncio.Lock] = {}

        self.passive_speaking_group_tamed: Dict[str, int] = {}
        self.last_speak_time_group: Dict[str, float] = {}
        self.negative_speaking_tokens: Dict[str, int] = {}
        self.missed_mentions: list = []
        self.emoji_b64: Dict[str, str] = {}

    def flush_prompt(self) -> str:
        try:
            with open(ROLE_SETUP_FILE, "r", encoding="utf-8") as f:
                self.role_setup = f.read().strip()
            logger.info("角色提示词已刷新")
            return "提示词已刷新"
        except Exception as e:
            logger.error(f"刷新提示词失败: {e}")
            raise

    def init_emoji_list(self) -> None:
        if not os.path.exists(EMOJI_DIR):
            logger.warning(f"表情目录不存在: {EMOJI_DIR}")
            self.emoji_list = []
            return
        self.emoji_list = [
            os.path.join(EMOJI_DIR, fname)
            for fname in os.listdir(EMOJI_DIR)
            if os.path.isfile(os.path.join(EMOJI_DIR, fname))
        ]
        logger.info(f"加载表情数量: {len(self.emoji_list)}")
        self.load_emoji_moods()

    def load_emoji_moods(self) -> None:
        self.emoji_moods = {}
        if not os.path.exists(EMOJI_MOOD_FILE):
            logger.info("表情情绪档案不存在，表情将纯随机挑选（可用 airibuildemoji 建档）")
            return
        try:
            import json
            with open(EMOJI_MOOD_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.emoji_moods = {k: float(v) for k, v in raw.items()}
            logger.info(f"加载表情情绪档案: {len(self.emoji_moods)} 条")
        except Exception as e:
            logger.warning(f"加载表情情绪档案失败: {e}")

    def save_emoji_moods(self) -> None:
        import json
        with open(EMOJI_MOOD_FILE, "w", encoding="utf-8") as f:
            json.dump(self.emoji_moods, f, ensure_ascii=False, indent=2)


@dataclass
class PendingMessage:
    group_id: str
    user_id: str
    bot: Bot
    event: MessageEvent
    content: str
    msg_id: str
    reply_to_id: Optional[str]
    nickname: str
    qq_nickname: str
    message: Any
    ts: float


airi_state = AiriState()
try:
    airi_state.flush_prompt()
except Exception:
    logger.error("角色提示词加载失败，插件以空提示词启动，可用 ldebug 刷新")
airi_state.init_emoji_list()

_2fa_key = str(getattr(driver.config, "_2fa_key", "") or "").strip()


@driver.on_startup
async def _on_startup() -> None:
    try:
        memory.load_all(airi_state)
    except Exception as e:
        logger.error(f"加载记忆失败: {e}")


@driver.on_shutdown
async def _on_shutdown() -> None:
    try:
        await _cancel_pending_batches()
        await memory.save_all(airi_state)
    except Exception as e:
        logger.error(f"关闭时保存记忆失败: {e}")


async def _flush_job() -> None:
    await memory.save_all(airi_state)


async def _extraction_job() -> None:
    await memory.extraction(airi_state)


async def _cleanup_job() -> None:
    await memory.cleanup_inactive_data(airi_state)


timings.add_job(_flush_job, "interval", minutes=2, misfire_grace_time=600, coalesce=True)
timings.add_job(_extraction_job, "interval", hours=12, misfire_grace_time=600, coalesce=True)
timings.add_job(_cleanup_job, "interval", hours=6, misfire_grace_time=600, coalesce=True)


def _image_source(seg: Any) -> str:
    data = seg.data or {}
    for key in ("url", "file"):
        val = str(data.get(key) or "")
        if val.startswith(("base64://", "http://", "https://", "file://")):
            return val
    val = str(data.get("file") or "")
    if val and os.path.exists(val):
        return "file://" + val
    return ""


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES_PER_MSG = 4
IMAGE_TIMEOUT = 15


async def get_image_base64_list(message: Any) -> List[str]:
    base64_results = []
    for seg in message:
        if seg.type != "image":
            continue
        if len(base64_results) >= MAX_IMAGES_PER_MSG:
            break
        file_str: str = _image_source(seg)
        if not file_str:
            continue
        try:
            if file_str.startswith("base64://"):
                raw = file_str[len("base64://"):]
                if len(raw) <= MAX_IMAGE_BYTES * 4 // 3:
                    base64_results.append(raw)
            elif file_str.startswith(("http://", "https://")):
                content = await download_public_bytes(
                    file_str, MAX_IMAGE_BYTES, timeout=IMAGE_TIMEOUT
                )
                base64_results.append(base64.b64encode(content).decode("utf-8"))
            elif file_str.startswith("file://"):
                fp = file_str[len("file://"):]
                if os.path.exists(fp) and os.path.getsize(fp) <= MAX_IMAGE_BYTES:
                    with open(fp, "rb") as f:
                        base64_results.append(base64.b64encode(f.read()).decode("utf-8"))
        except Exception as e:
            logger.warning(f"处理图片失败: {e}")
    return base64_results


def _pick_emoji_path(target_mood: Optional[float]) -> Optional[str]:
    if not airi_state.emoji_list:
        return None
    moods = airi_state.emoji_moods
    if target_mood is None or not moods:
        return random.choice(airi_state.emoji_list)

    scored = []
    for path in airi_state.emoji_list:
        fname = os.path.basename(path)
        if fname in moods:
            scored.append((path, abs(moods[fname] - target_mood)))
    if not scored:
        return random.choice(airi_state.emoji_list)

    within = [(p, d) for p, d in scored if d <= EMOJI_MOOD_TOLERANCE]
    pool = within if within else scored
    paths = [p for p, _ in pool]
    weights = [1.0 / (EMOJI_MOOD_SOFTNESS + d) for _, d in pool]
    return random.choices(paths, weights=weights, k=1)[0]


def _emoji_b64(path: str) -> Optional[str]:
    cached = asset_cache.get_b64(path)
    if cached:
        return cached
    try:
        with open(path, "rb") as f:
            return "base64://" + base64.b64encode(f.read()).decode("utf-8")
    except OSError as e:
        logger.warning(f"读取表情失败: {e}")
        return None


async def generate_random_emoji(target_mood: Optional[float] = None) -> Optional[MessageSegment]:
    path = _pick_emoji_path(target_mood)
    if not path:
        return None
    b64_data = _emoji_b64(path)
    if not b64_data:
        return None
    return MessageSegment.image(b64_data)


def get_user_nickname(bot: Bot, ev: MessageEvent) -> str:
    return ev.sender.card or ev.sender.nickname or str(ev.user_id)


async def _member_nickname(bot: Bot, group_id: str, qq_num: str) -> str:
    return await member_name(bot, group_id, qq_num)


async def replace_at_nickname(bot: Bot, group_id: str, input_text: str) -> str:
    at_pattern = re.compile(r"\[CQ:at,qq=(\d+)\]")
    replace_map = {}
    for match in at_pattern.finditer(input_text):
        cq_at = match.group(0)
        if cq_at in replace_map:
            continue
        qq_num = match.group(1)
        nick = await _member_nickname(bot, group_id, qq_num)
        replace_map[cq_at] = f" @{nick} "
    for old, new in replace_map.items():
        input_text = input_text.replace(old, new)
    input_text = re.sub(r"\[CQ:.*?\]", "", input_text)
    return input_text.strip()


async def build_message_content(bot: Bot, ev: MessageEvent, group_id: str) -> str:
    text = str(ev.message).strip()
    if text.startswith("."):
        text = text.lstrip(".").strip()
    text = await replace_at_nickname(bot, group_id, text)
    return text


def _time_prob_mult() -> float:
    h = time.localtime().tm_hour
    if 2 <= h < 6:
        return 0.08
    if 6 <= h < 9:
        return 0.55
    if 9 <= h < 12:
        return 1.2
    if 12 <= h < 14:
        return 0.75
    if 14 <= h < 18:
        return 1.0
    if 18 <= h < 22:
        return 1.1
    return 0.28


def _maybe_save_missed_mention(state: Any, gid: str, uid: str, snippet: str,
                              nickname: str = "", force: bool = False) -> None:
    if not snippet:
        return
    if not force and random.random() >= MISSED_MENTION_SAVE_PROB:
        return
    existing = [m for m in state.missed_mentions if m["gid"] == gid]
    if len(existing) >= MISSED_MENTION_MAX_PER_GROUP:
        return
    delay = random.randint(MISSED_MENTION_MIN_DELAY, MISSED_MENTION_MAX_DELAY)
    state.missed_mentions.append({
        "gid": gid,
        "uid": uid,
        "nickname": nickname or uid,
        "snippet": snippet[:100],
        "reply_after": time.time() + delay,
        "created_at": time.time(),
    })


def _peek_due_missed_mention(state: Any, gid: str) -> Optional[dict]:
    now = time.time()
    state.missed_mentions = [
        m for m in state.missed_mentions
        if now - m.get("created_at", now) < MISSED_MENTION_EXPIRY
    ]
    for m in state.missed_mentions:
        if m["gid"] == gid and m["reply_after"] <= now:
            return m
    return None


def _drop_missed_mention(state: Any, mention: Optional[dict]) -> None:
    if mention is None:
        return
    try:
        state.missed_mentions.remove(mention)
    except ValueError:
        pass


def _recent_traffic(group_id: str) -> int:
    ctx = airi_state.group_ctx.get(group_id)
    if not ctx:
        return 0
    cutoff = time.time() - TRAFFIC_WINDOW_SECS
    return sum(1 for e in ctx.entries if e.ts >= cutoff)


def _was_addressed(bot: Bot, ev: MessageEvent, msg_text: str) -> bool:
    return any([
        _at_self(ev, bot.self_id),
        _reply_to_self(ev, bot.self_id),
        msg_text.startswith("."),
    ])


def _should_probe_dialogue(
    bot: Bot,
    group_id: str,
    msg_text: str,
    ev: MessageEvent,
) -> bool:
    if _was_addressed(bot, ev, msg_text):
        return True
    if _alias_mentioned(msg_text):
        tokens = airi_state.negative_speaking_tokens.get(group_id, 0)
        if tokens > 0:
            return True
    last_speak = airi_state.last_speak_time_group.get(group_id, 0)
    if last_speak and time.time() - last_speak < MOMENTUM_WINDOW_SECS:
        return True
    return random.random() < AMBIENT_DIALOGUE_PROBE_PROB


def _effective_addressed(model_addressed: bool, explicit_addressed: bool) -> bool:
    return bool(model_addressed or explicit_addressed)


def _is_superuser_dot_batch(batch: List[PendingMessage]) -> bool:
    return any(
        item.user_id in SUPERUSERS and str(item.event.message).lstrip().startswith(".")
        for item in batch
    )


async def decide_speak(bot: Bot, group_id: str, user_id: str, addressed: bool) -> bool:
    tokens = airi_state.negative_speaking_tokens.get(group_id, 0)

    now = time.time()
    last_speak = airi_state.last_speak_time_group.get(group_id, 0)
    since_last = now - last_speak

    if addressed:
        if tokens > 0:
            airi_state.negative_speaking_tokens[group_id] = tokens + ADDRESSED_TOKENS_BONUS
        umem = airi_state.long_term.users.get(user_id)
        affinity = umem.affinity if umem else 0.0
        prob = min(ADDRESSED_PROB + max(0.0, affinity) * 0.08, 0.98)
        return random.random() < prob

    if since_last < HARD_COOLDOWN_SECS:
        return False

    p = BASE_SPEAK_PROB
    if tokens > 0 and since_last < MOMENTUM_WINDOW_SECS:
        p *= MOMENTUM_MULT
    traffic = _recent_traffic(group_id)
    if traffic > 0:
        p *= min(traffic / TRAFFIC_REF_MSGS, TRAFFIC_MULT_CAP)
    ctx = airi_state.group_ctx.get(group_id)
    mood = ctx.mood if ctx else 0.0
    p *= max(0.0, min(1.0 + mood, 2.0))
    arousal = ctx.bot_arousal if ctx else 0.0
    p *= max(0.3, min(1.0 + arousal, 1.8))
    p *= _time_prob_mult()

    p = min(p, MAX_UNADDRESSED_PROB)
    return random.random() < p


_bg_tasks: set = set()
_send_locks: Dict[str, asyncio.Lock] = {}


def _get_send_lock(group_id: str) -> asyncio.Lock:
    lock = _send_locks.get(group_id)
    if lock is None:
        if len(_send_locks) > 500:
            for k in [k for k, v in _send_locks.items() if not v.locked()]:
                _send_locks.pop(k, None)
        lock = asyncio.Lock()
        _send_locks[group_id] = lock
    return lock


def _spawn(coro, label: str) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)

    def _done(t):
        _bg_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.warning(f"后台任务 {label} 异常: {exc}")

    task.add_done_callback(_done)


_pending_batches: Dict[str, List[PendingMessage]] = {}
_pending_batch_tasks: Dict[str, asyncio.Task] = {}


async def _wait_and_process_batch(key: str) -> None:
    try:
        await asyncio.sleep(MESSAGE_BATCH_WAIT_SECS)
        batch = _pending_batches.pop(key, [])
        current = asyncio.current_task()
        if _pending_batch_tasks.get(key) is current:
            _pending_batch_tasks.pop(key, None)
        if batch:
            await _process_message_batch(batch)
    except asyncio.CancelledError:
        return
    except Exception as e:
        logger.warning(f"消息批次处理失败: {e}")
    finally:
        current = asyncio.current_task()
        if _pending_batch_tasks.get(key) is current:
            _pending_batch_tasks.pop(key, None)


def _queue_message(message: PendingMessage) -> None:
    key = message.group_id
    _pending_batches.setdefault(key, []).append(message)
    old_task = _pending_batch_tasks.get(key)
    if old_task is not None:
        old_task.cancel()
    task = asyncio.create_task(_wait_and_process_batch(key))
    _pending_batch_tasks[key] = task


async def _cancel_pending_batches() -> None:
    tasks = list(_pending_batch_tasks.values())
    _pending_batch_tasks.clear()
    _pending_batches.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


REPLY_MARK_RE = re.compile(r"[\[［]\s*(?:回复|reply)\s*[:：]\s*(\d{1,20})\s*[\]］]",
                           re.IGNORECASE)


def _batch_user_id(batch: List[PendingMessage]) -> str:
    for item in batch:
        if _was_addressed(item.bot, item.event, str(item.event.message)):
            return item.user_id
    return batch[-1].user_id


def _extract_reply_target(text: str, valid_ids: Set[str]) -> tuple:
    picked: Optional[str] = None
    for m in REPLY_MARK_RE.finditer(text):
        mid = m.group(1)
        if picked is None and mid in valid_ids:
            picked = mid
        elif picked is None:
            logger.warning(f"LLM 给出的引用消息ID {mid} 不在上下文中，忽略")
    cleaned = REPLY_MARK_RE.sub("", text).strip()
    return cleaned, picked


def _select_dialogue_candidate(
    result: dict, addressed: bool, valid_ids: Set[str]
) -> tuple:
    mode = "addressed" if addressed else "passive"
    reply_key = f"{mode}_reply"
    target_key = f"{mode}_reply_to"
    reply = result.get(reply_key, "")
    if not isinstance(reply, str):
        return "", None, mode
    requested_id = result.get(target_key, "")
    if not isinstance(requested_id, str) or requested_id not in valid_ids:
        requested_id = None
    reply, picked_id = _extract_reply_target(reply, valid_ids)
    if not reply:
        return "", None, mode
    return reply, requested_id or picked_id, mode


async def send_llm_reply(msg_content: str, reply_to_msg_id: Optional[str] = None,
                         bot: Optional[Bot] = None, group_id: Optional[str] = None) -> None:
    async def _out(payload) -> None:
        if bot is not None and group_id:
            await bot.send_group_msg(group_id=int(group_id), message=payload)
        else:
            await airi_llm.send(payload)

    punct_pattern = re.compile(r"[，。！？；：～,.!?;:~]+")
    msg_segments: list = []
    last_end = 0
    for m in punct_pattern.finditer(msg_content):
        body = msg_content[last_end:m.start()].strip()
        last_end = m.end()
        keep = "".join(c for c in m.group(0) if c in "！？!?～~")
        if body:
            msg_segments.append(body + keep)
        elif keep and msg_segments:
            msg_segments[-1] = msg_segments[-1] + keep
    tail = msg_content[last_end:].strip()
    if tail:
        msg_segments.append(tail)

    if not msg_segments:
        return

    if len(msg_segments) > 2 and all(len(s.rstrip("！？")) == 1 for s in msg_segments):
        merged = "！".join(s.rstrip("！？") for s in msg_segments)
        msg_segments = [merged + "！"]

    expanded: list = []
    for seg in msg_segments:
        if len(seg) > SEGMENT_MAX_LEN:
            parts = [p for p in TRANSITION_SPLIT_RE.split(seg) if p]
            expanded.extend(parts if len(parts) > 1 else [seg])
        else:
            expanded.append(seg)
    msg_segments = expanded

    send_lead = random.random() < EMOJI_RANDOM_PROB
    send_tail = random.random() < FINAL_EMOJI_PROB
    reply_mood: Optional[float] = None
    if (send_lead or send_tail) and airi_state.emoji_moods:
        try:
            reply_mood = await llm_client.classify_reply_emotion(msg_content)
        except Exception as e:
            logger.warning(f"回复情绪打分失败: {e}")

    if send_lead:
        try:
            emoji_seg = await generate_random_emoji(reply_mood)
            if emoji_seg is not None:
                await asyncio.sleep(random.randint(3, 8))
                await _out(emoji_seg)
        except Exception as e:
            logger.warning(f"发送开场表情失败（不影响回复）: {e}")

    await asyncio.sleep(random.randint(3, 8))

    pending_reply_id = reply_to_msg_id
    for idx, seg in enumerate(msg_segments):
        if seg:
            if pending_reply_id:
                try:
                    out = MessageSegment.reply(int(pending_reply_id)) + MessageSegment.text(seg)
                except (ValueError, TypeError):
                    out = seg
                pending_reply_id = None
            else:
                out = seg
            await _out(out)
            if idx != len(msg_segments) - 1:
                chars = len(seg)
                cps = TYPING_CHARS_PER_SEC_BASE + random.uniform(-TYPING_CHARS_PER_SEC_JITTER, TYPING_CHARS_PER_SEC_JITTER)
                sleep_time = max(TYPING_MIN_SECS, min(chars / max(cps, 0.5), TYPING_MAX_SECS))
                sleep_time += random.uniform(0.5, 2.0)
            else:
                sleep_time = random.uniform(1.2, 3.0)
            await asyncio.sleep(sleep_time)

    if send_tail:
        try:
            emoji_seg = await generate_random_emoji(reply_mood)
            if emoji_seg is not None:
                await _out(emoji_seg)
        except Exception as e:
            logger.warning(f"发送结尾表情失败（不影响回复）: {e}")


async def passive_speaking(bot: Bot, group_id: str, mode: int = 1) -> None:
    if group_id in BLACKLIST_GROUP:
        return
    if mode and airi_state.passive_speaking_group_tamed.get(group_id, 0):
        return
    try:
        if mode:
            airi_state.passive_speaking_group_tamed[group_id] = 1
            await asyncio.sleep(random.randint(*PASSIVE_SPEAK_DELAY_RANGE))

        ctx = airi_state.group_ctx.get(group_id)
        last_activity = ctx.last_activity_ts if ctx else 0
        if mode and (time.time() - last_activity) < PASSIVE_SPEAK_MIN_GAP:
            return

        if airi_state.negative_speaking_tokens.get(group_id, 0) == 0:
            airi_state.negative_speaking_tokens[group_id] = NEGATIVE_SPEAK_TOKENS_INIT

        if str(bot.self_id) not in nonebot.get_bots():
            logger.warning(f"主动插话时 bot {bot.self_id} 已断线，放弃发送")
            return

        lock = memory._get_lock(airi_state, group_id)
        if lock.locked():
            return

        reply = None
        reply_to_msg_id = None
        async with lock:
            candidates = memory.build_retrieval_candidates(airi_state, group_id, "")
            llm_input = memory.render_context(
                airi_state, group_id, retrieval_candidates=candidates
            )
            valid_reply_ids = memory.replyable_msg_ids(airi_state, group_id)
            result = await llm_client.generate_dialogue(
                _passive_system_prompt(), llm_input, []
            )
            if result is None:
                return

            reply = result["passive_reply"]
            requested_id = result["passive_reply_to"]
            if requested_id in valid_reply_ids:
                reply_to_msg_id = requested_id
            reply, picked_id = _extract_reply_target(reply, valid_reply_ids)
            if picked_id:
                reply_to_msg_id = picked_id
            if not reply:
                return

            knowledge.mark_used_context(
                memory.get_ctx(airi_state, group_id), group_id,
                airi_state, result["used_context"],
            )
            reply = _strip_chinese_parentheticals(reply)
            memory.save_context_entry(
                airi_state, group_id,
                memory.ContextEntry(ts=time.time(), user_id=bot.self_id,
                                    nickname="（我）", content=reply, is_self=True),
            )
            airi_state.last_speak_time_group[group_id] = time.time()

        live = nonebot.get_bots().get(str(bot.self_id))
        if live is None:
            logger.warning(f"主动插话发送前 bot {bot.self_id} 已断线，放弃发送")
            return
        try:
            async with _get_send_lock(group_id):
                await send_llm_reply(reply, reply_to_msg_id, bot=live, group_id=group_id)
        except Exception as e:
            logger.warning(f"主动插话发送失败: {e}")
    except Exception as e:
        logger.error(f"主动插话失败: {e}")
    finally:
        if mode:
            airi_state.passive_speaking_group_tamed.pop(group_id, None)


airi_llm = on_message(priority=50, block=False)
superuser_debug = on_startswith("ldebug ", priority=5, block=True, rule=to_me(), permission=SUPERUSER)
emoji_build = on_startswith("airibuildemoji", priority=5, block=True, permission=SUPERUSER)


@emoji_build.handle()
async def handle_emoji_build(bot: Bot, ev: MessageEvent):
    arg = ev.get_plaintext()[len("airibuildemoji"):].strip()
    rebuild_all = arg == "all"

    paths = list(airi_state.emoji_list)
    if not rebuild_all:
        paths = [p for p in paths if os.path.basename(p) not in airi_state.emoji_moods]
    if not paths:
        await emoji_build.finish("表情情绪档案已是最新（追加 all 可全部重建）")
        return

    await emoji_build.send(f"开始为 {len(paths)} 个表情建情绪档案，稍候……")

    BATCH = 8
    done = 0
    for i in range(0, len(paths), BATCH):
        batch = paths[i:i + BATCH]
        b64s = []
        for p in batch:
            with open(p, "rb") as f:
                b64s.append(base64.b64encode(f.read()).decode("utf-8"))
        try:
            vals = await llm_client.classify_image_emotions(b64s)
        except Exception as e:
            logger.warning(f"表情建档批次失败: {e}")
            vals = [None] * len(batch)
        for p, v in zip(batch, vals):
            if v is not None:
                airi_state.emoji_moods[os.path.basename(p)] = v
                done += 1

    try:
        airi_state.save_emoji_moods()
    except Exception as e:
        await emoji_build.finish(f"建档完成 {done} 个，但保存失败: {e}")
        return
    await emoji_build.finish(f"表情情绪档案完成：本次成功 {done} 个，共 {len(airi_state.emoji_moods)} 条")


def _batch_input(batch: List[PendingMessage], context: str) -> str:
    lines = []
    for item in batch:
        markers = []
        if _at_self(item.event, item.bot.self_id):
            markers.append("直接@你")
        if _reply_to_self(item.event, item.bot.self_id):
            markers.append("回复你的消息")
        if str(item.event.message).lstrip().startswith("."):
            markers.append("点号触发")
        marker = f"（{'、'.join(markers)}）" if markers else ""
        lines.append(f"[{item.msg_id}] {item.nickname}（{item.user_id}）{marker}：{item.content}")
    return "【当前待处理消息批次】\n" + "\n".join(lines) + "\n\n" + context


def _dialogue_system_prompt() -> str:
    return airi_state.role_setup + (
        "\n\n【内部对话协议】\n"
        "你需要结合当前待处理消息批次和最近群聊，判断这些话是不是在对你说，并同时准备两种候选回复。"
        "直接@你、回复你的消息、自然承接你刚才的话是受话线索；只提到你的名字、转述你、讨论你的身份或角色，不等于在对你说。"
        "当 addressed=true 时，addressed_reply 必须针对当前批次中实际指向你的具体内容、问题或情绪直接回复；"
        "当 addressed=false 时，passive_reply 必须像主动插话一样，从近期对话里挑一个具体内容自然带过，"
        "不得回答、不得复述、不得确认当前待处理消息，也不得假装对方是在和你说话；没有自然插话点时 passive_reply 留空。"
        "两种候选都要根据当前上下文自然生成，但程序只会选择最终受话状态对应的那一种。"
        "请同时判断背景候选是否真的与当前内容有关。"
        "严格只返回 JSON，不要返回 Markdown 或解释："
        '{"addressed": true, "addressed_reply": "受话时的直接回复正文", '
        '"addressed_reply_to": "受话时要引用的消息ID或空字符串", '
        '"passive_reply": "未受话时的主动插话正文或空字符串", '
        '"passive_reply_to": "主动插话要引用的消息ID或空字符串", '
        '"used_context": ["实际使用的候选ID"]}。addressed 必须是布尔值。'
        "两个 reply_to 只能填写最近群聊表中的非你消息ID；没有必要引用时留空。"
        "used_context 只能填写候选背景中出现的ID。"
    )


def _passive_system_prompt() -> str:
    return airi_state.role_setup + (
        "\n\n【主动插话协议】\n"
        "这是一次主动插话，不需要判断是否有人在对你说话。请从最近群聊中挑一个具体内容自然接话，"
        "严格只返回 JSON：{\"addressed\": false, \"addressed_reply\": \"\", "
        "\"addressed_reply_to\": \"\", \"passive_reply\": \"主动插话正文\", "
        "\"passive_reply_to\": \"要引用的消息ID或空字符串\", "
        "\"used_context\": [\"实际使用的候选ID\"]}。"
        "passive_reply_to 只能填写最近群聊表中的非你消息ID；used_context 只能填写候选背景中的ID。"
    )


async def _process_message_batch(batch: List[PendingMessage]) -> None:
    if not batch:
        return
    first = batch[0]
    bot = first.bot
    group_id = first.group_id
    user_id = _batch_user_id(batch)
    live = nonebot.get_bots().get(str(bot.self_id))
    if live is None:
        logger.warning(f"处理消息批次时 bot {bot.self_id} 已断线")
        return

    explicit_addressed = any(
        _was_addressed(bot, item.event, str(item.event.message)) for item in batch
    )
    combined_content = "\n".join(item.content for item in batch if item.content).strip()
    due_mention = _peek_due_missed_mention(airi_state, group_id)
    lock = memory._get_lock(airi_state, group_id)
    if lock.locked():
        if explicit_addressed and combined_content:
            _maybe_save_missed_mention(airi_state, group_id, user_id, combined_content,
                                       first.nickname, force=True)
        return

    reply = None
    reply_to_msg_id = None
    async with lock:
        if airi_state.negative_speaking_tokens.get(group_id, 0) == 0:
            airi_state.negative_speaking_tokens[group_id] = NEGATIVE_SPEAK_TOKENS_INIT

        ctx = memory.get_ctx(airi_state, group_id)
        candidates = memory.build_retrieval_candidates(
            airi_state, group_id, combined_content, user_id
        )
        recall_snippet = None
        if due_mention is not None:
            recall_snippet = (
                f"{due_mention.get('nickname') or due_mention['uid']}"
                f"[{due_mention['uid']}]：{due_mention['snippet']}"
            )
        llm_input = memory.render_context(
            airi_state, group_id, recall_snippet=recall_snippet,
            retrieval_candidates=candidates,
        )
        llm_input = _batch_input(batch, llm_input)
        images = []
        for item in batch:
            if len(images) >= MAX_IMAGES_PER_MSG:
                break
            images.extend(await get_image_base64_list(item.message))
        images = images[:MAX_IMAGES_PER_MSG]
        result = await llm_client.generate_dialogue(
            _dialogue_system_prompt(), llm_input, images
        )
        if result is None:
            logger.warning(
                f"群 {group_id} 的结构化对话结果无效，本轮不发言（显式受话={explicit_addressed}）"
            )
            return

        if due_mention is not None:
            _drop_missed_mention(airi_state, due_mention)

        effective_addressed = _effective_addressed(
            result["addressed"], explicit_addressed or due_mention is not None
        )
        force_superuser_dot = _is_superuser_dot_batch(batch)
        should_speak = (
            force_superuser_dot
            or due_mention is not None
            or await decide_speak(bot, group_id, user_id, effective_addressed)
        )
        if not should_speak:
            if explicit_addressed and combined_content:
                _maybe_save_missed_mention(airi_state, group_id, user_id, combined_content,
                                           first.nickname)
            return

        valid_reply_ids = memory.replyable_msg_ids(airi_state, group_id)
        reply, reply_to_msg_id, selected_mode = _select_dialogue_candidate(
            result, effective_addressed, valid_reply_ids
        )
        logger.info(
            f"群 {group_id} 批次受话判断：模型={result['addressed']}，"
            f"最终={effective_addressed}，显式={explicit_addressed}，"
            f"superuser点号={force_superuser_dot}，候选={selected_mode}，"
            f"回复={'有' if reply else '空'}"
        )
        if not reply:
            return

        knowledge.mark_used_context(ctx, group_id, airi_state, result["used_context"])
        reply = _strip_chinese_parentheticals(reply)
        memory.save_context_entry(
            airi_state, group_id,
            memory.ContextEntry(ts=time.time(), user_id=bot.self_id,
                                nickname="（我）", content=reply, is_self=True),
        )
        airi_state.last_speak_time_group[group_id] = time.time()

    try:
        async with _get_send_lock(group_id):
            await send_llm_reply(reply, reply_to_msg_id, bot=live, group_id=group_id)
    except Exception as e:
        logger.warning(f"回复发送失败: {e}")


@airi_llm.handle()
async def handle_airi_llm(bot: Bot, ev: MessageEvent):
    try:
        session_id = str(ev.get_session_id())
        if "group" not in session_id:
            return
        _, group_id, user_id = session_id.split("_")

        if group_id in BLACKLIST_GROUP:
            return

        if WHITELIST_BOT and bot.self_id not in WHITELIST_BOT:
            return

        uid_str = str(ev.user_id)
        is_sibling_bot = uid_str == str(bot.self_id) or uid_str in WHITELIST_BOT

        tokens = airi_state.negative_speaking_tokens.get(group_id, 0) - NEGATIVE_SPEAK_TOKENS_DEDUCT
        airi_state.negative_speaking_tokens[group_id] = max(tokens, 0)

        user_nick = get_user_nickname(bot, ev)
        qq_nickname = ev.sender.nickname or str(ev.user_id)
        content = await build_message_content(bot, ev, group_id)
        if not content and any(seg.type == "image" for seg in ev.message):
            content = "[图片]"
        msg_id = str(ev.message_id)
        reply_to_id: Optional[str] = None
        if hasattr(ev, "reply") and ev.reply:
            reply_to_id = str(ev.reply.message_id)
        else:
            for seg in ev.message:
                if seg.type == "reply":
                    reply_to_id = str(seg.data.get("id", "")) or None
                    break
        umem = airi_state.long_term.users.get(uid_str)
        if umem and umem.nickname != qq_nickname:
            umem.nickname = qq_nickname
            airi_state.dirty.add(group_id)
        if umem and (umem.card_name or "") != (ev.sender.card or ""):
            umem.card_name = ev.sender.card or ""
            airi_state.dirty.add(group_id)
        if content:
            memory.save_context_entry(
                airi_state, group_id,
                memory.ContextEntry(ts=time.time(), user_id=uid_str,
                                    nickname=user_nick, content=content,
                                    msg_id=msg_id, reply_to_id=reply_to_id,
                                    qq_nickname=qq_nickname),
            )

        if random.random() < PASSIVE_SPEAK_TRIGGER_PROB:
            _spawn(passive_speaking(bot, group_id, 1), "passive_speaking")

        _spawn(memory.maybe_distill(airi_state, group_id), "distill")
        _spawn(memory.maybe_refresh_group_state(airi_state, group_id), "group_state")
        _spawn(memory.maybe_refresh_speaking_style(airi_state, group_id), "speaking_style")
        _spawn(memory.maybe_extract_knowledge(airi_state, group_id), "extract_knowledge")

        if is_sibling_bot:
            return
        if not _should_probe_dialogue(
            bot,
            group_id,
            str(ev.message),
            ev,
        ):
            return
        _queue_message(PendingMessage(
            group_id=group_id,
            user_id=uid_str,
            bot=bot,
            event=ev,
            content=content,
            msg_id=msg_id,
            reply_to_id=reply_to_id,
            nickname=user_nick,
            qq_nickname=qq_nickname,
            message=ev.get_message(),
            ts=time.time(),
        ))

    except Exception as err:
        logger.error(f"消息处理失败: {err}\n{traceback.format_exc()}")
        return


@superuser_debug.handle()
async def handle_superuser_debug(bot: Bot, ev: MessageEvent):
    try:
        if not _2fa_key:
            await superuser_debug.send("未配置 _2fa_key，调试通道已禁用")
            return
        src = ev.get_plaintext()[6:].strip()
        while (tmpa := src.replace("  ", " ")) != src:
            src = tmpa
        user_2fa_digit = src[:6]
        if not totp_verify(_2fa_key, user_2fa_digit):
            await superuser_debug.send("2fa verification failed")
            return
        cmd = src[6:].strip()
        awaited = cmd.startswith("await ")
        if awaited:
            cmd = cmd[6:].lstrip()
        try:
            code = compile(cmd, "<ldebug>", "eval")
        except SyntaxError:
            code = None
        if code is not None:
            result = eval(code)
            if awaited or asyncio.iscoroutine(result):
                result = await result
        else:
            exec(compile(cmd, "<ldebug>", "exec"))
            result = None

        reply = "命令执行成功" if result is None else str(result)
        await superuser_debug.send(reply, reply_message=True)
    except Exception:
        await superuser_debug.finish(traceback.format_exc(), reply_message=True)
