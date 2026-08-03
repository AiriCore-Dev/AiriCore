from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from nonebot.log import logger
from pydantic import BaseModel, Field

from plugins.airi_point_salad import service
from plugins.airi_point_salad.commands import parse_skill_arg, parse_slot
from plugins.airi_point_salad.game import GameError
from plugins.airi_point_salad.models import Phase
from plugins.airi_point_salad.renderer import render_board_images, render_turn_change
from plugins.airi_point_salad.web_api import WebRooms

from . import accounts, auth


router = APIRouter(prefix="/api/point-salad")
rooms = WebRooms(service)


class CreateBody(BaseModel):
    speed: Literal["quick", "standard"]
    mode: Literal["classic", "mix"]


class CodeBody(BaseModel):
    room_id: str


class RedeemBody(BaseModel):
    code: str


class HeartbeatBody(BaseModel):
    room_id: str


class ActionBody(BaseModel):
    action: Literal[
        "start",
        "leave",
        "stop",
        "take",
        "flip",
        "skill",
        "request_swap",
        "respond_swap",
    ]
    args: list = Field(default_factory=list)


def _qq(authorization: str):
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    qq = auth.verify_token(token)
    if not qq:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return qq


def _nick(qq):
    account = accounts.ensure_account(qq)
    return account.get("web_nick") or qq


def _result(value):
    return {"ok": True, "data": value}


def _skill_args(values):
    return [parse_skill_arg(str(value)) for value in values]


def _take_args(values):
    if len(values) == 1 and type(values[0]) is int:
        return [values[0] - 1]
    if len(values) == 2 and type(values[0]) is int:
        return [values[0] - 1, parse_slot(str(values[1]))]
    return [parse_slot(str(value)) for value in values]


def _request_swap_args(values):
    if len(values) != 1 or type(values[0]) is not str or not values[0].strip():
        raise ValueError("交换请求参数无效")
    return values[0].strip()


def _respond_swap_args(values):
    if len(values) != 1 or type(values[0]) is not bool:
        raise ValueError("交换响应参数无效")
    return values[0]


def _finished_action(room_id, state):
    payload = state.to_dict()
    payload["room_id"] = room_id
    payload["finished"] = True
    rooms.close(room_id, payload)
    return _result(payload)


async def _notify_group(room_id, before, after):
    if room_id.startswith("web:") or before is None:
        return
    from nonebot import get_bots
    from nonebot.adapters.onebot.v11 import MessageSegment

    bots = list(get_bots().values())
    if not bots or after.phase is not Phase.PLAYING:
        return
    bot = bots[0]
    group_id = int(room_id)
    change = render_turn_change(before, after)
    if change is not None:
        await bot.send_group_msg(group_id=group_id, message=MessageSegment.image(change))
    player = after.players[after.current_player]
    active = rooms.active(room_id, player.user_id)
    try:
        await bot.get_group_member_info(group_id=group_id, user_id=int(player.user_id), no_cache=True)
        member = True
    except Exception:
        member = False
    if active and member:
        message = MessageSegment.at(player.user_id) + " 轮到你了，请在网页端继续操作"
    else:
        board, _ = render_board_images(after, player.user_id)
        if member:
            message = MessageSegment.at(player.user_id) + MessageSegment.image(board)
        else:
            message = MessageSegment.image(board)
    await bot.send_group_msg(group_id=group_id, message=message)


@router.post("/rooms")
async def create_room(body: CreateBody, authorization: str = Header(default="")):
    qq = _qq(authorization)
    state = await rooms.create(qq, _nick(qq), body.speed, body.mode)
    payload = rooms.snapshot(state.group_id, qq)
    payload["room_code"] = await rooms.code(state.group_id, qq)
    return _result(payload)


@router.get("/rooms")
async def room_list(authorization: str = Header(default="")):
    return _result(rooms.list_rooms(_qq(authorization)))


@router.post("/codes")
async def create_code(body: CodeBody, authorization: str = Header(default="")):
    qq = _qq(authorization)
    try:
        return _result({"code": await rooms.code(body.room_id, qq), "ttl": None})
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/codes/redeem")
async def redeem_code(body: RedeemBody, authorization: str = Header(default="")):
    qq = _qq(authorization)
    try:
        state = await rooms.redeem(body.code, qq, _nick(qq))
        return _result(rooms.snapshot(state.group_id, qq))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/rooms/{room_id}")
async def room_snapshot(room_id: str, authorization: str = Header(default="")):
    qq = _qq(authorization)
    try:
        return _result(rooms.snapshot(room_id, qq))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/heartbeat")
async def heartbeat(body: HeartbeatBody, authorization: str = Header(default="")):
    qq = _qq(authorization)
    try:
        rooms.heartbeat(body.room_id, qq)
        return _result({"active": True})
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error))


@router.post("/rooms/{room_id}/actions")
async def action(room_id: str, body: ActionBody, authorization: str = Header(default="")):
    qq = _qq(authorization)
    if not rooms.allowed(room_id, qq):
        raise HTTPException(status_code=403, detail="无权访问该房间")
    try:
        before = await service.board_state(room_id)
        if body.action == "start":
            after = await service.start(room_id, qq)
        elif body.action == "leave":
            after = await service.leave(room_id, qq)
        elif body.action == "stop":
            after = await service.stop(room_id, qq, False)
        elif body.action == "flip":
            after = await service.flip(room_id, qq, int(body.args[0]) - 1)
        elif body.action == "skill":
            after = await service.skill(room_id, qq, _skill_args(body.args))
        elif body.action == "take":
            after = await service.take(room_id, qq, _take_args(body.args))
        elif body.action == "request_swap":
            after = await service.request_swap(
                room_id,
                qq,
                _request_swap_args(body.args),
            )
        elif body.action == "respond_swap":
            after = await service.respond_swap(
                room_id,
                qq,
                _respond_swap_args(body.args),
            )
        try:
            await _notify_group(room_id, before, after)
        except Exception:
            logger.exception("Point Salad 群聊回合提示发送失败")
        if body.action == "leave":
            rooms.revoke(room_id, qq)
            if after.phase is Phase.FINISHED:
                rooms.close(room_id)
            return _result({"room_id": room_id, "left": True})
        if after.phase is Phase.FINISHED:
            return _finished_action(room_id, after)
        return _result(rooms.snapshot(room_id, qq))
    except (GameError, IndexError, TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error) or "操作参数无效")
