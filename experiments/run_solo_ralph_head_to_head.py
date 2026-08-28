#!/usr/bin/env python3
"""Bounded solo Ralph loops for Lenovo LFM and Ling, with deterministic validators."""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from experiments.ralph_completion_gate import CompletionEvidence, deterministic_completion_gate

ENDPOINTS = {
    "lfm": ("http://100.105.137.98:1234/v1", "lenovo-lfm-cpu"),
    "ling": ("http://100.105.137.98:1236/v1", "lenovo-ling-specialist"),
}
TASKS = [
    {"id": "arithmetic", "prompt": "Calculate 17 multiplied by 19. Give the result and one-sentence verification.", "validator": lambda s: bool(re.search(r"\b323\b", s))},
    {"id": "switches", "prompt": "Three switches are outside a room and one bulb is inside. You may manipulate switches before entering once. Explain how to identify the correct switch.", "validator": lambda s: all(x in s.lower() for x in ("on", "off", "warm"))},
    {"id": "false_premise", "prompt": "A migration is complete even though two tests still fail. State whether it is complete and what must happen next.", "validator": lambda s: ("not complete" in s.lower() or "incomplete" in s.lower()) and ("test" in s.lower() or "fix" in s.lower())},
]

async def call_model(model: str, messages: list[dict[str, str]], timeout: float) -> dict[str, Any]:
    base, model_id = ENDPOINTS[model]
    payload = {"model": model_id, "messages": messages, "temperature": 0.1, "max_tokens": 512 if model == "lfm" else 768, "stream": False}
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=timeout, write=20, pool=20)) as client:
            response = await client.post(f"{base}/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        return {"ok": True, "text": text, "finish_reason": choice.get("finish_reason"), "elapsed_s": time.monotonic() - started, "completion_tokens": (body.get("usage") or {}).get("completion_tokens")}
    except Exception as exc:
        return {"ok": False, "text": "", "error": f"{type(exc).__name__}: {exc}", "elapsed_s": time.monotonic() - started}

async def run_one(model: str, task: dict[str, Any], max_iters: int, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    messages = [{"role": "system", "content": "You are the worker in a bounded Ralph loop. Solve the task. On each iteration report work and next step. Only say the task is completed when your answer is actually finished."}, {"role": "user", "content": task["prompt"]}]
    iterations = []
    for iteration in range(1, max_iters + 1):
        result = await call_model(model, messages, timeout)
        text = result["text"]
        valid = bool(task["validator"](text)) if text else False
        evidence = CompletionEvidence(tests_passed=valid, required_artifacts_present=True, process_ok=result["ok"], completion_verified=valid)
        decision = deterministic_completion_gate(task["prompt"], text, evidence)
        row = {"iteration": iteration, **result, "validator_passed": valid, "gate_done": decision.done, "gate_reason": decision.reason}
        iterations.append(row)
        if decision.done:
            return {"model": model, "task_id": task["id"], "complete": True, "iterations": iteration, "elapsed_s": time.monotonic() - started, "iterations_detail": iterations}
        messages.extend([{ "role": "assistant", "content": text or "(no usable response)" }, {"role": "user", "content": "Continue with the next bounded iteration. Re-check the answer against the task and finish only when it is correct; explicitly state whether the task is completed."}])
    return {"model": model, "task_id": task["id"], "complete": False, "iterations": max_iters, "elapsed_s": time.monotonic() - started, "iterations_detail": iterations}

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/lenovo-solo-ralph-head-to-head-20260828.json")
    parser.add_argument("--max-iters", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    started = time.monotonic()
    results = []
    for task in TASKS:
        for model in ("lfm", "ling"):
            results.append(await run_one(model, task, args.max_iters, args.timeout))
    output = {"started_at": time.time(), "elapsed_s": time.monotonic() - started, "max_iters": args.max_iters, "timeout_s": args.timeout, "results": results}
    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    summary = [{"model": r["model"], "task": r["task_id"], "complete": r["complete"], "iterations": r["iterations"], "elapsed_s": round(r["elapsed_s"], 2)} for r in results]
    print(json.dumps({"elapsed_s": round(output["elapsed_s"], 2), "summary": summary}, indent=2))
    print(f"wrote {args.output}")

if __name__ == "__main__":
    asyncio.run(main())
