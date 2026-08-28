#!/usr/bin/env python3
"""Measure two unrelated live adjudications sharing Lenovo's Ling slot."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.dual_model_adjudicator import DualModelAdjudicator
from experiments.run_live_adjudicator import stream_provider


async def main() -> None:
    prompts = [
        "Compute 23 multiplied by 17 and verify the result in one sentence.",
        "Compute 29 multiplied by 13 and verify the result in one sentence.",
    ]
    controller = DualModelAdjudicator(stream_provider, ling_timeout_s=45.0, ling_slots=1, ling_queue_limit=0)
    started = time.monotonic()
    outputs = await asyncio.gather(*(controller.run(prompt, session_id=f"concurrency-{i}") for i, prompt in enumerate(prompts)))
    rows = []
    for prompt, (result, events) in zip(prompts, outputs):
        rows.append({
            "prompt": prompt,
            "session_id": result.session_id,
            "status": result.status,
            "final_answer": result.final_answer,
            "ling_available": result.ling_available,
            "flags": result.flags,
            "lfm_draft_s": result.lfm_draft.elapsed_s if result.lfm_draft else None,
            "ling_s": result.ling_analysis_response.elapsed_s if result.ling_analysis_response else None,
            "ling_error": result.ling_analysis_response.error if result.ling_analysis_response else None,
            "events": len(events),
        })
    output = {"total_wall_s": time.monotonic() - started, "rows": rows}
    path = Path("/tmp/lenovo-live-adjudicator-concurrency-20260827.json")
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
