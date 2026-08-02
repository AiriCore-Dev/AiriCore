import asyncio
import json
import socket
import ssl
import urllib.error
import urllib.request
from typing import Any
from uuid import UUID, uuid4

from .config import AstralConfig
from .models import validate_response


class BackendError(RuntimeError):
    pass


class AstralBackendClient:
    def __init__(self, config: AstralConfig):
        self._config = config
        self._context = ssl.create_default_context(cafile=config.backend_ca_file or None)

    async def command(self, user_id: str, raw_command: str) -> tuple[UUID, dict[str, Any]]:
        request_id = uuid4()
        payload = {"request_id": str(request_id), "platform": "qq", "user_id": user_id, "command": raw_command}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        result = await asyncio.to_thread(self._post, body)
        return request_id, validate_response(result, request_id)

    def _post(self, body: bytes) -> Any:
        request = urllib.request.Request(self._config.backend_url + "/v1/command", data=body, method="POST", headers={"Authorization": f"Bearer {self._config.backend_token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, context=self._context, timeout=self._config.backend_timeout) as response:
                if response.status != 200:
                    raise BackendError("后端暂时不可用")
                return json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise BackendError("后端认证失败") from error
            raise BackendError("后端暂时不可用") from error
        except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError, json.JSONDecodeError) as error:
            raise BackendError("无法连接查询后端") from error
