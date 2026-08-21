from __future__ import annotations

import base64
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable


CREDENTIAL_PATH = Path("/Users/liko/Store/credentials/gptimage2.key")
MODEL_ID = "gpt-image-2"


def _credentials(path: Path = CREDENTIAL_PATH) -> tuple[str, str]:
    values: dict[str, str] = {}
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if lines and not any("=" in line for line in lines):
        if len(lines) >= 3:
            baseurl, apikey, model = lines[:3]
            if model == MODEL_ID:
                return baseurl.rstrip("/"), apikey
        raise ValueError("生图凭据字段不完整或模型不是 gpt-image-2")
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.strip()
    baseurl = values.get("baseurl", "").rstrip("/")
    apikey = values.get("apikey", "")
    model = values.get("model") or values.get("model_id") or values.get("modelid")
    if not baseurl or not apikey or model != MODEL_ID:
        raise ValueError("生图凭据字段不完整或模型不是 gpt-image-2")
    return baseurl, apikey


def generate(
    prompt: str,
    output_path: Path,
    credential_path: Path = CREDENTIAL_PATH,
    opener: Callable[..., Any] = urllib.request.urlopen,
    request_factory: Callable[..., Any] = urllib.request.Request,
    timeout: int = 120,
) -> dict[str, str]:
    baseurl, apikey = _credentials(credential_path)
    body = json.dumps({"model": MODEL_ID, "prompt": str(prompt), "size": "1024x1024"}).encode("utf-8")
    root_url = baseurl[:-3] if baseurl.lower().endswith("/v1") else baseurl
    request = request_factory(root_url + "/images/generations", data=body, headers={"Authorization": f"Bearer {apikey}", "Content-Type": "application/json"}, method="POST")
    with opener(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    encoded = payload.get("data", [{}])[0].get("b64_json")
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("生图响应缺少图片")
    image_bytes = base64.b64decode(encoded, validate=True)
    if not image_bytes:
        raise ValueError("生图响应为空")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)
    return {"path": str(output_path), "model": MODEL_ID}


def generate_batch(
    jobs: list[tuple[str, Path]],
    credential_path: Path = CREDENTIAL_PATH,
    opener: Callable[..., Any] = urllib.request.urlopen,
    request_factory: Callable[..., Any] = urllib.request.Request,
    max_workers: int = 5,
) -> list[dict[str, str]]:
    if max_workers < 1:
        raise ValueError("并发数必须为正数")
    worker_count = min(5, max_workers, max(1, len(jobs)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(generate, prompt, path, credential_path, opener, request_factory) for prompt, path in jobs]
        return [future.result() for future in futures]
