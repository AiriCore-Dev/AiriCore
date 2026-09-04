import asyncio
import copy
import json
from typing import Any, Callable

import nonebot
import websockets
from nonebot import get_driver, logger
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.message import event_preprocessor

from utils import credits
from utils.coordination import registry


DEFAULT_WS_LINK = "ws://localhost:2345/ws"
MESSAGE_ACTIONS = {
    "send_msg",
    "send_private_msg",
    "send_group_msg",
    "send_forward_msg",
    "send_private_forward_msg",
    "send_group_forward_msg",
}
MESSAGE_COST = 10


def get_ws_link(config: Any) -> str:
    raw = config.get("haruki_ws_link", "") if isinstance(config, dict) else getattr(config, "haruki_ws_link", "")
    value = str(raw or "").strip()
    return value or DEFAULT_WS_LINK


def _event_payload(event: Event) -> dict:
    if hasattr(event, "model_dump"):
        try:
            payload = event.model_dump(mode="json", exclude_none=False)
        except TypeError:
            payload = event.model_dump()
    elif hasattr(event, "dict"):
        payload = event.dict()
    else:
        payload = dict(getattr(event, "__dict__", {}))
    if "original_message" in payload:
        payload["message"] = copy.deepcopy(payload["original_message"])
    return {str(key): value for key, value in payload.items()}


def _json_safe(value):
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return str(value)


class HarukiBridge:

    def __init__(self, bot_selector: Callable[[dict[str, Bot]], Bot | None] | None = None, ws_link: str = DEFAULT_WS_LINK):
        self.ws_link = ws_link
        self._bot_selector = bot_selector or self._default_bot_selector
        self._socket = None
        self._send_lock = asyncio.Lock()
        self._stopping = False
        self._last_bot_id = ""
        self._group_context = {}

    def select_bot(self) -> Bot | None:
        return self._bot_selector(nonebot.get_bots())

    @staticmethod
    def _default_bot_selector(bots: dict[str, Bot]) -> Bot | None:
        if not bots:
            return None
        return {str(key): value for key, value in bots.items()}[sorted(str(key) for key in bots)[0]]

    async def broadcast_event(self, event: Event) -> None:
        socket = self._socket
        if socket is None:
            return
        event_user_id = getattr(event, "user_id", None)
        event_bot_id = getattr(event, "self_id", None)
        if event_bot_id is not None and str(event_bot_id).strip():
            self._last_bot_id = str(event_bot_id).strip()
        event_group_id = getattr(event, "group_id", None)
        if event_group_id is not None and event_user_id is not None and event_bot_id is not None:
            self._group_context[str(event_group_id)] = (str(event_bot_id), str(event_user_id))
        payload = _json_safe(_event_payload(event))
        try:
            async with self._send_lock:
                await socket.send(json.dumps(payload, ensure_ascii=False))
        except Exception:
            if self._socket is socket:
                self._socket = None

    async def handle_action(self, request: dict) -> dict:
        action = str(request.get("action", "")).strip()
        params = request.get("params")
        if not isinstance(params, dict):
            params = {}
        echo = request.get("echo")
        if action not in MESSAGE_ACTIONS:
            return self._failed("不支持的 OneBot 操作", echo)
        user_id = self._action_user_id(request, params, action)
        if not user_id:
            return self._failed("无法确定发送消息的用户", echo)
        try:
            if not await credits.has_account(user_id):
                return self._failed('❌ 账号未注册！\n请先签到一次！\n发送"签到"即可', echo)
            await credits.debit(user_id, MESSAGE_COST)
        except credits.InsufficientCreditsError:
            balance = await credits.get_balance(user_id)
            return self._failed(f"❌ 你的积分余额不足！\n现有积分：{balance}\n需要积分：{MESSAGE_COST}", echo)
        except Exception as exc:
            logger.warning(f"Haruki 消息扣除积分失败: {exc}")
            return self._failed("积分服务暂时不可用，消息未发送", echo)
        bot = self._select_action_bot(request)
        if bot is None:
            await self._refund(user_id)
            return self._failed("当前没有可用的 Airi Bot", echo)
        try:
            call_params = dict(params)
            if action in {"send_group_msg", "send_group_forward_msg"}:
                call_params.pop("user_id", None)
            data = await bot.call_api(action, **call_params)
        except Exception as exc:
            await self._refund(user_id)
            return self._failed(f"消息发送失败: {exc}", echo)
        result = {"status": "ok", "retcode": 0, "data": data}
        if echo is not None:
            result["echo"] = echo
        return result

    @staticmethod
    def _action_user_id(request: dict, params: dict, action: str) -> str:
        for source in (request, request.get("context"), request.get("meta"), request.get("data")):
            if isinstance(source, dict):
                for key in ("user_id", "sender_id", "operator_id"):
                    value = source.get(key)
                    if value is not None and str(value).strip():
                        return str(value).strip()
        for key in ("sender_id", "operator_id"):
            value = params.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @staticmethod
    async def _refund(user_id: str) -> None:
        try:
            await credits.credit(user_id, MESSAGE_COST)
        except Exception as exc:
            logger.warning(f"Haruki 消息退款失败: {exc}")

    def _select_action_bot(self, request: dict) -> Bot | None:
        requested = request.get("self_id")
        if requested is None and isinstance(request.get("params"), dict):
            requested = request["params"].get("self_id")
        bots = nonebot.get_bots()
        if requested is not None:
            selected = {str(key): value for key, value in bots.items()}.get(str(requested))
            if selected is not None:
                return selected
        group_id = request.get("params", {}).get("group_id") if isinstance(request.get("params"), dict) else None
        context = self._group_context.get(str(group_id)) if group_id is not None else None
        if context:
            selected = {str(key): value for key, value in bots.items()}.get(context[0])
            if selected is not None:
                return selected
        if self._last_bot_id:
            selected = {str(key): value for key, value in bots.items()}.get(self._last_bot_id)
            if selected is not None:
                return selected
        return self.select_bot()

    @staticmethod
    def _failed(message: str, echo=None) -> dict:
        result = {"status": "failed", "retcode": 1400, "data": {"message": message}, "message": message}
        if echo is not None:
            result["echo"] = echo
        return result

    async def run(self) -> None:
        self._stopping = False
        while not self._stopping:
            try:
                async with websockets.connect(self.ws_link, ping_interval=20, ping_timeout=20) as socket:
                    self._socket = socket
                    logger.info(f"Haruki 反向 WebSocket 已连接: {self.ws_link}")
                    async for raw in socket:
                        try:
                            request = json.loads(raw)
                        except (TypeError, ValueError):
                            continue
                        if not isinstance(request, dict):
                            continue
                        response = await self.handle_action(request)
                        async with self._send_lock:
                            await socket.send(json.dumps(response, ensure_ascii=False))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not self._stopping:
                    logger.warning(f"Haruki 反向 WebSocket 连接失败: {exc}")
                    await asyncio.sleep(5)
            finally:
                self._socket = None

    async def stop(self) -> None:
        self._stopping = True
        socket = self._socket
        if socket is not None:
            await socket.close()


driver = get_driver()
bridge = HarukiBridge(ws_link=get_ws_link(driver.config))


@event_preprocessor
async def _share_event(bot: Bot, event: Event):
    await bridge.broadcast_event(event)


@driver.on_startup
async def _start_bridge():
    registry.create(bridge.run(), owner="haruki_help", key="reverse_ws")


@driver.on_shutdown
async def _stop_bridge():
    await bridge.stop()
