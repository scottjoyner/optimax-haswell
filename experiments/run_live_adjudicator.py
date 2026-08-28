#!/usr/bin/env python3
"""Run the experiment-only dual-model adjudicator against Lenovo endpoints."""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from experiments.dual_model_adjudicator import DualModelAdjudicator

ENDPOINTS = {
    "lfm": ("http://100.105.137.98:1234/v1", "lenovo-lfm-cpu"),
    "ling": ("http://100.105.137.98:1236/v1", "lenovo-ling-specialist"),
}


async def stream_provider(model: str, messages: list[dict[str, str]], phase: str) -> AsyncIterator[dict[str, Any]]:
    base_url, model_id = ENDPOINTS[model]
    max_tokens = 768 if model == "lfm" else 1536
    if phase == "final":
        max_tokens = 768
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "stream": True,
    }
    timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        started = time.monotonic()
        async with client.stream("POST", f"{base_url}/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    return
                event = json.loads(raw)
                choice = (event.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                yield {
                    "content": delta.get("content") or "",
                    "reasoning_content": delta.get("reasoning_content") or delta.get("reasoning") or "",
                    "finish_reason": choice.get("finish_reason"),
                    "elapsed_s": time.monotonic() - started,
                }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--output", default="/tmp/lenovo-live-adjudicator.json")
    parser.add_argument("--ling-timeout", type=float, default=300.0)
    args = parser.parse_args()

    events = []

    async def persist_event(event: dict[str, Any]) -> None:
        # Keep this callback intentionally lightweight; the final JSON is written
        # atomically after the run, while every event remains in result['events'].
        return None

    controller = DualModelAdjudicator(
        stream_provider,
        ling_timeout_s=args.ling_timeout,
        lfm_timeout_s=180.0,
        event_sink=persist_event,
    )
    started = time.monotonic()
    result, captured = await controller.run(args.prompt)
    output = {
        "started_at": time.time(),
        "elapsed_s": time.monotonic() - started,
        "prompt": args.prompt,
        "result": {
            "session_id": result.session_id,
            "status": result.status,
            "final_answer": result.final_answer,
            "ling_available": result.ling_available,
            "flags": result.flags,
            "lfm_draft": result.lfm_draft.__dict__ if result.lfm_draft else None,
            "ling_analysis": result.ling_analysis_response.__dict__ if result.ling_analysis_response else None,
        },
        "events": captured,
    }
    path = Path(args.output)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output["result"], indent=2, ensure_ascii=False))
    print(f"wrote {path} elapsed_s={output['elapsed_s']:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
