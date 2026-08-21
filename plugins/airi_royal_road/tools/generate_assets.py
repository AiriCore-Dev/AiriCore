from __future__ import annotations

import base64
import json
import os
import urllib.request
from pathlib import Path


CREDENTIAL_PATH = Path("/Users/liko/Store/credentials/gptimage2.key")


def _credentials() -> tuple[str, str, str]:
    values = {}
    for line in CREDENTIAL_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip().lower()] = value.strip()
    baseurl = values.get("baseurl", "")
    apikey = values.get("apikey", "")
    model = values.get("model") or values.get("model_id") or values.get("modelid") or "gpt-image-2"
    if not baseurl or not apikey or not model:
        raise ValueError("生图凭据字段不完整")
    return baseurl, apikey, model


def generate(prompt: str, output_path: Path, request=None) -> dict:
    baseurl, apikey, model = _credentials()
    body = json.dumps({"model": model, "prompt": prompt, "size": "1024x1024"}).encode("utf-8")
    request = request or urllib.request.Request(baseurl.rstrip("/") + "/images/generations", data=body, headers={"Authorization": f"Bearer {apikey}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    encoded = payload["data"][0].get("b64_json")
    if not encoded:
        raise ValueError("生图响应缺少图片")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(encoded))
    return {"path": str(output_path), "model": "gpt-image-2"}
