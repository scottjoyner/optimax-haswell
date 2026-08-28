#!/usr/bin/env python3
"""Bounded live capacity matrix for Lenovo LFM and Ling endpoints."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

ENDPOINTS = {
    "lfm": ("http://100.105.137.98:1234/v1", "lenovo-lfm-cpu"),
    "ling": ("http://100.105.137.98:1236/v1", "lenovo-ling-specialist"),
}


async def one_request(model: str, prompt: str, max_tokens: int, timeout_s: float) -> dict[str, Any]:
    base_url, model_id = ENDPOINTS[model]
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "stream": True,
    }
    started = time.monotonic()
    first_token_s = None
    content: list[str] = []
    reasoning: list[str] = []
    finish_reason = None
    error = None
    timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{base_url}/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    event = json.loads(raw)
                    choice = (event.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    c = delta.get("content") or ""
                    r = delta.get("reasoning_content") or delta.get("reasoning") or ""
                    if (c or r) and first_token_s is None:
                        first_token_s = time.monotonic() - started
                    content.append(c)
                    reasoning.append(r)
                    finish_reason = choice.get("finish_reason") or finish_reason
    except asyncio.TimeoutError:
        error = f"controller timeout after {timeout_s}s"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {
        "model": model,
        "prompt": prompt,
        "elapsed_s": time.monotonic() - started,
        "first_token_s": first_token_s,
        "content": "".join(content),
        "reasoning_chars": len("".join(reasoning)),
        "finish_reason": finish_reason,
        "error": error,
        "usable": finish_reason == "stop" and bool("".join(content).strip()),
    }


async def run_case(name: str, model: str, prompts: list[str], max_tokens: int, timeout_s: float) -> dict[str, Any]:
    started = time.monotonic()
    results = await asyncio.gather(*(asyncio.wait_for(one_request(model, p, max_tokens, timeout_s), timeout=timeout_s) for p in prompts), return_exceptions=True)
    normalized = []
    for result in results:
        if isinstance(result, Exception):
            normalized.append({"model": model, "error": f"{type(result).__name__}: {result}", "usable": False})
        else:
            normalized.append(result)
    return {"case": name, "model": model, "n": len(prompts), "wall_s": time.monotonic() - started, "results": normalized}


async def main() -> None:
    prompt_a = "Compute 23 multiplied by 17. Return only the number."
    prompt_b = "Compute 29 multiplied by 13. Return only the number."
    cases = [
        run_case("lfm-x2", "lfm", [prompt_a, prompt_b], 32, 60.0),
        run_case("ling-x1", "ling", [prompt_a], 256, 30.0),
        run_case("ling-x2", "ling", [prompt_a, prompt_b], 256, 30.0),
    ]
    started = time.monotonic()
    output = {"started_at": time.time(), "cases": await asyncio.gather(*cases)}
    output["matrix_wall_s"] = time.monotonic() - started
    path = Path("/tmp/lenovo-live-capacity-matrix-20260827.json")
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
