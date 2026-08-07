import asyncio
import ipaddress
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult
from multidict import CIMultiDict
from yarl import URL

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

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class _PinnedResolver(AbstractResolver):
    def __init__(self, hostname: str, addresses: tuple[str, ...]):
        self.hostname = hostname
        self.addresses = addresses

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_INET,
    ) -> list[ResolveResult]:
        if host != self.hostname:
            raise OSError("下载地址解析异常")
        results = []
        for address in self.addresses:
            address_family = (
                socket.AF_INET6
                if ipaddress.ip_address(address).version == 6
                else socket.AF_INET
            )
            results.append(
                ResolveResult(
                    hostname=host,
                    host=address,
                    port=port,
                    family=address_family,
                    proto=socket.IPPROTO_TCP,
                    flags=socket.AI_NUMERICHOST,
                )
            )
        return results

    async def close(self) -> None:
        return None


async def download_public_bytes(
    url: str,
    max_bytes: int,
    max_redirects: int = 3,
    timeout: float = 15,
    headers: dict[str, str] | None = None,
) -> bytes:
    current_url = str(url).strip()
    for redirect_count in range(max_redirects + 1):
        addresses = await resolve_public_ips_async(current_url)
        if not addresses:
            raise ValueError("下载地址不安全")
        hostname = URL(current_url).raw_host
        if not hostname:
            raise ValueError("下载地址不安全")
        resolver = _PinnedResolver(hostname, addresses)
        connector = aiohttp.TCPConnector(
            resolver=resolver,
            use_dns_cache=False,
            ttl_dns_cache=0,
        )
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        request_headers = CIMultiDict(headers or {})
        request_headers["Accept-Encoding"] = "identity"
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=client_timeout,
            headers=request_headers,
            auto_decompress=False,
            trust_env=False,
        ) as client:
            async with client.get(current_url, allow_redirects=False) as response:
                if response.status in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location or redirect_count >= max_redirects:
                        raise ValueError("下载重定向无效或次数过多")
                    current_url = urljoin(current_url, location)
                    continue
                response.raise_for_status()
                content_encodings = [
                    token.strip().lower()
                    for value in response.headers.getall("content-encoding", [])
                    for token in value.split(",")
                ]
                if any(token not in ("", "identity") for token in content_encodings):
                    raise ValueError("下载响应使用了不支持的压缩编码")
                content_length = response.content_length
                if content_length is not None and content_length > max_bytes:
                    raise ValueError("下载内容超过大小限制")
                chunks = []
                size = 0
                async for chunk in response.content.iter_chunked(65536):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("下载内容超过大小限制")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise ValueError("下载重定向次数过多")

