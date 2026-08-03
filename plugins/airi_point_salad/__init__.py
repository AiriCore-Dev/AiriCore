import asyncio
from dataclasses import dataclass
from pathlib import Path
import re

import nonebot
from nonebot import get_driver, logger, on_regex
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from nonebot.plugin import PluginMetadata

from utils.asset_cache import get_b64

from .commands import Command, CommandError, parse_command
from .game import GameError
from .help import help_sections
from .models import GameMode, GameSpeed, GameState, Phase
from .persistence import GameStore
from .message_retention import MessageRetention
from .renderer import render_board_images, render_result, render_turn_change
from .service import GameService
from .skills import skill_description


USAGE = (
    "MORE MORE JUMP！得分沙拉\n"
    "普通模式使用官方基础规则；混合模式增加 Center 与 Live Mission\n"
    "快速/标准只改变牌量：每种角色为人数 × 2 / 人数 × 3\n"
    "创建：,沙拉 创建 快速 原版\n"
    "等价：,salad create quick classic\n"
    "缩写：,sl cr qk cl\n"
    "加入/退出：,sl j / ,sl lv\n"
    "开始/结束：,sl st / ,sl sp\n"
    "拿牌：,sl ta A / ,sl ta A1 B2\n"
    "翻牌：,sl fl 2\n"
    "技能：,sl sk\n"
    "桌面/规则：,sl bd / ,sl rl"
)


__plugin_meta__ = PluginMetadata(
    name="MORE MORE JUMP！得分沙拉",
    description="2–6 人群聊内游玩的 MORE MORE JUMP！主题 Point Salad 选牌桌游",
    usage=USAGE,
    extra={"author": "AiriCore Dev.", "version": "1.0.0"},
)


service = GameService(
    GameStore(Path("data/airi_point_salad/games.pk"))
)
message_retention = MessageRetention()
try:
    driver = get_driver()
except ValueError:
    driver = None
salad = on_regex(
    r"^\s*,\s*(?:沙拉|salad|sl)(?:\s+|$)",
    flags=re.IGNORECASE,
    priority=12,
    block=True,
)
COVER_PATH = Path(__file__).resolve().parent / "assets" / "cover.png"


@dataclass(frozen=True, slots=True)
class CommandResponse:
    body: str | tuple[str, ...]
    turn_user_id: str | None = None
    turn_notice: str | None = None


def response_message(response: CommandResponse):
    segments = Message()
    if response.turn_notice is not None:
        segments += MessageSegment.image(response.turn_notice)
    if response.turn_user_id is not None:
        segments += MessageSegment.at(response.turn_user_id)
    if isinstance(response.body, tuple):
        for item in response.body:
            if item.startswith("base64://"):
                segments += MessageSegment.image(item)
            else:
                segments += MessageSegment.text(item)
        return segments
    if not response.body.startswith("base64://"):
        if len(segments):
            segments += MessageSegment.text(response.body)
            return segments
        return response.body
    segments += MessageSegment.image(response.body)
    return segments


def detailed_help_nodes(bot_id: str) -> list[dict]:
    nodes = []
    for index, (title, body) in enumerate(help_sections()):
        content = body
        if index == 0:
            cover = get_b64(COVER_PATH)
            if cover is None:
                logger.warning("得分沙拉帮助封面缺失，已降级为纯文本")
            else:
                content = MessageSegment.text(body) + MessageSegment.image(cover)
        nodes.append({
            "type": "node",
            "data": {
                "name": title,
                "uin": bot_id,
                "content": content,
            },
        })
    return nodes


async def send_detailed_help(bot: Bot, group_id: int) -> tuple[str | None, str | None]:
    try:
        receipt = await bot.send_group_forward_msg(
            group_id=group_id,
            messages=detailed_help_nodes(bot.self_id),
        )
    except Exception as error:
        logger.opt(exception=error).error("得分沙拉详细帮助发送失败")
        return "得分沙拉详细帮助暂时无法发送，请稍后重试", None
    return None, receipt_message_id(receipt)


def receipt_message_id(receipt) -> str | None:
    if isinstance(receipt, dict):
        message_id = receipt.get("message_id")
    elif receipt is not None:
        message_id = getattr(receipt, "message_id", None)
    else:
        message_id = None
    return None if message_id is None else str(message_id)


def render_state(state: GameState, viewer_id: str) -> str | tuple[str, str]:
    if state.phase is Phase.PLAYING:
        return render_board_images(state, viewer_id)
    if state.phase is Phase.FINISHED:
        if state.cards:
            return render_result(state)
        return "得分沙拉房间已关闭"
    return render_board_images(state, viewer_id)


async def execute_command(
    command: Command,
    group_id: str,
    user_id: str,
    user_name: str,
    is_admin: bool,
) -> CommandResponse:
    def prepare(state, turn_user_id, before=None):
        notice = render_turn_change(before, state) if turn_user_id is not None else None
        return CommandResponse(render_state(state, user_id), turn_user_id, notice)

    if command.action == "create":
        return await service.create(
            group_id,
            user_id,
            user_name,
            GameSpeed(command.args[0]),
            GameMode(command.args[1]),
            prepare=prepare,
        )
    if command.action == "join":
        return await service.join(group_id, user_id, user_name, prepare=prepare)
    if command.action == "leave":
        return await service.leave(group_id, user_id, prepare=prepare)
    if command.action == "start":
        state = await service.board_state(group_id)
        if state.phase is Phase.PLAYING and state.mode is GameMode.MIX:
            return CommandResponse(await service.rules_text(group_id))
        return await service.start(group_id, user_id, prepare=prepare)
    if command.action == "take":
        return await service.take(group_id, user_id, command.args, prepare=prepare)
    if command.action == "flip":
        return await service.flip(group_id, user_id, command.args[0], prepare=prepare)
    if command.action == "skill":
        state = await service.board_state(group_id)
        player = next((item for item in state.players if item.user_id == user_id), None)
        if state.mode is GameMode.MIX and state.phase is Phase.PLAYING and player is not None and player.center is not None:
            response = await service.skill(group_id, user_id, command.args, prepare=prepare)
            body = response.body
            if isinstance(body, tuple):
                return CommandResponse((skill_description(player.center), *body), response.turn_user_id, response.turn_notice)
            return CommandResponse((skill_description(player.center), body), response.turn_user_id, response.turn_notice)
        return await service.skill(group_id, user_id, command.args, prepare=prepare)
    if command.action == "stop":
        return await service.stop(
            group_id,
            user_id,
            is_admin,
            prepare=prepare,
        )
    if command.action == "board":
        state = await service.board_state(group_id)
        body = await asyncio.to_thread(render_state, state, user_id)
        return CommandResponse(body)
    if command.action == "summary":
        return CommandResponse(await service.rules_text(group_id))
    raise CommandError("未知指令，请使用 ,sl rl 查看规则")


@salad.handle()
async def handle_salad(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await salad.finish("该游戏仅支持群聊")
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    user_name = event.sender.card or event.sender.nickname or user_id
    is_admin = event.sender.role in {"owner", "admin"}
    token = message_retention.reserve(group_id, str(event.message_id))

    async def delete(message_id):
        await bot.call_api(
            "delete_msg",
            message_id=int(message_id) if str(message_id).isdigit() else message_id,
        )

    was_playing = (
        group_id in service.games
        and service.games[group_id].phase is Phase.PLAYING
    )
    if was_playing:
        await message_retention.activate(group_id, token, delete)
    try:
        command = parse_command(event.get_plaintext())
        if command.action == "rules":
            error_message, bot_message_id = await send_detailed_help(bot, event.group_id)
            if error_message is None:
                if was_playing:
                    await message_retention.complete(
                        group_id,
                        token,
                        bot_message_id,
                        delete,
                    )
                else:
                    message_retention.cancel(group_id, token)
                return
            response = CommandResponse(error_message)
        else:
            response = await execute_command(
                command,
                group_id,
                user_id,
                user_name,
                is_admin,
            )
    except (CommandError, GameError) as error:
        response = CommandResponse(str(error))
    except Exception as error:
        logger.opt(exception=error).error("得分沙拉指令处理失败")
        response = CommandResponse("得分沙拉暂时无法处理这次操作，请稍后重试")
    current = service.games.get(group_id)
    playing = current is not None and current.phase is Phase.PLAYING
    if playing and not was_playing:
        await message_retention.activate(group_id, token, delete)
    try:
        receipt = await bot.send(event, response_message(response))
    except Exception as error:
        logger.opt(exception=error).error("得分沙拉回复发送失败")
        if playing or was_playing:
            await message_retention.complete(group_id, token, None, delete)
        else:
            message_retention.cancel(group_id, token)
        return
    if playing or was_playing:
        await message_retention.complete(
            group_id,
            token,
            receipt_message_id(receipt),
            delete,
        )
        if not playing:
            message_retention.clear(group_id)
    else:
        message_retention.cancel(group_id, token)


async def notify_timeout(group_id: str, phase: Phase) -> None:
    message_retention.clear(group_id)
    label = "大厅" if phase is Phase.LOBBY else "对局"
    message = f"得分沙拉{label}因长时间无人操作已自动关闭"
    for bot in nonebot.get_bots().values():
        try:
            await bot.send_group_msg(group_id=int(group_id), message=message)
            return
        except Exception:
            continue
    logger.warning(f"得分沙拉超时通知未送达：群 {group_id}")


service.timeout_callback = notify_timeout


async def load_games() -> None:
    try:
        await service.load()
        logger.info(f"得分沙拉已恢复 {len(service.games)} 局游戏")
    except Exception as error:
        logger.opt(exception=error).error("得分沙拉存档加载失败")


async def save_games() -> None:
    try:
        await service.save()
    except Exception as error:
        logger.opt(exception=error).error("得分沙拉存档保存失败")
    finally:
        service.close()


if driver is not None:
    driver.on_startup(load_games)
    driver.on_shutdown(save_games)
