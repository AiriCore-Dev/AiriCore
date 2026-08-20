import asyncio
import copy
import pickle
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass

from nonebot import logger
from nonebot.adapters.onebot.v11 import Adapter as BaseAdapter, Bot, Event
from nonebot.adapters.onebot.v11.event import (
    GroupAdminNoticeEvent,
    GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent,
    GroupMessageEvent,
    MessageEvent,
)
from nonebot.adapters.onebot.v11.exception import NetworkError
from nonebot.adapters.onebot.store import ResultStore
from nonebot.message import event_preprocessor

QUERY_TTL = 7200.0
QUERY_TIMEOUT = 3.0
FAILURE_COOLDOWN = 30.0
MAX_ENTRIES = 4096
MAX_BYTES = 64 * 1024 * 1024
LATENCY_MAX_AGE = 300.0
LATENCY_MAX_BOTS = 128
UNCHANGED_GET_APIS = {
    "get_file",
    "get_image",
    "get_record",
    "download_file",
}
_MISS = object()
_ID_KEYS = {
    "group_id",
    "message_id",
    "self_id",
    "target_id",
    "user_id",
}
_OBSERVED_MAX = 8192
_OBSERVER_INSTALLED = False
_LATENCY_API_PREFIXES = ("get_", "send_", "set_", "delete_")
_LATENCY_EXCLUDED_PARTS = (
    "file",
    "upload",
    "download",
    "image",
    "record",
    "video",
    "audio",
    "forward",
    "list",
)
_LATENCY_TRANSFER_SEGMENTS = {
    "file",
    "image",
    "record",
    "video",
    "audio",
    "forward",
}


class SafeResultStore(ResultStore):
    def add_result(self, result: dict):
        echo = result.get("echo")
        if not isinstance(echo, str) or not echo.isdecimal():
            return
        future = self._futures.get(int(echo))
        if future is not None and not future.done():
            future.set_result(result)


def _is_timeout_error(exception) -> bool:
    text = f"{type(exception).__name__} {exception}".lower()
    return "timeout" in text or "timed out" in text or "超时" in text


@Bot.on_called_api
async def _log_timeout_api_error(bot, exception, api: str, data: dict, result):
    if exception is None or not _is_timeout_error(exception):
        return
    detail = str(exception).strip() or type(exception).__name__
    logger.error(f"Bot {bot.self_id} 调用接口 {api} 超时: {detail}")


def is_cached_query(api: str) -> bool:
    return (
        api.startswith("get_")
        and api not in UNCHANGED_GET_APIS
        and "file" not in api
    )


def _has_transfer_payload(value) -> bool:
    segment_type = str(getattr(value, "type", "") or "").lower()
    if segment_type in _LATENCY_TRANSFER_SEGMENTS:
        return True
    if isinstance(value, dict):
        if str(value.get("type", "")).lower() in _LATENCY_TRANSFER_SEGMENTS:
            return True
        return any(_has_transfer_payload(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_transfer_payload(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(f"[cq:{kind}" in lowered for kind in _LATENCY_TRANSFER_SEGMENTS)
    return False


def is_latency_sample_api(api: str, data=None) -> bool:
    name = str(api).lower()
    if not name.startswith(_LATENCY_API_PREFIXES):
        return False
    if any(part in name for part in _LATENCY_EXCLUDED_PARTS):
        return False
    return not _has_transfer_payload(data)


def _freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


def _params(data: dict) -> dict:
    params = {}
    for key, value in data.items():
        if key in {"_timeout", "no_cache"}:
            continue
        params[key] = str(value) if key in _ID_KEYS and value is not None else value
    return params


@dataclass
class CacheEntry:
    value: object
    expires_at: float
    size: int


@dataclass
class LatencySample:
    elapsed: float
    sampled_at: float


@dataclass
class ObservedMember:
    nickname: str
    card: str
    role: str
    expires_at: float


class QueryStore:
    def __init__(
        self,
        ttl=QUERY_TTL,
        timeout=QUERY_TIMEOUT,
        cooldown=FAILURE_COOLDOWN,
        max_entries=MAX_ENTRIES,
        max_bytes=MAX_BYTES,
        clock=time.monotonic,
    ):
        self.ttl = float(ttl)
        self.timeout = float(timeout)
        self.cooldown = float(cooldown)
        self.max_entries = int(max_entries)
        self.max_bytes = int(max_bytes)
        self.clock = clock
        self.cache = OrderedDict()
        self.inflight = {}
        self.failures = {}
        self.bytes = 0
        self.metrics = Counter()

    def key(self, bot_id: str, api: str, data: dict):
        return str(bot_id), str(api), _freeze(_params(data))

    def reset(self):
        for task in self.inflight.values():
            task.cancel()
        self.cache.clear()
        self.inflight.clear()
        self.failures.clear()
        self.metrics.clear()
        self.bytes = 0

    def _drop(self, key):
        entry = self.cache.pop(key, None)
        if entry is not None:
            self.bytes -= entry.size

    def _get(self, key):
        entry = self.cache.get(key)
        if entry is None:
            return _MISS
        if self.clock() >= entry.expires_at:
            self._drop(key)
            return _MISS
        self.cache.move_to_end(key)
        self.metrics["cache_hit"] += 1
        return copy.deepcopy(entry.value)

    def peek(self, bot_id: str, api: str, data: dict):
        return self._get(self.key(bot_id, api, data))

    def seed(self, bot_id: str, api: str, data: dict, value):
        key = self.key(bot_id, api, data)
        payload = copy.deepcopy(value)
        size = len(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))
        self._drop(key)
        self.cache[key] = CacheEntry(payload, self.clock() + self.ttl, size)
        self.bytes += size
        while len(self.cache) > self.max_entries or self.bytes > self.max_bytes:
            oldest = next(iter(self.cache))
            self._drop(oldest)

    def invalidate(self, bot_id: str, api: str, data: dict):
        self._drop(self.key(bot_id, api, data))

    def _derive(self, bot_id: str, api: str, data: dict, value):
        if api == "get_group_list" and isinstance(value, list):
            for group in value:
                if isinstance(group, dict) and group.get("group_id") is not None:
                    self.seed(
                        bot_id,
                        "get_group_info",
                        {"group_id": group["group_id"]},
                        group,
                    )
        if api == "get_group_member_list" and isinstance(value, list):
            group_id = data.get("group_id")
            for member in value:
                if not isinstance(member, dict) or member.get("user_id") is None:
                    continue
                member_group_id = member.get("group_id", group_id)
                if member_group_id is None:
                    continue
                payload = dict(member)
                payload.setdefault("group_id", member_group_id)
                self.seed(
                    bot_id,
                    "get_group_member_info",
                    {"group_id": member_group_id, "user_id": member["user_id"]},
                    payload,
                )

    async def _fetch(self, key, bot_id, api, data, caller):
        payload = dict(data)
        payload["_timeout"] = self.timeout
        self.metrics["kernel_query"] += 1
        try:
            value = await asyncio.wait_for(
                caller(payload),
                timeout=self.timeout,
            )
            self.seed(bot_id, api, data, value)
            self._derive(bot_id, api, data, value)
            self.failures.pop(key, None)
            return copy.deepcopy(value)
        except Exception as exc:
            self.failures[key] = (
                self.clock() + self.cooldown,
                type(exc).__name__,
                str(exc),
            )
            self.metrics["query_failure"] += 1
            raise
        finally:
            self.inflight.pop(key, None)

    async def run(self, bot_id: str, api: str, data: dict, caller):
        key = self.key(bot_id, api, data)
        cached = self._get(key)
        if cached is not _MISS:
            return cached
        failure = self.failures.get(key)
        if failure is not None:
            if self.clock() < failure[0]:
                self.metrics["cooldown_hit"] += 1
                raise NetworkError(f"查询 {api} 暂时冷却中")
            self.failures.pop(key, None)
        task = self.inflight.get(key)
        if task is None:
            task = asyncio.create_task(
                self._fetch(key, str(bot_id), str(api), dict(data), caller)
            )
            self.inflight[key] = task
        else:
            self.metrics["singleflight_hit"] += 1
        return copy.deepcopy(await asyncio.shield(task))


QUERY_STORE = QueryStore()
OBSERVED_MEMBERS = OrderedDict()
LATENCY_SAMPLES = OrderedDict()


def record_api_latency(bot_id, api: str, elapsed: float, data=None) -> None:
    if not is_latency_sample_api(api, data):
        return
    key = str(bot_id)
    LATENCY_SAMPLES[key] = LatencySample(float(elapsed), time.monotonic())
    LATENCY_SAMPLES.move_to_end(key)
    while len(LATENCY_SAMPLES) > LATENCY_MAX_BOTS:
        LATENCY_SAMPLES.popitem(last=False)


def latest_api_latency(bot_id, max_age=LATENCY_MAX_AGE):
    key = str(bot_id)
    sample = LATENCY_SAMPLES.get(key)
    if sample is None:
        return None
    if time.monotonic() - sample.sampled_at > float(max_age):
        LATENCY_SAMPLES.pop(key, None)
        return None
    return sample


def reset_query_state():
    QUERY_STORE.reset()
    OBSERVED_MEMBERS.clear()
    LATENCY_SAMPLES.clear()


def event_nickname(event: MessageEvent) -> str:
    sender = event.sender
    return str(
        getattr(sender, "card", "")
        or getattr(sender, "nickname", "")
        or event.user_id
    )


def session_key(event: MessageEvent) -> str:
    scene_id = event.group_id if isinstance(event, GroupMessageEvent) else event.user_id
    return f"QQClient_{scene_id}"


def avatar_url(user_id) -> str:
    return f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"


def event_session(bot: Bot, event: MessageEvent):
    from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
    from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, Session, User

    user_id = str(event.user_id)
    name = str(getattr(event.sender, "nickname", "") or user_id)
    card = str(getattr(event.sender, "card", "") or "")
    user = User(
        id=user_id,
        name=name,
        nick=card or name,
        avatar=avatar_url(user_id),
    )
    if isinstance(event, GroupMessageEvent):
        role_name = str(getattr(event.sender, "role", "member") or "member")
        role_level = {"owner": 100, "admin": 10, "member": 1}.get(role_name, 1)
        scene = Scene(id=str(event.group_id), type=SceneType.GROUP)
        member = Member(
            user=user,
            nick=card or name,
            roles=[Role(role_name.upper(), role_level, role_name)],
        )
    else:
        scene = Scene(
            id=user_id,
            type=SceneType.PRIVATE,
            name=name,
            avatar=avatar_url(user_id),
        )
        member = None
    return Session(
        self_id=str(bot.self_id),
        adapter=SupportAdapter.onebot11,
        scope=SupportScope.qq_client,
        scene=scene,
        user=user,
        member=member,
    )


def _observe_member(bot: Bot, event: GroupMessageEvent):
    key = str(bot.self_id), str(event.group_id), str(event.user_id)
    OBSERVED_MEMBERS[key] = ObservedMember(
        str(event.sender.nickname or ""),
        str(event.sender.card or ""),
        str(event.sender.role or "member"),
        time.monotonic() + QUERY_TTL,
    )
    OBSERVED_MEMBERS.move_to_end(key)
    while len(OBSERVED_MEMBERS) > _OBSERVED_MAX:
        OBSERVED_MEMBERS.popitem(last=False)


def observe_event(bot: Bot, event: Event) -> None:
    try:
        if isinstance(event, GroupMessageEvent):
            _observe_member(bot, event)
            return
        if not isinstance(
            event,
            (GroupIncreaseNoticeEvent, GroupDecreaseNoticeEvent, GroupAdminNoticeEvent),
        ):
            return
        bot_id = str(bot.self_id)
        group_id = int(event.group_id)
        user_id = int(event.user_id)
        QUERY_STORE.invalidate(
            bot_id,
            "get_group_member_list",
            {"group_id": group_id},
        )
        QUERY_STORE.invalidate(
            bot_id,
            "get_group_member_info",
            {"group_id": group_id, "user_id": user_id},
        )
        OBSERVED_MEMBERS.pop((bot_id, str(group_id), str(user_id)), None)
        if str(user_id) == bot_id:
            QUERY_STORE.invalidate(bot_id, "get_group_list", {})
    except Exception:
        return


async def _observe_event(bot: Bot, event: Event):
    observe_event(bot, event)


def install_event_observer() -> None:
    global _OBSERVER_INSTALLED
    if _OBSERVER_INSTALLED:
        return
    event_preprocessor(_observe_event)
    _OBSERVER_INSTALLED = True


def _observed_member(bot: Bot, group_id, user_id):
    key = str(bot.self_id), str(group_id), str(user_id)
    observed = OBSERVED_MEMBERS.get(key)
    if observed is None:
        return None
    if time.monotonic() >= observed.expires_at:
        OBSERVED_MEMBERS.pop(key, None)
        return None
    OBSERVED_MEMBERS.move_to_end(key)
    return observed


async def member_name(bot: Bot, group_id, user_id) -> str:
    observed = _observed_member(bot, group_id, user_id)
    if observed is not None:
        QUERY_STORE.metrics["event_hit"] += 1
        return observed.card or observed.nickname or str(user_id)
    cached = QUERY_STORE.peek(
        str(bot.self_id),
        "get_group_member_info",
        {"group_id": group_id, "user_id": user_id},
    )
    if cached is not _MISS and isinstance(cached, dict):
        QUERY_STORE.metrics["derived_hit"] += 1
        return str(cached.get("card") or cached.get("nickname") or user_id)
    try:
        info = await bot.get_group_member_info(
            group_id=int(group_id),
            user_id=int(user_id),
        )
    except Exception:
        return str(user_id)
    return str(info.get("card") or info.get("nickname") or user_id)


async def group_name(bot: Bot, group_id) -> str:
    try:
        info = await bot.get_group_info(group_id=int(group_id))
    except Exception:
        return str(group_id)
    return str(info.get("group_name") or group_id)


async def bot_name(bot: Bot, default="Airi") -> str:
    try:
        info = await bot.get_login_info()
    except Exception:
        return default
    return str(info.get("nickname") or default)


async def bot_profile(bot: Bot) -> dict:
    try:
        info = await bot.get_stranger_info(user_id=int(bot.self_id))
    except Exception:
        info = {}
    profile = dict(info) if isinstance(info, dict) else {}
    if not profile.get("nickname") and not profile.get("nick"):
        profile["nickname"] = await bot_name(bot, str(bot.self_id))
    profile.setdefault("uin", str(bot.self_id))
    return profile


class Adapter(BaseAdapter):
    _result_store = SafeResultStore()

    async def _call_api(self, bot, api: str, **data):
        if not is_cached_query(api):
            if not is_latency_sample_api(api, data):
                return await super()._call_api(bot, api, **data)
            started = time.monotonic()
            value = await super()._call_api(bot, api, **data)
            record_api_latency(bot.self_id, api, time.monotonic() - started, data)
            return value

        async def caller(payload):
            if not is_latency_sample_api(api, payload):
                return await super(Adapter, self)._call_api(bot, api, **payload)
            started = time.monotonic()
            value = await super(Adapter, self)._call_api(bot, api, **payload)
            record_api_latency(bot.self_id, api, time.monotonic() - started, payload)
            return value

        return await QUERY_STORE.run(bot.self_id, api, data, caller)
