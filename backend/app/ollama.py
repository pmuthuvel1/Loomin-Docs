from __future__ import annotations

import time
from typing import Any

import httpx

from .config import OLLAMA_URL


async def generate(model: str, prompt: str) -> tuple[str, dict[str, Any]]:
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}},
        )
        response.raise_for_status()
        data = response.json()
    elapsed = max(time.perf_counter() - started, 0.001)
    answer = data.get("response", "")
    tokens = max(1, len(answer) // 4)
    return answer, {
        "generation_ms": round(elapsed * 1000),
        "tokens_per_second": tokens / elapsed,
        "eval_count": data.get("eval_count"),
        "eval_duration": data.get("eval_duration"),
    }
