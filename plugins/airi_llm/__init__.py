import os
import re
import time
import random
import base64
import asyncio
import logging
import traceback
from typing import Dict, List, Optional, Any

import httpx
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
from .llm_client import call_llm

driver = get_driver()
logger = logging.getLogger("airi_llm")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)

timings = require("nonebot_plugin_apscheduler").scheduler

WHITELIST_GROUP = {"657965723", "740774974", "466470972", "823217376", "808085026", "1030569383", "609034568"}
WHITELIST_BOT = {"1330248395", "535071478", "2745762139", "1264177306", "3357763830"}
SUPERUSERS = {"864623174", "3630532026"}

NEGATIVE_SPEAK_TOKENS_INIT = 50
NEGATIVE_SPEAK_TOKENS_DEDUCT = 3
ADDRESSED_TOKENS_BONUS = 2

BASE_SPEAK_PROB = 1 / 150
ADDRESSED_PROB = 0.9
HARD_COOLDOWN_SECS = 25
MOMENTUM_WINDOW_SECS = 150
MOMENTUM_MULT = 5.0
TRAFFIC_WINDOW_SECS = 90
TRAFFIC_REF_MSGS = 6
TRAFFIC_MULT_CAP = 2.0
MAX_UNADDRESSED_PROB = 0.15
NIGHT_DAMP_MULT = 0.3
NIGHT_START, NIGHT_END = 22, 6

PASSIVE_SPEAK_DELAY_RANGE = (301, 7200)
PASSIVE_SPEAK_TRIGGER_PROB = 1 / 150
PASSIVE_SPEAK_MIN_GAP = 300

EMOJI_RANDOM_PROB = 1 / 10
FINAL_EMOJI_PROB = 1 / 5
EMOJI_MOOD_TOLERANCE = 0.35
EMOJI_MOOD_SOFTNESS = 0.25

REPLY_MENTION_PROB = 0.1

PROJECT_DIR = os.path.dirname(__file__)
ROLE_SETUP_FILE = os.path.join(PROJECT_DIR, "airi_prompt_v3.md")
EMOJI_DIR = os.path.join(PROJECT_DIR, "emoji")
EMOJI_MOOD_FILE = os.path.join(PROJECT_DIR, "emoji_moods.json")

CHAR_NAME = (getattr(driver.config, "airi_char_name", "") or "").strip() or "爱莉"
_raw_aliases = getattr(driver.config, "airi_char_aliases", None)
if isinstance(_raw_aliases, str):
    _raw_aliases = [a.strip() for a in _raw_aliases.split(",")]
CHAR_ALIASES = [a.strip().lower() for a in (_raw_aliases or ["airi", "爱莉"]) if a and a.strip()]


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


airi_state = AiriState()
airi_state.flush_prompt()
airi_state.init_emoji_list()

_2fa_key = getattr(driver.config, "_2fa_key", "")


@driver.on_startup
async def _on_startup() -> None:
    try:
        memory.load_all(airi_state)
    except Exception as e:
        logger.error(f"加载记忆失败: {e}")


@driver.on_shutdown
async def _on_shutdown() -> None:
    try:
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
timings.add_job(_extraction_job, "interval", minutes=30, misfire_grace_time=600, coalesce=True)
timings.add_job(_cleanup_job, "interval", hours=6, misfire_grace_time=600, coalesce=True)


async def get_image_base64_list(message: Any) -> List[str]:
    base64_results = []
    async with httpx.AsyncClient() as http_client:
        for seg in message:
            if seg.type != "image":
                continue
            file_str: str = seg.data.get("url", "")
            try:
                if file_str.startswith("base64://"):
                    base64_results.append(file_str[len("base64://"):])
                elif file_str.startswith(("http://", "https://")):
                    resp = await http_client.get(file_str)
                    resp.raise_for_status()
                    base64_results.append(base64.b64encode(resp.content).decode("utf-8"))
                elif file_str.startswith("file://"):
                    fp = file_str[len("file://"):]
                    if os.path.exists(fp):
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


async def generate_random_emoji(target_mood: Optional[float] = None) -> MessageSegment:
    path = _pick_emoji_path(target_mood)
    if not path:
        return MessageSegment.text("😜")
    with open(path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    return MessageSegment.image(f"base64://{b64_data}")


def get_user_nickname(bot: Bot, ev: MessageEvent) -> str:
    return ev.sender.card or ev.sender.nickname or str(ev.user_id)


async def replace_at_nickname(bot: Bot, group_id: str, input_text: str) -> str:
    at_pattern = re.compile(r"\[CQ:at,qq=(\d+)\]")
    replace_map = {}
    for match in at_pattern.finditer(input_text):
        cq_at = match.group(0)
        qq_num = match.group(1)
        try:
            member_info = await bot.get_group_member_info(group_id=group_id, user_id=qq_num)
            nick = member_info.get("nickname") or member_info.get("card") or qq_num
            replace_map[cq_at] = f" @{nick} "
        except Exception as e:
            logger.warning(f"获取@用户信息失败: {e}")
            replace_map[cq_at] = f" @{qq_num} "
    for old, new in replace_map.items():
        input_text = input_text.replace(old, new)
    input_text = re.sub(r"\[CQ:.*?\]", "", input_text)
    return input_text.strip()


async def build_message_content(bot: Bot, ev: MessageEvent, group_id: str) -> str:
    text = str(ev.message).strip()
    text = await replace_at_nickname(bot, group_id, text)
    return text


def _is_night() -> bool:
    h = time.localtime().tm_hour
    return h >= NIGHT_START or h < NIGHT_END


def _recent_traffic(group_id: str) -> int:
    ctx = airi_state.group_ctx.get(group_id)
    if not ctx:
        return 0
    cutoff = time.time() - TRAFFIC_WINDOW_SECS
    return sum(1 for e in ctx.entries if e.ts >= cutoff)


async def decide_speak(bot: Bot, ev: MessageEvent, group_id: str, user_id: str) -> bool:
    if user_id in SUPERUSERS and str(ev.message).startswith("."):
        return True

    tokens = airi_state.negative_speaking_tokens.get(group_id, 0)
    msg_raw = str(ev)
    msg_text = str(ev.message)
    msg_lower = msg_text.lower()
    addressed = any([
        any(alias in msg_lower for alias in CHAR_ALIASES),
        bot.self_id in msg_raw,
        msg_text.startswith("."),
        (hasattr(ev, "reply") and ev.reply and str(ev.reply.sender.user_id) == bot.self_id),
    ])

    now = time.time()
    last_speak = airi_state.last_speak_time_group.get(group_id, 0)
    since_last = now - last_speak

    if addressed and tokens > 0:
        airi_state.negative_speaking_tokens[group_id] = tokens + ADDRESSED_TOKENS_BONUS
        return random.random() < ADDRESSED_PROB

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
    if _is_night():
        p *= NIGHT_DAMP_MULT

    p = min(p, MAX_UNADDRESSED_PROB)
    return random.random() < p


async def send_llm_reply(msg_content: str, need_reply: int) -> int:
    punct_pattern = re.compile(r"[，。！？；：～]+")
    if random.randint(1, 8) > 1:
        msg_segments = punct_pattern.split(msg_content)
    else:
        msg_segments = [msg_content]

    msg_segments = [seg.strip() for seg in msg_segments if seg.strip()]
    if not msg_segments:
        return 0

    if len(msg_segments) > 2:
        is_single = 1
        for idx in range(len(msg_segments)):
            seg = msg_segments[idx]
            if seg.endswith(("，", "。")):
                msg_segments[idx] = seg[:-1]
            if idx != len(msg_segments) - 1 and len(seg) > 1:
                is_single = 0
        if is_single:
            msg_segments = ["！".join(msg_segments) + "！"]
    for idx in range(len(msg_segments)):
        seg = msg_segments[idx]
        if seg.endswith(("，", "。")):
            msg_segments[idx] = seg[:-1]

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
            await asyncio.sleep(random.randint(3, 8))
            await airi_llm.send(emoji_seg)
        except Exception as e:
            logger.warning(f"发送开场表情失败（不影响回复）: {e}")

    await asyncio.sleep(random.randint(3, 8))

    for idx, seg in enumerate(msg_segments):
        if seg:
            await airi_llm.send(seg, reply_message=bool(need_reply))
            need_reply = 0
            sleep_time = random.randint(4, 8) if idx != len(msg_segments) - 1 else random.randint(1, 2)
            await asyncio.sleep(sleep_time)

    if send_tail:
        try:
            emoji_seg = await generate_random_emoji(reply_mood)
            await airi_llm.send(emoji_seg)
        except Exception as e:
            logger.warning(f"发送结尾表情失败（不影响回复）: {e}")

    return need_reply


async def passive_speaking(bot: Bot, group_id: str, mode: int = 1) -> None:
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

        lock = memory._get_lock(airi_state, group_id)
        if lock.locked():
            return

        async with lock:
            llm_input = memory.render_context(airi_state, group_id)
            reply = await call_llm(airi_state.role_setup, llm_input, [])
            if not reply:
                return

            reply = re.sub(r"[(（].+?[)）]", "", reply)
            memory.save_context_entry(
                airi_state, group_id,
                memory.ContextEntry(ts=time.time(), user_id=bot.self_id,
                                    nickname="（我）", content=reply, is_self=True),
            )
            airi_state.last_speak_time_group[group_id] = time.time()
            try:
                await send_llm_reply(reply, 0)
            except Exception:
                pass
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


@airi_llm.handle()
async def handle_airi_llm(bot: Bot, ev: MessageEvent):
    try:
        session_id = str(ev.get_session_id())
        if "group" not in session_id:
            return
        _, group_id, user_id = session_id.split("_")

        if bot.self_id not in WHITELIST_BOT:
            return

        tokens = airi_state.negative_speaking_tokens.get(group_id, 0) - NEGATIVE_SPEAK_TOKENS_DEDUCT
        airi_state.negative_speaking_tokens[group_id] = max(tokens, 0)

        user_nick = get_user_nickname(bot, ev)
        content = await build_message_content(bot, ev, group_id)
        if content:
            memory.save_context_entry(
                airi_state, group_id,
                memory.ContextEntry(ts=time.time(), user_id=str(ev.user_id),
                                    nickname=user_nick, content=content),
            )

        if random.random() < PASSIVE_SPEAK_TRIGGER_PROB:
            asyncio.create_task(passive_speaking(bot, group_id, 1))

        asyncio.create_task(memory.maybe_distill(airi_state, group_id))
        asyncio.create_task(memory.maybe_refresh_mood(airi_state, group_id))
        asyncio.create_task(memory.maybe_refresh_speaking_style(airi_state, group_id))
        asyncio.create_task(memory.maybe_refresh_bot_mood(airi_state, group_id))

        if not await decide_speak(bot, ev, group_id, user_id):
            return

        img_b64_list = await get_image_base64_list(ev.get_message())

        lock = memory._get_lock(airi_state, group_id)
        if lock.locked():
            return
        async with lock:
            if airi_state.negative_speaking_tokens.get(group_id, 0) == 0:
                airi_state.negative_speaking_tokens[group_id] = NEGATIVE_SPEAK_TOKENS_INIT

            need_reply = 1 if random.random() < REPLY_MENTION_PROB else 0

            llm_input = memory.render_context(airi_state, group_id)
            llm_reply = await call_llm(airi_state.role_setup, llm_input, img_b64_list)
            if not llm_reply:
                return

            llm_reply = re.sub(r"[(（].+?[)）]", "", llm_reply)
            memory.save_context_entry(
                airi_state, group_id,
                memory.ContextEntry(ts=time.time(), user_id=bot.self_id,
                                    nickname="（我）", content=llm_reply, is_self=True),
            )
            airi_state.last_speak_time_group[group_id] = time.time()

            try:
                await send_llm_reply(llm_reply, need_reply)
            except Exception:
                pass

    except Exception as err:
        logger.error(f"消息处理失败: {err}\n{traceback.format_exc()}")
        return


@superuser_debug.handle()
async def handle_superuser_debug(bot: Bot, ev: MessageEvent):
    try:
        src = ev.get_plaintext()[6:].strip()
        while (tmpa := src.replace("  ", " ")) != src:
            src = tmpa
        user_2fa_digit = src[:6]
        if not totp_verify(_2fa_key, user_2fa_digit):
            await superuser_debug.send("2fa verification failed")
            return
        cmd = src[6:].strip()
        if cmd.startswith("await "):
            try:
                result = await eval(cmd[6:].lstrip())
            except Exception:
                result = await exec(cmd[6:].lstrip())
        else:
            try:
                result = eval(cmd)
            except Exception:
                result = exec(cmd)

        reply = "命令执行成功" if result is None else str(result)
        await superuser_debug.send(reply, reply_message=True)
    except Exception:
        await superuser_debug.finish(traceback.format_exc(), reply_message=True)
