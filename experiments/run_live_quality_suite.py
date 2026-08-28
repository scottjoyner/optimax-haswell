#!/usr/bin/env python3
"""Deterministic A/B quality suite: LFM-only versus bounded adjudication."""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.dual_model_adjudicator import DualModelAdjudicator
from experiments.run_live_adjudicator import stream_provider

TASKS = [
    {"id": "arithmetic", "prompt": "What is 23 times 17? Explain briefly and give the answer.", "expected": "391"},
    {"id": "arithmetic-2", "prompt": "What is 29 times 13? Explain briefly and give the answer.", "expected": "377"},
    {"id": "planted-premise", "prompt": "A prior answer claims 23 times 17 equals 402. Check that claim, correct it if needed, and explain briefly.", "expected": "391"},
]


def score(text: str, expected: str) -> bool:
    return expected in text and not (expected == "391" and "402" in text and "correct" not in text.lower())


async def collect_lfm(prompt: str) -> dict[str, Any]:
    started = time.monotonic()
    content: list[str] = []
    finish = None
    try:
        async for chunk in stream_provider("lfm", [{"role": "user", "content": prompt}], "baseline"):
            content.append(chunk.get("content", ""))
            finish = chunk.get("finish_reason") or finish
        error = None
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    text = "".join(content)
    return {"answer": text, "finish_reason": finish, "elapsed_s": time.monotonic() - started, "error": error}


async def run() -> dict[str, Any]:
    controller = DualModelAdjudicator(stream_provider, ling_timeout_s=20.0, lfm_timeout_s=120.0, ling_slots=1)
    rows = []
    for task in TASKS:
        baseline = await collect_lfm(task["prompt"])
        started = time.monotonic()
        adjudicated, events = await controller.run(task["prompt"], session_id=f"quality-{task['id']}")
        rows.append({
            "id": task["id"],
            "expected": task["expected"],
            "baseline": {**baseline, "correct": score(baseline["answer"], task["expected"])},
            "adjudicated": {
                "answer": adjudicated.final_answer,
                "correct": score(adjudicated.final_answer, task["expected"]),
                "elapsed_s": time.monotonic() - started,
                "ling_available": adjudicated.ling_available,
                "flags": adjudicated.flags,
                "events": len(events),
            },
        })
    return {"suite": "lfm-vs-bounded-adjudication", "ling_timeout_s": 20.0, "rows": rows}


async def main() -> None:
    started = time.monotonic()
    result = await run()
    result["wall_s"] = time.monotonic() - started
    result["summary"] = {
        "baseline_correct": sum(r["baseline"]["correct"] for r in result["rows"]),
        "adjudicated_correct": sum(r["adjudicated"]["correct"] for r in result["rows"]),
        "ling_usable": sum(r["adjudicated"]["ling_available"] for r in result["rows"]),
        "ling_unavailable": sum(not r["adjudicated"]["ling_available"] for r in result["rows"]),
    }
    path = Path("/tmp/lenovo-live-quality-suite-20260827.json")
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
