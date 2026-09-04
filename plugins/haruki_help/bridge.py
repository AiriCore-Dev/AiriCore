import asyncio
import copy
import json
import time
from collections import OrderedDict
from typing import Any, Callable

import nonebot
import websockets
from nonebot import get_driver, logger
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.message import event_preprocessor

from utils import credit
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
CONTEXT_TTL = 180.0
CONTEXT_MAX = 4096


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
        self._contexts = OrderedDict()

    def select_bot(self) -> Bot | None:
        return self._bot_selector(nonebot.get_bots())

    @staticmethod
    def _default_bot_selector(bots: dict[str, Bot]) -> Bot | None:
        if not bots:
            return None
        return {str(key): value for key, value in bots.items()}[sorted(str(key) for key in bots)[0]]

    async def broadcast_event(self, event: Event) -> None:
        event_bot_id = getattr(event, "self_id", None)
        event_user_id = getattr(event, "user_id", None)
        if event_user_id is None:
            sender = getattr(event, "sender", None)
            if isinstance(sender, dict):
                event_user_id = sender.get("user_id")
            else:
                event_user_id = getattr(sender, "user_id", None)
        message_type = str(getattr(event, "message_type", "")).strip().lower()
        if event_bot_id is not None and event_user_id is not None and message_type in {"group", "private"}:
            bot_id = str(event_bot_id).strip()
            user_id = str(event_user_id).strip()
            if bot_id and user_id:
                self._last_bot_id = bot_id
                if message_type == "group" and getattr(event, "group_id", None) is not None:
                    self._remember_context("group", str(event.group_id), bot_id, user_id)
                elif message_type == "private":
                    self._remember_context("private", user_id, bot_id, user_id)
        socket = self._socket
        if socket is None:
            return
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
        user_id, context_bot_id = self._resolve_action_context(request, params, action)
        if not user_id:
            return self._failed("无法确定发送消息的用户", echo)
        try:
            if not await credit.has_account(user_id):
                return self._failed('❌ 账号未注册！\n请先签到一次！\n发送"签到"即可', echo)
            await credit.debit(user_id, MESSAGE_COST)
        except credit.InsufficientCreditsError:
            balance = await credit.get_balance(user_id)
            return self._failed(f"❌ 你的积分余额不足！\n现有积分：{balance}\n需要积分：{MESSAGE_COST}", echo)
        except Exception as exc:
            logger.warning(f"Haruki 消息扣除积分失败: {exc}")
            return self._failed("积分服务暂时不可用，消息未发送", echo)
        bot = self._select_action_bot(request, context_bot_id)
        if bot is None:
            await self._refund(user_id)
            return self._failed("当前没有可用的 Airi Bot", echo)
        try:
            call_params = dict(params)
            for key in ("sender_id", "operator_id"):
                call_params.pop(key, None)
            call_params.pop("self_id", None)
            if action in {"send_group_msg", "send_group_forward_msg"}:
                call_params.pop("user_id", None)
                call_params.pop("message_type", None)
            data = await bot.call_api(action, **call_params)
        except Exception as exc:
            await self._refund(user_id)
            return self._failed(f"消息发送失败: {exc}", echo)
        result = {"status": "ok", "retcode": 0, "data": data}
        if echo is not None:
            result["echo"] = echo
        return result

    @staticmethod
    def _explicit_user_id(request: dict) -> str:
        params = request.get("params")
        for source in (request, request.get("context"), request.get("meta"), request.get("data")):
            if isinstance(source, dict):
                for key in ("user_id", "sender_id", "operator_id"):
                    value = source.get(key)
                    if value is not None and str(value).strip():
                        return str(value).strip()
                for key in ("sender", "user", "operator", "caller"):
                    nested = source.get(key)
                    if isinstance(nested, dict):
                        for nested_key in ("user_id", "sender_id", "operator_id", "id"):
                            value = nested.get(nested_key)
                            if value is not None and str(value).strip():
                                return str(value).strip()
        if isinstance(params, dict):
            for key in ("sender_id", "operator_id"):
                value = params.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
            for key in ("sender", "user", "operator", "caller"):
                nested = params.get(key)
                if isinstance(nested, dict):
                    for nested_key in ("user_id", "sender_id", "operator_id", "id"):
                        value = nested.get(nested_key)
                        if value is not None and str(value).strip():
                            return str(value).strip()
        return ""

    def _remember_context(self, kind: str, key: str, bot_id: str, user_id: str) -> None:
        now = time.monotonic()
        token = (kind, key)
        self._contexts[token] = (bot_id, user_id, now)
        self._contexts.move_to_end(token)
        for stale, value in tuple(self._contexts.items()):
            if now - value[2] > CONTEXT_TTL:
                self._contexts.pop(stale, None)
        while len(self._contexts) > CONTEXT_MAX:
            self._contexts.popitem(last=False)

    def _get_context(self, kind: str, key: str):
        token = (kind, key)
        value = self._contexts.get(token)
        if value is None:
            return None
        if time.monotonic() - value[2] > CONTEXT_TTL:
            self._contexts.pop(token, None)
            return None
        self._contexts.move_to_end(token)
        return value

    def _resolve_action_context(self, request: dict, params: dict, action: str) -> tuple[str, str | None]:
        explicit = self._explicit_user_id(request)
        if explicit:
            return explicit, None
        message_type = str(params.get("message_type", "")).strip().lower()
        if action in {"send_group_msg", "send_group_forward_msg"} or message_type == "group" or (
            action in {"send_msg", "send_forward_msg"} and params.get("group_id") is not None
        ):
            user_id = params.get("user_id")
            if user_id is not None and str(user_id).strip():
                return str(user_id).strip(), None
            group_id = params.get("group_id")
            context = self._get_context("group", str(group_id)) if group_id is not None else None
            return (context[1], context[0]) if context else ("", None)
        if action in {"send_private_msg", "send_private_forward_msg"} or message_type == "private" or (
            action in {"send_msg", "send_forward_msg"} and params.get("user_id") is not None and params.get("group_id") is None
        ):
            target_id = params.get("user_id")
            context = self._get_context("private", str(target_id)) if target_id is not None else None
            if context:
                return context[1], context[0]
            return "", None
        return "", None

    @staticmethod
    async def _refund(user_id: str) -> None:
        try:
            await credit.credit(user_id, MESSAGE_COST)
        except Exception as exc:
            logger.warning(f"Haruki 消息退款失败: {exc}")

    def _select_action_bot(self, request: dict, context_bot_id: str | None = None) -> Bot | None:
        requested = request.get("self_id")
        if requested is None and isinstance(request.get("params"), dict):
            requested = request["params"].get("self_id")
        bots = nonebot.get_bots()
        if requested is not None:
            selected = {str(key): value for key, value in bots.items()}.get(str(requested))
            if selected is not None:
                return selected
        if context_bot_id:
            selected = {str(key): value for key, value in bots.items()}.get(context_bot_id)
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
