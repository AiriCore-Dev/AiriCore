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
from .render_runtime import run_sync, shutdown as shutdown_render_runtime
from .service import GameService
from .skills import skill_description


USAGE = (
    "MMJ 得分沙拉｜指令速查" 
    "创建房间：创建/create/cr + 快速/quick/qk 或 标准/standard/std + 原版/classic/cl 或 混合/mix/mx"
    "房间：加入/join/j · 退出/leave/lv · 开始/start/st · 结束/stop/sp"
    "行动：拿/take/ta · 翻/flip/fl · 技能/skill/sk"
    "查看：桌面/board/bd · 规则/rules/rl"
    "示例：,sl cr qk cl · ,sl ta A · ,sl ta A1 B2 · ,sl fl 2 · ,sl sk"
    "详细帮助请发送 ,sl rl 查看"
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
        response = await service.create(
            group_id,
            user_id,
            user_name,
            GameSpeed(command.args[0]),
            GameMode(command.args[1]),
            prepare=prepare,
        )
        try:
            from plugins.airi_game_server.point_salad_api import rooms

            code = await rooms.code(group_id, user_id)
            body = response.body
            if isinstance(body, tuple):
                body = (f"网页房间码：{code}", *body)
            else:
                body = (f"网页房间码：{code}", body)
            return CommandResponse(body, response.turn_user_id, response.turn_notice)
        except Exception:
            return response
    if command.action == "join":
        return await service.join(group_id, user_id, user_name, prepare=prepare)
    if command.action == "leave":
        response = await service.leave(group_id, user_id, prepare=prepare)
        if group_id not in service.games:
            try:
                from plugins.airi_game_server.point_salad_api import rooms

                rooms.close(group_id)
            except Exception as error:
                logger.opt(exception=error).error("得分沙拉网页房间清理失败")
        return response
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
        response = await service.stop(
            group_id,
            user_id,
            is_admin,
            prepare=prepare,
        )
        try:
            from plugins.airi_game_server.point_salad_api import rooms

            rooms.close(group_id)
        except Exception as error:
            logger.opt(exception=error).error("得分沙拉网页房间清理失败")
        return response
    if command.action == "board":
        state = await service.board_state(group_id)
        body = await run_sync(render_state, state, user_id)
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
    try:
        from plugins.airi_game_server.point_salad_api import rooms

        rooms.close(group_id)
    except Exception as error:
        logger.opt(exception=error).error("得分沙拉网页房间清理失败")
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
        shutdown_render_runtime()


if driver is not None:
    driver.on_startup(load_games)
    driver.on_shutdown(save_games)
