import asyncio
import ipaddress
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

_BLOCKED_PORTS = {22, 23, 25, 445, 3306, 5432, 6379, 9200, 11211, 27017}

_RESOLVE_TIMEOUT = 5.0
_executor = None
_executor_lock = threading.Lock()
_resolve_slots = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is not None:
        return _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=4, thread_name_prefix="airi_netguard"
            )
        return _executor


def _ip_allowed(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if (
        not ip.is_global
        or ip.is_multicast
        or getattr(ip, "is_site_local", False)
    ):
        return False
    return True


async def is_public_url_async(url) -> bool:
    return bool(await resolve_public_ips_async(url))


async def resolve_public_ips_async(url) -> tuple[str, ...] | None:
    global _resolve_slots
    if _resolve_slots is None:
        _resolve_slots = asyncio.Semaphore(4)
    slots = _resolve_slots
    try:
        await asyncio.wait_for(slots.acquire(), timeout=_RESOLVE_TIMEOUT)
    except asyncio.TimeoutError:
        return None
    loop = asyncio.get_running_loop()
    try:
        fut = loop.run_in_executor(_get_executor(), resolve_public_ips, url)
    except Exception:
        slots.release()
        raise
    fut.add_done_callback(lambda _: slots.release())
    try:
        return await asyncio.wait_for(asyncio.shield(fut), timeout=_RESOLVE_TIMEOUT)
    except asyncio.TimeoutError:
        fut.add_done_callback(lambda f: f.exception())
        return None
    except asyncio.CancelledError:
        fut.add_done_callback(lambda f: f.exception())
        raise


def is_public_url(url) -> bool:
    return bool(resolve_public_ips(url))


def resolve_public_ips(url) -> tuple[str, ...] | None:
    try:
        parsed = urlparse(str(url))
        port = parsed.port
    except Exception:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    host = parsed.hostname
    if not host:
        return None
    if port is not None and port in _BLOCKED_PORTS:
        return None
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except Exception:
        return None
    if not infos:
        return None
    addresses = []
    for info in infos:
        address = info[4][0]
        if not _ip_allowed(address):
            return None
        if address not in addresses:
            addresses.append(address)
    return tuple(addresses)
