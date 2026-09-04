import asyncio
import base64
import os
import pickle
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from nonebot import get_driver, on_command, on_fullmatch, logger
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.params import Command, CommandArg
from PIL import Image, ImageDraw, ImageFont

from utils import credits
from utils.superuser_2fa import SUPERUSER_2FA


driver = get_driver()
_CONFIG_ROOT = Path(
    getattr(driver.config, "nb2_path", Path(__file__).resolve().parents[2])
)
UTC_PLUS_8 = timezone(timedelta(hours=8))


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class PlanSpec:
    days: int
    cost: int


@dataclass(frozen=True)
class PurchaseResult:
    bot_id: str
    plan_type: str
    days: int
    cost: int
    expires_at: int


PLAN_CATALOG = {
    "日卡": PlanSpec(days=1, cost=2000),
    "周卡": PlanSpec(days=7, cost=10000),
    "月卡": PlanSpec(days=30, cost=31900),
}


def _plan_now(now: int | float | None) -> int:
    return int(time.time() if now is None else now)


def _normalize_plan_bot_id(bot_id: str) -> str:
    normalized = str(bot_id).strip()
    if not re.fullmatch(r"[1-9]\d{4,11}", normalized):
        raise PlanError("QQ号格式不正确")
    return normalized


def parse_plan_request(text: str) -> tuple[str, str]:
    parts = str(text).strip().split()
    if len(parts) != 2:
        raise PlanError("用法：llmplan BotQQ号 套餐类型\n套餐类型：日卡、周卡、月卡")
    bot_id = _normalize_plan_bot_id(parts[0])
    if parts[1] not in PLAN_CATALOG:
        raise PlanError("套餐类型无效，可选：日卡、周卡、月卡")
    return bot_id, parts[1]


def parse_plan_admin_add_request(text: str) -> tuple[str, int]:
    parts = str(text).strip().split()
    if len(parts) != 2:
        raise PlanError("用法：llmplanadd BotQQ 小时数")
    bot_id = _normalize_plan_bot_id(parts[0])
    if not re.fullmatch(r"[1-9]\d*", parts[1]):
        raise PlanError("小时数必须是正整数")
    try:
        hours = int(parts[1])
    except ValueError:
        raise PlanError("小时数过大") from None
    return bot_id, hours


def parse_plan_admin_bot_request(text: str) -> str:
    parts = str(text).strip().split()
    if len(parts) != 1:
        raise PlanError("用法：llmplanrevert BotQQ")
    return _normalize_plan_bot_id(parts[0])


def add_plan_hours(
    expiries: dict,
    bot_id: str,
    hours: int,
    *,
    now: int | float | None = None,
) -> int:
    normalized_bot_id = _normalize_plan_bot_id(bot_id)
    if isinstance(hours, bool) or int(hours) <= 0:
        raise PlanError("小时数必须是正整数")
    current_time = _plan_now(now)
    expires_at = max(current_time, int(float(expiries.get(normalized_bot_id, 0))))
    expires_at += int(hours) * 3600
    expiries[normalized_bot_id] = expires_at
    return expires_at


def revert_plan(expiries: dict, bot_id: str) -> bool:
    normalized_bot_id = _normalize_plan_bot_id(bot_id)
    return expiries.pop(normalized_bot_id, None) is not None


def format_plan_subscriptions(
    expiries: dict,
    permanent_bot_ids: set[str] | list[str] | tuple[str, ...] = (),
    nicknames: dict[str, str] | None = None,
    *,
    now: int | float | None = None,
) -> str:
    current_time = _plan_now(now)
    names = nicknames or {}
    temporary_lines = []
    for bot_id, expires_at in sorted(
        expiries.items(), key=lambda item: (str(item[0]), float(item[1]))
    ):
        expiry = int(float(expires_at))
        status = "生效中" if expiry > current_time else "已过期"
        temporary_lines.append(
            f"{names.get(str(bot_id), str(bot_id))}({bot_id})｜{status}｜有效期至：{datetime.fromtimestamp(expiry, tz=UTC_PLUS_8):%Y-%m-%d %H:%M:%S}"
        )

    permanent_ids = sorted({str(bot_id).strip() for bot_id in permanent_bot_ids if str(bot_id).strip()})
    lines = ["当前订阅情况："]
    lines.extend(temporary_lines or ["临时订阅：无"])
    if permanent_ids:
        lines.append("永久权限：")
        lines.extend(
            f"{names.get(bot_id, bot_id)}({bot_id})｜永久权限"
            for bot_id in permanent_ids
        )
    return "\n".join(lines)


def has_permanent_llm_access(bot_id: str, permanent_bot_ids: set[str] | list[str] | tuple[str, ...]) -> bool:
    normalized_bot_id = str(bot_id).strip()
    return normalized_bot_id in {str(item).strip() for item in permanent_bot_ids}


def format_plan_status(
    bot_id: str,
    expiries: dict,
    permanent_bot_ids: set[str] | list[str] | tuple[str, ...] = (),
    *,
    now: int | float | None = None,
) -> str:
    normalized_bot_id = str(bot_id).strip()
    current_time = _plan_now(now)
    if has_permanent_llm_access(normalized_bot_id, permanent_bot_ids):
        status = "永久权限"
        expiry_line = "有效期：永久"
    else:
        expiry = int(float(expiries.get(normalized_bot_id, 0)))
        if expiry > current_time:
            status = "临时订阅生效中"
            expiry_line = f"有效期至：{datetime.fromtimestamp(expiry, tz=UTC_PLUS_8):%Y-%m-%d %H:%M:%S}"
        else:
            status = "无订阅" if normalized_bot_id not in expiries else "临时订阅已过期"
            expiry_line = "有效期：无"
    return "\n".join(("当前分布式订阅信息：", f"订阅状态：{status}", expiry_line))


async def purchase_plan_with_credits(
    payer_id: str,
    expiries: dict,
    bot_id: str,
    plan_type: str,
    *,
    now: int | float | None = None,
) -> PurchaseResult:
    normalized_payer_id = str(payer_id).strip()
    normalized_bot_id = _normalize_plan_bot_id(bot_id)
    spec = PLAN_CATALOG.get(str(plan_type).strip())
    if spec is None:
        raise PlanError("套餐类型无效，可选：日卡、周卡、月卡")
    balance = await credits.get_balance(normalized_payer_id)
    if balance < spec.cost:
        raise PlanError(f"付款人积分不足：需要{spec.cost}积分，当前{balance}积分")
    current_time = _plan_now(now)
    previous_expiry = int(float(expiries.get(normalized_bot_id, 0)))
    expires_at = max(current_time, previous_expiry) + spec.days * 86400
    try:
        await credits.debit(normalized_payer_id, spec.cost)
    except credits.InsufficientCreditsError:
        raise PlanError(f"付款人积分不足：需要{spec.cost}积分，当前{balance}积分") from None
    try:
        expiries[normalized_bot_id] = expires_at
    except Exception:
        await credits.credit(normalized_payer_id, spec.cost)
        raise
    return PurchaseResult(
        bot_id=normalized_bot_id,
        plan_type=str(plan_type).strip(),
        days=spec.days,
        cost=spec.cost,
        expires_at=expires_at,
    )


def has_llm_access(
    bot_id: str,
    permanent_bot_ids: set[str] | list[str] | tuple[str, ...],
    expiries: dict,
    *,
    now: int | float | None = None,
) -> bool:
    normalized_bot_id = str(bot_id).strip()
    if normalized_bot_id in {str(item).strip() for item in permanent_bot_ids}:
        return True
    return float(expiries.get(normalized_bot_id, 0)) > _plan_now(now)


def ensure_plan_target_is_temporary(
    bot_id: str,
    permanent_bot_ids: set[str] | list[str] | tuple[str, ...],
) -> None:
    if has_permanent_llm_access(bot_id, permanent_bot_ids):
        raise PlanError("该 Bot 已配置为永久权限，不能进行普通订阅、增加或取消操作")


def is_exact_llm_plan_command(command: tuple[str, ...] | None) -> bool:
    return command == ("llmplan",)


def load_plan_expiries(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as stream:
            raw = pickle.load(stream)
        if not isinstance(raw, dict):
            return {}
        return {
            str(bot_id): int(float(expires_at))
            for bot_id, expires_at in raw.items()
            if str(bot_id).strip() and float(expires_at) > 0
        }
    except (OSError, EOFError, TypeError, ValueError, pickle.PickleError):
        return {}


def save_plan_expiries(path: Path, expiries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            pickle.dump(expiries, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


PLAN_FILE = Path(__file__).resolve().parents[2] / "data" / "airi_llm" / "llm_plan.pk"
PLAN_EXPIRIES = load_plan_expiries(PLAN_FILE)


airi_llm_plan = on_command("llmplan", priority=5, block=True, force_whitespace=True)
airi_llm_plan_query = on_command(
    "llmplanquery", priority=4, block=True, permission=SUPERUSER_2FA
)
airi_llm_plan_add = on_command(
    "llmplanadd", priority=4, block=True, permission=SUPERUSER_2FA
)
airi_llm_plan_revert = on_command(
    "llmplanrevert", priority=4, block=True, permission=SUPERUSER_2FA
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
    generated_help = Path(__file__).resolve().parent / "assets" / "llmplan_help.png"
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
    y = 320
    for line in ("日卡　1天　2000签到积分", "周卡　7天　10000签到积分", "月卡　30天　31900签到积分"):
        draw.text((125, y), line, font=body_font, fill=(92, 55, 105))
        y += 83
    draw.text((110, 610), "使用指令：llmplan BotQQ号 套餐类型", font=small_font, fill=(99, 73, 111))
    output = BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=94)
    return output.getvalue()


def _format_llm_plan_expiry(expires_at: int) -> str:
    return datetime.fromtimestamp(expires_at, tz=UTC_PLUS_8).strftime("%Y-%m-%d %H:%M:%S")


airi_llm_plan_confirm = on_fullmatch(
    ("确认", "取消"), priority=4, block=True, rule=_pending_llm_plan_exists
)


@airi_llm_plan_query.handle()
async def _query_plan(bot: Bot):
    permanent_bot_ids = getattr(driver.config, "airi_llm_whitelist_bot", None)
    if isinstance(permanent_bot_ids, str):
        permanent_bot_ids = permanent_bot_ids.split(",")
    async with _LLM_PLAN_LOCK:
        plan_expiries = dict(PLAN_EXPIRIES)
        permanent_ids = tuple(permanent_bot_ids or ())
    bot_ids = sorted(
        set(plan_expiries)
        | {str(bot_id).strip() for bot_id in permanent_ids if str(bot_id).strip()}
    )
    nickname_results = await asyncio.gather(
        *(bot.get_stranger_info(user_id=int(bot_id)) for bot_id in bot_ids),
        return_exceptions=True,
    )
    nicknames = {}
    for bot_id, info in zip(bot_ids, nickname_results):
        if isinstance(info, dict):
            nicknames[bot_id] = str(info.get("nickname") or info.get("nick") or bot_id)
        else:
            nicknames[bot_id] = bot_id
    async with _LLM_PLAN_LOCK:
        result = format_plan_subscriptions(plan_expiries, permanent_ids, nicknames)
    await airi_llm_plan_query.finish(result)


@airi_llm_plan_add.handle()
async def _add_plan(args: Message = CommandArg()):
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
async def _revert_plan(args: Message = CommandArg()):
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
    await airi_llm_plan_revert.finish(f"✅ 已取消 Bot QQ号 {bot_id} 的临时订阅。", reply_message=True)


async def _confirm_llm_plan(matcher, bot: Bot, ev: MessageEvent):
    key = _llm_plan_confirmation_key(bot, ev)
    pending = _PENDING_LLM_PLANS.pop(key, None)
    if not pending or time.time() - pending["created_at"] > _LLM_PLAN_CONFIRM_TTL:
        await matcher.finish("❌ 没有找到待确认的套餐订单，请重新发送 llmplan BotQQ号 套餐类型")
    decision = ev.get_plaintext().strip()
    if decision == "取消":
        await matcher.finish("已取消本次套餐购买。")
    async with _LLM_PLAN_LOCK:
        had_previous_expiry = pending["bot_id"] in PLAN_EXPIRIES
        previous_expiry = PLAN_EXPIRIES.get(pending["bot_id"])
        try:
            result = await purchase_plan_with_credits(
                pending["payer_id"],
                PLAN_EXPIRIES,
                pending["bot_id"],
                pending["plan_type"],
            )
            save_plan_expiries(PLAN_FILE, PLAN_EXPIRIES)
        except PlanError as e:
            await matcher.finish(f"❌ {e}")
        except Exception as e:
            try:
                await credits.credit(pending["payer_id"], PLAN_CATALOG[pending["plan_type"]].cost)
            except Exception:
                pass
            if had_previous_expiry:
                PLAN_EXPIRIES[pending["bot_id"]] = previous_expiry
            else:
                PLAN_EXPIRIES.pop(pending["bot_id"], None)
            logger.error(f"llmplan 购买保存失败: {e}")
            await matcher.finish("❌ 套餐开通失败，积分未扣除，请稍后重试")
    await matcher.finish(
        "✅ 套餐开通成功！\n"
        f"Bot QQ号：{result.bot_id}\n"
        f"套餐：{result.plan_type}（{result.days}天）\n"
        f"扣除付款人积分：{result.cost}\n"
        f"付款人剩余积分：{await credits.get_balance(pending['payer_id'])}\n"
        f"有效期至：{_format_llm_plan_expiry(result.expires_at)}"
    )


@airi_llm_plan.handle()
async def _plan(
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
        status = format_plan_status(str(bot.self_id), PLAN_EXPIRIES, permanent_bot_ids or ())
        await airi_llm_plan.finish(
            MessageSegment.image("base64://" + base64.b64encode(image).decode())
            + MessageSegment.text("\n" + status)
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
    payer_id = str(ev.user_id)
    cost = PLAN_CATALOG[plan_type].cost
    balance = await credits.get_balance(payer_id)
    if balance < cost:
        await airi_llm_plan.finish(
            f"❌ 付款人积分不足：需要{cost}积分，当前{balance}积分",
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
        f"付款人当前积分：{balance}\n"
        f"有效期至：{_format_llm_plan_expiry(preview_expiry)}\n\n"
        "请回复“确认”完成购买，回复“取消”放弃。",
        reply_message=True,
    )


@airi_llm_plan_confirm.handle()
async def _plan_confirm(bot: Bot, ev: MessageEvent):
    await _confirm_llm_plan(airi_llm_plan_confirm, bot, ev)
