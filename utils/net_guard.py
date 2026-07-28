import ipaddress
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

_BLOCKED_PORTS = {22, 23, 25, 445, 3306, 5432, 6379, 9200, 11211, 27017}

_RESOLVE_TIMEOUT = 5.0
_executor = None
_executor_lock = threading.Lock()


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
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False
    return True


async def is_public_url_async(url) -> bool:
    import asyncio

    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(_get_executor(), is_public_url, url)
    try:
        return await asyncio.wait_for(asyncio.shield(fut), timeout=_RESOLVE_TIMEOUT)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        fut.add_done_callback(lambda f: f.exception())
        return False


def is_public_url(url) -> bool:
    try:
        parsed = urlparse(str(url))
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port
    if port is not None and port in _BLOCKED_PORTS:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        if not _ip_allowed(info[4][0]):
            return False
    return True
