import os
import re
import sys
import base64
import shutil
import time
import hashlib
import asyncio
import subprocess
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import httpx
import nonebot
from dotenv.parser import parse_stream
from nonebot import on_command, on_fullmatch, on_startswith, require, get_driver, logger
from nonebot.config import Config
from nonebot.params import Command, CommandArg
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, PrivateMessageEvent, MessageEvent
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont

from utils.onebot_query import bot_name, bot_profile, group_name, latest_api_latency
from utils import llm
from utils.llm import (
    PLAN_CATALOG,
    PLAN_EXPIRIES,
    PLAN_FILE,
    PlanError,
    add_plan_hours,
    ensure_plan_target_is_temporary,
    format_plan_subscriptions,
    format_plan_status,
    has_permanent_llm_access,
    parse_plan_admin_add_request,
    parse_plan_admin_bot_request,
    parse_plan_request,
    purchase_plan,
    revert_plan,
    save_plan_expiries,
    is_exact_llm_plan_command,
)

from . import counter
from . import cache
from . import dedup
from . import ram_inspector
from .charts import draw_pies_vstack, draw_summary, render_bot_cell, draw_grid
from .llm_query import render_query

def decimal_to_quaternary(decimal_num: int) -> str:
    if decimal_num <= 0:
        return "0"
    digits = []
    num = decimal_num
    while num > 0:
        digits.append(str(num % 4))
        num //= 4
    return "".join(digits)


_QQ_LEVEL_SIGNALS = ['⭐', '🌙', '☀️', '👑', '🐧']
_QQ_LEVEL_MAX_SYMBOLS = 60


def build_qq_level_signal(qq_level: int) -> str:
    if qq_level <= 0:
        return ""
    top = len(_QQ_LEVEL_SIGNALS) - 1
    remain = qq_level
    counts = [0] * len(_QQ_LEVEL_SIGNALS)
    counts[top] = remain // (4 ** top)
    remain -= counts[top] * (4 ** top)
    for i in range(top - 1, -1, -1):
        counts[i] = remain // (4 ** i)
        remain -= counts[i] * (4 ** i)
    parts = []
    total = 0
    for i in range(top, -1, -1):
        n = counts[i]
        if total + n > _QQ_LEVEL_MAX_SYMBOLS:
            n = max(0, _QQ_LEVEL_MAX_SYMBOLS - total)
        total += n
        parts.append(_QQ_LEVEL_SIGNALS[i] * n)
    return "".join(parts)

async def format_qq_data(data_list):
    UTC_PLUS_8 = timezone(timedelta(hours=8))
    msg = []
    for user,bot in data_list:
        output_lines = []
        if isinstance(user, BaseException):
            qq_number = str(bot.self_id)
            nickname = await bot_name(bot, qq_number)
            output_lines.append(f"=== {nickname} ===")
            output_lines.append(f"-QQ号：{qq_number}")
        else:
            qq_number = user.get('uin', str(bot.self_id))
            nickname = user.get('nickname', user.get('nick', '')) or await bot_name(bot, qq_number)
            reg_timestamp = user.get('regTime', user.get('reg_time', 0))
            try:
                reg_timestamp_int = int(reg_timestamp)
            except (TypeError, ValueError):
                reg_timestamp_int = 0
            reg_time = "未知"
            if reg_timestamp_int > 0:
                dt = datetime.fromtimestamp(reg_timestamp_int, tz=UTC_PLUS_8)
                reg_time = dt.strftime("%Y年%m月%d日 %H:%M:%S")[:5]
            qq_level = user.get('qqLevel', 0)
            qid = user.get('qid', 'N/A')
            is_vip = user.get('is_vip', False)
            vip_level = user.get('vip_level', 0)
            vip_info = ('\n' + f"是，VIP等级：{vip_level}") if is_vip else "否"
            output_lines.append(f"=== {nickname} ===")
            output_lines.append(f"-QQ号：{qq_number}")
            output_lines.append(f"-QID：{qid if len(qid) else '无'}")
            output_lines.append(f"-注册年份：{reg_time}")
            try:
                qq_level_int = int(qq_level)
            except (TypeError, ValueError):
                qq_level_int = 0
            qq_level_str2 = build_qq_level_signal(qq_level_int)
            qq_level_disp = "未知" if qq_level_int <= 0 else qq_level_int

        start_time = time.time()
        try:
            await bot.get_version_info()
            direct_delay = (time.time() - start_time) * 1000
        except Exception:
            direct_delay = -1

        if not isinstance(user, BaseException):
            output_lines.append(f"-QQ等级：{qq_level_disp} {qq_level_str2}".strip())
            output_lines.append(f"-是否为VIP及VIP等级：{vip_info}")
        delay_text = "获取失败" if direct_delay < 0 else f"{direct_delay:.2f}ms"
        output_lines.append(f"-连接延迟：{delay_text}")
        msg.append({"type": "node", "data": {"name": nickname, "uin": qq_number, "content": '\n'.join(output_lines)}})
    return msg

timing = require("nonebot_plugin_apscheduler").scheduler

driver = get_driver()


def _env_files(root: Path, environment: str) -> tuple[Path, Path]:
    return root / ".env", root / f".env.{environment}"


def _read_env_keys(paths: tuple[Path, ...]) -> set[str]:
    contents = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        contents.append(path.read_text(encoding="utf-8"))
    return _parse_env_keys(paths, tuple(contents))


def _parse_env_keys(paths: tuple[Path, ...], contents: tuple[str, ...]) -> set[str]:
    keys = set()
    for path, content in zip(paths, contents):
        for binding in parse_stream(StringIO(content)):
            if binding.error:
                raise ValueError(
                    f"配置文件格式错误：{path.name} 第 {binding.original.line} 行"
                )
            if binding.key:
                keys.add(binding.key.lower())
    return keys


def load_env_config(root: Path, environment: str) -> tuple[Config, set[str]]:
    paths = _env_files(root, environment)
    contents = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        contents.append(path.read_text(encoding="utf-8"))
    snapshots = tuple(contents)
    keys = _parse_env_keys(paths, snapshots)
    try:
        with TemporaryDirectory() as directory:
            snapshot_root = Path(directory)
            snapshot_paths = tuple(snapshot_root / path.name for path in paths)
            for snapshot_path, content in zip(snapshot_paths, snapshots):
                snapshot_path.write_text(content, encoding="utf-8")
            fresh = Config(_env_file=snapshot_paths)
    except Exception:
        raise ValueError("配置校验失败，请检查配置项格式") from None
    fresh.__dict__["_env_file"] = paths
    return fresh, keys


def replace_config(
    current: Config,
    fresh: Config,
    previous_env_keys: set[str],
) -> None:
    current_extra = dict(current.__pydantic_extra__ or {})
    runtime_extra = {
        key: value
        for key, value in current_extra.items()
        if key.lower() not in previous_env_keys
    }
    fresh_extra = dict(fresh.__pydantic_extra__ or {})
    merged_extra = runtime_extra | fresh_extra
    object.__setattr__(current, "__dict__", fresh.__dict__.copy())
    object.__setattr__(current, "__pydantic_extra__", merged_extra)
    object.__setattr__(
        current,
        "__pydantic_fields_set__",
        fresh.__pydantic_fields_set__.copy() | set(runtime_extra),
    )


_CONFIG_ROOT = Path(
    getattr(driver.config, "nb2_path", Path(__file__).resolve().parents[2])
)
_ENVIRONMENT = str(driver.env or "prod")
_loaded_env_keys = _read_env_keys(_env_files(_CONFIG_ROOT, _ENVIRONMENT))

airi_flush = on_fullmatch('airiflush', priority=5, block=True, permission=SUPERUSER)


@airi_flush.handle()
async def _():
    global _loaded_env_keys
    try:
        fresh, current_env_keys = load_env_config(_CONFIG_ROOT, _ENVIRONMENT)
    except Exception as e:
        logger.opt(colors=True).warning(f'<y>配置刷新失败: {e}</y>')
        await airi_flush.finish(f'配置刷新失败：{e}')
    replace_config(driver.config, fresh, _loaded_env_keys)
    _loaded_env_keys = current_env_keys
    await airi_flush.finish(
        '配置已刷新。运行时动态读取的配置已生效，导入时固化的配置仍需重启。'
    )

airi_query_accounts = on_fullmatch('airiquery', priority=5, block=True, permission=SUPERUSER)

airi_llm_query = on_command("airillmquery", priority=5, block=True, permission=SUPERUSER)
airi_llm_switch = on_command("airiccswitch", priority=5, block=True, permission=SUPERUSER)
airi_llm_plan = on_command(
    "llmplan", priority=5, block=True, force_whitespace=True
)
airi_llm_plan_query = on_command(
    "llmplanquery", priority=4, block=True, permission=SUPERUSER
)
airi_llm_plan_add = on_command(
    "llmplanadd", priority=4, block=True, permission=SUPERUSER
)
airi_llm_plan_revert = on_command(
    "llmplanrevert", priority=4, block=True, permission=SUPERUSER
)


_LLM_PLAN_LOCK = asyncio.Lock()
_LLM_PLAN_CONFIRM_TTL = 120
_PENDING_LLM_PLANS = {}


def _llm_plan_confirmation_key(bot: Bot, ev: MessageEvent) -> str:
    return f"{bot.self_id}:{ev.get_session_id()}:{ev.user_id}"


def _pending_llm_plan_exists(bot: Bot, ev: MessageEvent) -> bool:
    key = _llm_plan_confirmation_key(bot, ev)
    pending = _PENDING_LLM_PLANS.get(key)
    if not pending or time.time() - pending["created_at"] > _LLM_PLAN_CONFIRM_TTL:
        _PENDING_LLM_PLANS.pop(key, None)
        return False
    return True


def _llm_plan_help_image() -> bytes:
    generated_help = (
        _CONFIG_ROOT / "plugins" / "airi_switch" / "assets" / "llmplan_help.png"
    )
    if generated_help.is_file():
        return generated_help.read_bytes()

    source = _CONFIG_ROOT / "version.jpg"
    if source.is_file():
        image = Image.open(source).convert("RGB")
        image.thumbnail((1600, 900), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (1600, 900), (238, 232, 248))
        left = (canvas.width - image.width) // 2
        top = (canvas.height - image.height) // 2
        canvas.paste(image, (left, top))
    else:
        canvas = Image.new("RGB", (1600, 900), (238, 232, 248))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((55, 55, 880, 845), radius=36, fill=(255, 249, 255, 226))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(canvas)
    font_path = _CONFIG_ROOT / "plugins" / "airi_daily_check" / "utils" / "font.ttc"
    title_font = ImageFont.truetype(str(font_path), 60)
    body_font = ImageFont.truetype(str(font_path), 37)
    small_font = ImageFont.truetype(str(font_path), 30)
    draw.text((105, 82), "AiriCore 智能体套餐", font=title_font, fill=(78, 45, 91))
    draw.text((110, 175), "花费签到积分，让你的分布式“活起来”！", font=small_font, fill=(63, 45, 74))
    draw.text((110, 240), "套餐类型：", font=body_font, fill=(63, 45, 74))
    lines = [
        "日卡　1天　2000签到积分",
        "周卡　7天　10000签到积分",
        "月卡　30天　31900签到积分",
    ]
    y = 320
    for line in lines:
        draw.text((125, y), line, font=body_font, fill=(92, 55, 105))
        y += 83
    draw.text((110, 610), "使用指令：llmplan BotQQ号 套餐类型", font=small_font, fill=(99, 73, 111))
    output = BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=94)
    return output.getvalue()


def _format_llm_plan_expiry(expires_at: int) -> str:
    return datetime.fromtimestamp(
        expires_at, tz=timezone(timedelta(hours=8))
    ).strftime("%Y-%m-%d %H:%M:%S")


airi_llm_plan_confirm = on_fullmatch(
    ("确认", "取消"),
    priority=4,
    block=True,
    rule=_pending_llm_plan_exists,
)


@airi_llm_plan_query.handle()
async def _():
    permanent_bot_ids = getattr(driver.config, "airi_llm_whitelist_bot", None)
    if isinstance(permanent_bot_ids, str):
        permanent_bot_ids = permanent_bot_ids.split(",")
    async with _LLM_PLAN_LOCK:
        result = format_plan_subscriptions(PLAN_EXPIRIES, permanent_bot_ids or ())
    await airi_llm_plan_query.finish(result)


@airi_llm_plan_add.handle()
async def _(args: Message = CommandArg()):
    try:
        bot_id, hours = parse_plan_admin_add_request(str(args))
    except PlanError as e:
        await airi_llm_plan_add.finish(f"❌ {e}", reply_message=True)

    permanent_bot_ids = getattr(driver.config, "airi_llm_whitelist_bot", None)
    if isinstance(permanent_bot_ids, str):
        permanent_bot_ids = permanent_bot_ids.split(",")
    try:
        ensure_plan_target_is_temporary(bot_id, permanent_bot_ids or ())
    except PlanError as e:
        await airi_llm_plan_add.finish(f"❌ {e}", reply_message=True)

    async with _LLM_PLAN_LOCK:
        had_previous_expiry = bot_id in PLAN_EXPIRIES
        previous_expiry = PLAN_EXPIRIES.get(bot_id)
        try:
            expires_at = add_plan_hours(PLAN_EXPIRIES, bot_id, hours)
            save_plan_expiries(PLAN_FILE, PLAN_EXPIRIES)
        except PlanError as e:
            await airi_llm_plan_add.finish(f"❌ {e}", reply_message=True)
        except Exception as e:
            if had_previous_expiry:
                PLAN_EXPIRIES[bot_id] = previous_expiry
            else:
                PLAN_EXPIRIES.pop(bot_id, None)
            logger.error(f"llmplanadd 保存失败: {e}")
            await airi_llm_plan_add.finish("❌ 添加订阅失败，请稍后重试", reply_message=True)

    await airi_llm_plan_add.finish(
        f"✅ 已为 Bot QQ号 {bot_id} 添加 {hours} 小时订阅。\n"
        f"有效期至：{_format_llm_plan_expiry(expires_at)}",
        reply_message=True,
    )


@airi_llm_plan_revert.handle()
async def _(args: Message = CommandArg()):
    try:
        bot_id = parse_plan_admin_bot_request(str(args))
    except PlanError as e:
        await airi_llm_plan_revert.finish(f"❌ {e}", reply_message=True)

    permanent_bot_ids = getattr(driver.config, "airi_llm_whitelist_bot", None)
    if isinstance(permanent_bot_ids, str):
        permanent_bot_ids = permanent_bot_ids.split(",")
    try:
        ensure_plan_target_is_temporary(bot_id, permanent_bot_ids or ())
    except PlanError as e:
        await airi_llm_plan_revert.finish(f"❌ {e}", reply_message=True)

    async with _LLM_PLAN_LOCK:
        if bot_id not in PLAN_EXPIRIES:
            await airi_llm_plan_revert.finish(
                f"❌ Bot QQ号 {bot_id} 没有临时订阅记录。", reply_message=True
            )
        previous_expiry = PLAN_EXPIRIES[bot_id]
        try:
            revert_plan(PLAN_EXPIRIES, bot_id)
            save_plan_expiries(PLAN_FILE, PLAN_EXPIRIES)
        except Exception as e:
            PLAN_EXPIRIES[bot_id] = previous_expiry
            logger.error(f"llmplanrevert 保存失败: {e}")
            await airi_llm_plan_revert.finish("❌ 取消订阅失败，请稍后重试", reply_message=True)

    await airi_llm_plan_revert.finish(
        f"✅ 已取消 Bot QQ号 {bot_id} 的临时订阅。", reply_message=True
    )


def _format_llm_profile(info: dict[str, object], profiles: list[str]) -> str:
    auxiliary = str(info.get("other_model") or "未配置")
    available = "、".join(profiles) if profiles else "无"
    return "\n".join(
        (
            f"当前LLM配置：{info.get('name', '')}",
            f"Base URL：{info.get('base_url', '')}",
            f"Token：{info.get('token', '')}",
            f"对话模型：{info.get('chat_model', '')}",
            f"文本模型：{info.get('chat_text_model', '')}",
            f"辅助模型：{auxiliary}",
            f"可用配置：{available}",
        )
    )


@airi_llm_switch.handle()
async def _(args: Message = CommandArg()):
    profile_name = str(args).strip()
    try:
        if profile_name:
            info = await llm.switch_profile(profile_name)
            profiles = llm.list_profiles()
            result = "配置已切换\n" + _format_llm_profile(info, profiles)
        else:
            info = llm.inspect_active()
            result = _format_llm_profile(info, llm.list_profiles())
    except Exception as e:
        logger.warning(f"LLM 配置切换失败: {e}")
        result = f"LLM 配置操作失败：{e}"
    await airi_llm_switch.finish(result)


@airi_llm_query.handle()
async def _(args: Message = CommandArg()):
    try:
        result = render_query(str(args))
    except ValueError as e:
        result = str(e)
    except Exception as e:
        logger.warning(f"LLM 调用统计查询失败: {e}")
        result = "LLM 调用统计读取失败，请稍后重试。"
    await airi_llm_query.finish(result)


async def _confirm_llm_plan(matcher, bot: Bot, ev: MessageEvent):
    key = _llm_plan_confirmation_key(bot, ev)
    pending = _PENDING_LLM_PLANS.pop(key, None)
    if not pending or time.time() - pending["created_at"] > _LLM_PLAN_CONFIRM_TTL:
        await matcher.finish("❌ 没有找到待确认的套餐订单，请重新发送 llmplan BotQQ号 套餐类型")

    decision = ev.get_plaintext().strip()
    if decision == "取消":
        await matcher.finish("已取消本次套餐购买。")

    from plugins.airi_daily_check.base import state as daily_state
    from plugins.airi_daily_check.base.persistence import save_to_json

    async with _LLM_PLAN_LOCK:
        account = daily_state.data.get(pending["payer_id"])
        previous_credits = account.get("credits") if account else None
        had_previous_expiry = pending["bot_id"] in PLAN_EXPIRIES
        previous_expiry = PLAN_EXPIRIES.get(pending["bot_id"])
        try:
            result = purchase_plan(
                daily_state.data,
                PLAN_EXPIRIES,
                pending["bot_id"],
                pending["plan_type"],
                payer_id=pending["payer_id"],
            )
            await save_to_json()
            save_plan_expiries(PLAN_FILE, PLAN_EXPIRIES)
        except PlanError as e:
            await matcher.finish(f"❌ {e}")
        except Exception as e:
            if account is not None and previous_credits is not None:
                account["credits"] = previous_credits
            if had_previous_expiry:
                PLAN_EXPIRIES[pending["bot_id"]] = previous_expiry
            else:
                PLAN_EXPIRIES.pop(pending["bot_id"], None)
            try:
                await save_to_json()
            except Exception:
                pass
            logger.error(f"llmplan 购买保存失败: {e}")
            await matcher.finish("❌ 套餐开通失败，积分未扣除，请稍后重试")

    await matcher.finish(
        "✅ 套餐开通成功！\n"
        f"Bot QQ号：{result.bot_id}\n"
        f"套餐：{result.plan_type}（{result.days}天）\n"
        f"扣除付款人积分：{result.cost}\n"
        f"付款人剩余积分：{daily_state.data[pending['payer_id']]['credits']}\n"
        f"有效期至：{_format_llm_plan_expiry(result.expires_at)}"
    )


@airi_llm_plan.handle()
async def _(
    bot: Bot,
    ev: MessageEvent,
    args: Message = CommandArg(),
    command: tuple[str, ...] = Command(),
):
    if not is_exact_llm_plan_command(command):
        return
    arg_text = str(args).strip()
    if arg_text in ("确认", "取消"):
        await _confirm_llm_plan(airi_llm_plan, bot, ev)
        return
    if not arg_text:
        image = _llm_plan_help_image()
        permanent_bot_ids = getattr(driver.config, "airi_llm_whitelist_bot", None)
        if isinstance(permanent_bot_ids, str):
            permanent_bot_ids = permanent_bot_ids.split(",")
        status = format_plan_status(
            str(bot.self_id), PLAN_EXPIRIES, permanent_bot_ids or ()
        )
        await airi_llm_plan.finish(
            MessageSegment.image("base64://" + base64.b64encode(image).decode())
            + MessageSegment.text("\n" + status),
        )

    try:
        bot_id, plan_type = parse_plan_request(arg_text)
    except PlanError as e:
        await airi_llm_plan.finish(f"❌ {e}", reply_message=True)

    permanent_bot_ids = getattr(driver.config, "airi_llm_whitelist_bot", None)
    if isinstance(permanent_bot_ids, str):
        permanent_bot_ids = permanent_bot_ids.split(",")
    if has_permanent_llm_access(bot_id, permanent_bot_ids or set()):
        await airi_llm_plan.finish(
            "❌ 该 Bot 已在 .env.prod 中配置为永久权限，不能进行普通订阅。",
            reply_message=True,
        )

    from plugins.airi_daily_check.base import state as daily_state

    payer_id = str(ev.user_id)
    account = daily_state.data.get(payer_id)
    if account is None:
        await airi_llm_plan.finish('❌ 付款人尚未注册，请先发送“签到”', reply_message=True)
    cost = PLAN_CATALOG[plan_type].cost
    credits = int(account.get("credits", 0))
    if credits < cost:
        await airi_llm_plan.finish(
            f"❌ 付款人积分不足：需要{cost}积分，当前{credits}积分",
            reply_message=True,
        )

    now = int(time.time())
    current_expiry = int(float(PLAN_EXPIRIES.get(bot_id, 0)))
    preview_expiry = max(now, current_expiry) + PLAN_CATALOG[plan_type].days * 86400
    _PENDING_LLM_PLANS[_llm_plan_confirmation_key(bot, ev)] = {
        "bot_id": bot_id,
        "plan_type": plan_type,
        "payer_id": payer_id,
        "created_at": time.time(),
    }
    await airi_llm_plan.finish(
        "请确认购买以下套餐：\n"
        f"Bot QQ号：{bot_id}\n"
        f"套餐：{plan_type}（{PLAN_CATALOG[plan_type].days}天）\n"
        f"扣除付款人积分：{cost}\n"
        f"付款人当前积分：{credits}\n"
        f"有效期至：{_format_llm_plan_expiry(preview_expiry)}\n\n"
        "请回复“确认”完成购买，回复“取消”放弃。",
        reply_message=True,
    )


@airi_llm_plan_confirm.handle()
async def _(bot: Bot, ev: MessageEvent):
    await _confirm_llm_plan(airi_llm_plan_confirm, bot, ev)


async def _query_bot_profiles():
    bots = nonebot.get_bots()
    accounts = list(bots.values())
    profiles = await asyncio.gather(
        *(account.get_stranger_info(user_id=int(account.self_id)) for account in accounts),
        return_exceptions=True,
    )
    return list(zip(profiles, accounts))


@airi_query_accounts.handle()
async def _(bot: Bot, ev: MessageEvent):
    data_list = await _query_bot_profiles()
    res = await format_qq_data(data_list)
    if isinstance(ev, GroupMessageEvent):
        await bot.send_group_forward_msg(group_id=ev.group_id, messages=res)
    else:
        await bot.send_private_forward_msg(user_id=ev.user_id, messages=res)


def _img_seg(png: bytes):
    return MessageSegment.image("base64://" + base64.b64encode(png).decode())


_DEFAULT_AVATAR_MD5 = "acef72340ac0e914090bd35799f5594e"


async def _download_url(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        for _ in range(3):
            try:
                resp = await client.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                return resp.content
            except Exception:
                continue
    return b""


async def _user_avatar(uid: str) -> bytes:
    cached = cache.get("user_avatar", uid, ttl=cache.TTL_AVATAR)
    if cached:
        return cached
    url = f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=640"
    data = await _download_url(url)
    if not data or hashlib.md5(data).hexdigest() == _DEFAULT_AVATAR_MD5:
        data = await _download_url(f"http://q1.qlogo.cn/g?b=qq&nk={uid}&s=100")
    if data:
        cache.put("user_avatar", uid, data)
    return data


async def _group_avatar(gid: str) -> bytes:
    cached = cache.get("group_avatar", gid, ttl=cache.TTL_AVATAR)
    if cached:
        return cached
    data = await _download_url(f"http://p.qlogo.cn/gh/{gid}/{gid}/640")
    if data:
        cache.put("group_avatar", gid, data)
    return data


async def _prefetch_avatars(user_ids, group_ids) -> dict:
    ids = [u for u in dict.fromkeys(user_ids) if u]
    gids = [g for g in dict.fromkeys(group_ids) if g and g != counter.PRIVATE_KEY]
    tasks = [_user_avatar(u) for u in ids] + [_group_avatar(g) for g in gids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = {}
    for key, res in zip(ids + gids, results):
        out[key] = res if isinstance(res, (bytes, bytearray)) else b""
    return out


async def _bot_nick(bot: Bot, self_id: str) -> str:
    cached = cache.get("bot_name", self_id, ttl=cache.TTL_NAME)
    if cached:
        return cached
    if str(bot.self_id) == str(self_id):
        nick = await bot_name(bot, str(self_id))
        if nick:
            cache.put("bot_name", self_id, nick)
            return nick
    return cache.get("bot_name", self_id) or self_id


async def _group_labeler(bot: Bot, sessions):
    names = {}
    for sid in sessions:
        if sid == counter.PRIVATE_KEY:
            continue
        cached = cache.get("group_name", sid, ttl=cache.TTL_NAME)
        if cached:
            names[sid] = cached
            continue
        gname = await group_name(bot, sid)
        if gname == str(sid):
            gname = ""
        if gname and gname != str(sid):
            cache.put("group_name", sid, gname)
        names[sid] = gname or cache.get("group_name", sid) or ""

    def label_of(sid):
        if sid == counter.PRIVATE_KEY:
            return ("私聊", "")
        gname = names.get(sid) or f"群{sid}"
        return (gname, f"群号：{sid}")

    return label_of


async def _bot_pies(bot: Bot, self_id: str, data: dict, avatars: dict = None, date_text: str = "") -> bytes:
    avatars = avatars or {}
    recv = data.get("recv", {})
    sent = data.get("sent", {})
    label_of = await _group_labeler(bot, set(recv) | set(sent))
    recv_total = sum(recv.values())
    sent_total = sum(sent.values())
    return await asyncio.to_thread(
        draw_pies_vstack,
        (f"收 · 共 {recv_total} 条", recv),
        (f"发 · 共 {sent_total} 条", sent),
        label_of,
        lambda sid: avatars.get(sid),
        date_text,
    )


async def _bot_cell(bot: Bot, self_id: str, nick: str, data: dict, avatars: dict = None):
    avatars = avatars or {}
    recv = data.get("recv", {})
    sent = data.get("sent", {})
    label_of = await _group_labeler(bot, set(recv) | set(sent))
    recv_total = sum(recv.values())
    sent_total = sum(sent.values())
    return await asyncio.to_thread(
        render_bot_cell,
        f"{nick}({self_id})",
        (f"收 · 共 {recv_total} 条", recv),
        (f"发 · 共 {sent_total} 条", sent),
        label_of,
        lambda sid: avatars.get(sid),
        avatars.get(self_id),
    )


airi_analysis = on_startswith('airianalysis', priority=5, block=True, permission=SUPERUSER)
@airi_analysis.handle()
async def _(bot: Bot, ev: MessageEvent):
    if not isinstance(ev, GroupMessageEvent):
        await airi_analysis.finish('请在群里使用 airianalysis')

    arg = ev.get_plaintext().removeprefix('airianalysis').strip()
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')

    day = today
    bot_id = ''
    for tok in arg.split():
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', tok):
            day = tok
        elif tok:
            bot_id = tok

    stats = counter.get_stats(day)

    if bot_id:
        data = stats.get(bot_id)
        if not data:
            days = counter.get_available_days()
            tip = f'\n可用日期：{"、".join(days)}' if days else ''
            await airi_analysis.finish(f'{day} 没有 bot {bot_id} 的收发记录{tip}')
        nick = await _bot_nick(bot, bot_id)
        groups = set(data.get('recv', {})) | set(data.get('sent', {}))
        avatars = await _prefetch_avatars([], groups)
        pie = await _bot_pies(bot, bot_id, data, avatars, date_text=day)
        cache.flush()
        msg = Message(f'{nick}({bot_id}) · {day}\n') + _img_seg(pie)
        await bot.send_group_msg(group_id=ev.group_id, message=msg)
        return

    if not stats:
        days = counter.get_available_days()
        tip = f'\n可用日期：{"、".join(days)}' if days else ''
        await airi_analysis.finish(f'{day} 暂无收发统计{tip}')

    bots = nonebot.get_bots()
    all_groups = set()
    for data in stats.values():
        all_groups |= set(data.get('recv', {})) | set(data.get('sent', {}))
    avatars = await _prefetch_avatars(list(stats.keys()), all_groups)

    bot_totals = []
    cells = []
    for self_id, data in stats.items():
        cur = bots.get(self_id, bot)
        nick = await _bot_nick(cur, self_id)
        recv_total = sum(data.get('recv', {}).values())
        sent_total = sum(data.get('sent', {}).values())
        bot_totals.append((nick, self_id, recv_total, sent_total, avatars.get(self_id)))
        try:
            cells.append(await _bot_cell(cur, self_id, nick, data, avatars))
        except Exception as e:
            logger.opt(colors=True).warning(f'<y>airianalysis 生成 {self_id} 单元格失败: {e}</y>')

    grid = await asyncio.to_thread(draw_grid, cells, 4, day)
    summary = await asyncio.to_thread(draw_summary, bot_totals, day)

    cache.flush()
    await airi_analysis.finish(_img_seg(grid)+_img_seg(summary), reply_message=True)


SCREEN_BIN = shutil.which('screen') or '/usr/bin/screen'
SCREEN_SESSION = str(getattr(driver.config, 'reboot_screen_session', '') or 'airicore')
AIRICORE_DIR = str(getattr(driver.config, 'reboot_workdir', '') or os.getcwd())
BASH_BIN = shutil.which('bash') or '/bin/bash'

def _launch_script() -> str:
    names = (
        ('launch_macos.command', 'launch.command', 'launch_linux.sh', 'launch.sh')
        if sys.platform == 'darwin'
        else ('launch_linux.sh', 'launch.sh', 'launch_macos.command', 'launch.command')
    )
    for name in names:
        if os.path.isfile(os.path.join(AIRICORE_DIR, name)):
            return name
    return names[0]


LAUNCH_SCRIPT = _launch_script()

REBOOT_CMD = (
    f'{SCREEN_BIN} -S {SCREEN_SESSION} -X quit; '
    f'{BASH_BIN} -c "cd {AIRICORE_DIR} && {SCREEN_BIN} -dmS {SCREEN_SESSION} ./{LAUNCH_SCRIPT}"'
)


def _reboot_preflight() -> str:
    if os.name == 'nt':
        return '重启指令依赖 screen，Windows 环境不支持，请手动重启。'
    if not os.path.isfile(SCREEN_BIN):
        return f'未找到 screen（{SCREEN_BIN}），无法执行重启，请手动重启。'
    if not os.path.isdir(AIRICORE_DIR):
        return f'工作目录不存在（{AIRICORE_DIR}），请配置 reboot_workdir。'
    launch_path = os.path.join(AIRICORE_DIR, LAUNCH_SCRIPT)
    if not os.path.isfile(launch_path):
        return f'启动脚本不存在（{launch_path}），无法执行重启。'
    if not os.access(launch_path, os.X_OK):
        return f'启动脚本不可执行（{launch_path}），请先补充执行权限。'
    return ''


airi_force_reboot = on_fullmatch('force-reboot', priority=5, block=True, permission=SUPERUSER)
@airi_force_reboot.handle()
async def _(bot: Bot, ev: MessageEvent):
    err = _reboot_preflight()
    if err:
        await airi_force_reboot.finish(err)
    try:
        subprocess.Popen(
            REBOOT_CMD,
            shell=True,
            executable=BASH_BIN,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as e:
        await airi_force_reboot.finish(f'强制重启失败: {e}')
    await airi_force_reboot.send('已发出强制重启指令，AiriCore 即将重启。')


airi_reboot = on_fullmatch('reboot', priority=5, block=True, permission=SUPERUSER)
@airi_reboot.handle()
async def _(bot: Bot, ev: MessageEvent):
    err = _reboot_preflight()
    if err:
        await airi_reboot.finish(err)
    try:
        subprocess.Popen(
            [SCREEN_BIN, '-S', SCREEN_SESSION, '-X', 'stuff', '\003'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as e:
        await airi_reboot.finish(f'重启失败: {e}')
    await airi_reboot.send('已发出重启指令，AiriCore 即将重启。')


def _format_bytes(b: int) -> str:
    if b < 1024:
        return f"{b}B"
    kb = b / 1024
    if kb < 1024:
        return f"{kb:.1f}KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f}MB"
    gb = mb / 1024
    return f"{gb:.2f}GB"


def _ram_node(bot_id: str, name: str, content: str) -> dict:
    return {"type": "node", "data": {"name": name, "uin": bot_id, "content": content}}


airi_ram = on_fullmatch('airiram', priority=5, block=True, permission=SUPERUSER)
@airi_ram.handle()
async def _(bot: Bot, ev: MessageEvent):
    if not isinstance(ev, GroupMessageEvent):
        await airi_ram.finish('请在群里使用 airiram')

    process_mem, mode, inspections = ram_inspector.inspect_all()
    bot_id = str(bot.self_id)

    mode_desc = {
        "ram": "全驻留内存，最快，内存占用最高",
        "balanced": "仅缓存高频文件，平衡模式",
        "disk": "完全停用缓存，每次读盘，内存最小",
    }

    total_disk = sum(i["disk_bytes"] for i in inspections)
    total_ram = sum(i["ram_bytes"] for i in inspections)

    overview = ["=== 概览 ==="]
    if process_mem > 0:
        overview.append(f"Bot 进程内存占用: {_format_bytes(process_mem)}")
    else:
        overview.append("Bot 进程内存占用: 无法获取 (需安装 psutil)")
    overview.append(f"当前缓存模式: {mode}")
    if mode in mode_desc:
        overview.append(mode_desc[mode])
    overview.append("")
    overview.append(f"磁盘缓存合计: {_format_bytes(total_disk)}")
    overview.append(f"内存缓存合计: {_format_bytes(total_ram)}")
    if mode == "disk":
        overview.append("注: disk 模式下内存缓存已停用")

    nodes = [_ram_node(bot_id, "概览", "\n".join(overview))]

    for info in inspections:
        lines = [f"=== {info['name']} ==="]
        lines.append(f"磁盘: {_format_bytes(info['disk_bytes'])}")
        lines.append(f"内存: {_format_bytes(info['ram_bytes'])}")
        if info.get("error"):
            lines.append(f"读取失败: {info['error']}")
        elif info["details"]:
            lines.append("缓存明细:")
            for d in info["details"]:
                lines.append(f"  - {d}")
        else:
            lines.append("缓存明细: 暂无缓存内容")
        nodes.append(_ram_node(bot_id, info["name"], "\n".join(lines)))

    await bot.send_group_forward_msg(group_id=ev.group_id, messages=nodes, _timeout=120)
