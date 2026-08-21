from __future__ import annotations

import asyncio
import base64
import inspect
import json
from pathlib import Path
from typing import Any, Callable

from openai import AsyncOpenAI


CREDENTIAL_PATH = Path("/Users/liko/Store/credentials/gptimage2.key")
MODEL_ID = "gpt-image-2"
PROMPT_LIBRARY_PATH = Path(__file__).with_name("image_prompts.json")


def _credentials(path: Path = CREDENTIAL_PATH) -> tuple[str, str]:
    values: dict[str, str] = {}
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if lines and not any("=" in line for line in lines):
        if len(lines) >= 3:
            baseurl, apikey, model = lines[:3]
            if model == MODEL_ID:
                return baseurl, apikey
        raise ValueError("生图凭据字段不完整或模型不是 gpt-image-2")
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.strip()
    baseurl = values.get("baseurl", "")
    apikey = values.get("apikey", "")
    model = values.get("model") or values.get("model_id") or values.get("modelid")
    if not baseurl or not apikey or model != MODEL_ID:
        raise ValueError("生图凭据字段不完整或模型不是 gpt-image-2")
    return baseurl, apikey


def load_prompt_library(path: Path = PROMPT_LIBRARY_PATH) -> dict[str, Any]:
    library = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(library, dict) or not isinstance(library.get("prompts"), dict):
        raise ValueError("生图 prompt 库格式无效")
    return library


def build_prompt(template_name: str, values: dict[str, str], path: Path = PROMPT_LIBRARY_PATH) -> str:
    library = load_prompt_library(path)
    template = library["prompts"].get(template_name)
    if not isinstance(template, str):
        raise KeyError(f"未知生图 prompt 模板: {template_name}")
    return template.format(
        global_style=library["global_style"],
        negative_prompt=library["negative_prompt"],
        character_identity_rule=library["character_identity_rule"],
        **values,
    )


async def generate(
    prompt: str,
    output_path: Path,
    credential_path: Path = CREDENTIAL_PATH,
    client_factory: Callable[..., Any] = AsyncOpenAI,
    size: str = "1024x1024",
    quality: str = "high",
) -> dict[str, str]:
    baseurl, apikey = _credentials(credential_path)
    client = client_factory(api_key=apikey, base_url=baseurl)
    try:
        result = await client.images.generate(model=MODEL_ID, prompt=str(prompt), size=size, quality=quality, output_format="png", n=1)
        first = result.data[0]
        encoded = first.get("b64_json") if isinstance(first, dict) else getattr(first, "b64_json", None)
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            result = close()
            if inspect.isawaitable(result):
                await result
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("生图响应缺少图片")
    image_bytes = base64.b64decode(encoded, validate=True)
    if not image_bytes:
        raise ValueError("生图响应为空")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)
    return {"path": str(output_path), "model": MODEL_ID}


async def generate_batch(
    jobs: list[tuple[str, Path]],
    credential_path: Path = CREDENTIAL_PATH,
    client_factory: Callable[..., Any] = AsyncOpenAI,
    max_workers: int = 5,
) -> list[dict[str, str]]:
    if max_workers < 1:
        raise ValueError("并发数必须为正数")
    semaphore = asyncio.Semaphore(min(5, max_workers, max(1, len(jobs))))

    async def run_one(prompt: str, path: Path) -> dict[str, str]:
        async with semaphore:
            return await generate(prompt, path, credential_path, client_factory)

    return await asyncio.gather(*(run_one(prompt, path) for prompt, path in jobs))
