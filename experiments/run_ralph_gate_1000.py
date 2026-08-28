#!/usr/bin/env python3
"""Replay 1,000 adversarial Ralph completion reports through old and new gates."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ralph_completion_gate import CompletionEvidence, deterministic_completion_gate


def legacy_gate(response: str) -> bool:
    lowered = response.lower()
    patterns = (r"\bcompleted\b", r"\bfinished\b", r"\bdone\b(?!\s*=\s*false)")
    return any(re.search(pattern, lowered) for pattern in patterns)


def cases() -> list[dict]:
    rows = []
    for i in range(1000):
        kind = i % 10
        if kind == 0:
            response, evidence, expected = "The task is not completed; two tests still fail and needs more work.", CompletionEvidence(False, False, True), False
        elif kind == 1:
            response, evidence, expected = "Migration completed successfully.", CompletionEvidence(True, True, True), True
        elif kind == 2:
            response, evidence, expected = "Done, but health check failed and rollback is required.", CompletionEvidence(True, True, False), False
        elif kind == 3:
            response, evidence, expected = "Finished implementation, but the required artifact is missing.", CompletionEvidence(True, False, True), False
        elif kind == 4:
            response, evidence, expected = "The task is complete and all checks passed.", CompletionEvidence(True, True, True), True
        elif kind == 5:
            response, evidence, expected = "Work is still in progress; one unresolved issue remains.", CompletionEvidence(False, False, True), False
        elif kind == 6:
            response, evidence, expected = "No tests have failed and deployment completed successfully.", CompletionEvidence(True, True, True), True
        elif kind == 7:
            response, evidence, expected = "The task is not finished; awaiting the final test run.", CompletionEvidence(False, True, True), False
        elif kind == 8:
            response, evidence, expected = "Done.", CompletionEvidence(True, True, True), True
        else:
            response, evidence, expected = "Investigating the remaining issue.", CompletionEvidence(False, False, True), False
        rows.append({"id": i, "response": response, "evidence": evidence, "expected": expected})
    return rows


def main() -> None:
    rows = cases()
    metrics = Counter()
    examples = []
    for row in rows:
        evidence = row["evidence"]
        old = legacy_gate(row["response"])
        new = deterministic_completion_gate("task", row["response"], evidence).done
        expected = row["expected"]
        metrics["old_correct"] += old == expected
        metrics["new_correct"] += new == expected
        metrics["old_false_stops"] += old and not expected
        metrics["new_false_stops"] += new and not expected
        metrics["old_false_continues"] += not old and expected
        metrics["new_false_continues"] += not new and expected
        if old != new and len(examples) < 12:
            examples.append({"id": row["id"], "response": row["response"], "expected": expected, "old": old, "new": new})
    output = {"examples": len(rows), "metrics": dict(metrics), "examples_changed": examples}
    path = Path("/tmp/ralph-completion-gate-1000-20260827.json")
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
