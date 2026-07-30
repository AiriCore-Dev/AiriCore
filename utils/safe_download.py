import ipaddress
import socket
from urllib.parse import urljoin

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult
from multidict import CIMultiDict
from yarl import URL

from utils.net_guard import resolve_public_ips_async

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
