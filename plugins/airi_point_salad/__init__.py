import asyncio
from dataclasses import dataclass
from pathlib import Path
import re

import nonebot
from nonebot import get_driver, logger, on_regex
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from nonebot.plugin import PluginMetadata

from .commands import Command, CommandError, parse_command
from .game import GameError
from .models import GameMode, GameSpeed, GameState, Phase
from .persistence import GameStore
from .renderer import render_board, render_result
from .service import GameService


USAGE = (
    "MORE MORE JUMP！得分沙拉\n"
    "创建：沙拉 创建 快速 原版\n"
    "等价：salad create quick classic\n"
    "缩写：sl cr qk cl\n"
    "加入/退出：sl j / sl lv\n"
    "开始/结束：sl st / sl sp\n"
    "拿牌：sl ta A / sl ta A1 B2\n"
    "翻牌：sl fl 2\n"
    "技能：sl sk\n"
    "桌面/规则：sl bd / sl rl"
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
try:
    driver = get_driver()
except ValueError:
    driver = None
salad = on_regex(
    r"^\s*(?:沙拉|salad|sl)(?:\s+|$)",
    flags=re.IGNORECASE,
    priority=12,
    block=True,
)


@dataclass(frozen=True, slots=True)
class CommandResponse:
    body: str
    turn_user_id: str | None = None


def response_message(response: CommandResponse):
    if not response.body.startswith("base64://"):
        return response.body
    image = MessageSegment.image(response.body)
    if response.turn_user_id is None:
        return image
    return MessageSegment.at(response.turn_user_id) + image


def render_state(state: GameState, viewer_id: str) -> str:
    if state.phase is Phase.PLAYING:
        return render_board(state, viewer_id)
    if state.phase is Phase.FINISHED:
        if state.cards:
            return render_result(state)
        return "得分沙拉房间已关闭"
    return render_board(state, viewer_id)


async def execute_command(
    command: Command,
    group_id: str,
    user_id: str,
    user_name: str,
    is_admin: bool,
) -> CommandResponse:
    def prepare(state, turn_user_id):
        return CommandResponse(render_state(state, user_id), turn_user_id)

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
        return await service.start(group_id, user_id, prepare=prepare)
    if command.action == "take":
        return await service.take(group_id, user_id, command.args, prepare=prepare)
    if command.action == "flip":
        return await service.flip(group_id, user_id, command.args[0], prepare=prepare)
    if command.action == "skill":
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
    if command.action == "rules":
        return CommandResponse(await service.rules_text(group_id))
    raise CommandError("未知指令，请使用 sl rl 查看规则")


@salad.handle()
async def handle_salad(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await salad.finish("该游戏仅支持群聊")
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    user_name = event.sender.card or event.sender.nickname or user_id
    is_admin = event.sender.role in {"owner", "admin"}
    try:
        command = parse_command(event.get_plaintext())
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
    await salad.finish(response_message(response))


async def notify_timeout(group_id: str, phase: Phase) -> None:
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
