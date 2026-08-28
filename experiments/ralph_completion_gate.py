from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CompletionEvidence:
    tests_passed: bool
    required_artifacts_present: bool
    process_ok: bool
    completion_verified: bool = False


@dataclass(frozen=True)
class CompletionDecision:
    done: bool
    reason: str


_BLOCKING_PATTERNS = (
    r"\bnot\s+(?:yet\s+)?completed\b",
    r"\b(?:still|currently)\s+(?:has|have|contains?)\b",
    r"\b(?:fail(?:s|ed|ing)?|broken|unresolved|incomplete|unfinished)\b",
    r"\bneeds?\s+more\s+work\b",
    r"\brollback\s+(?:is\s+)?required\b",
)
_COMPLETION_PATTERNS = (
    r"\bcompleted\b",
    r"\bcomplete\b",
    r"\bfinished\b",
    r"\bdone\b",
    r"\bsuccess(?:ful|fully)\b",
)


def deterministic_completion_gate(
    task_text: str,
    response_text: str,
    evidence: CompletionEvidence,
) -> CompletionDecision:
    """Authorize Ralph completion only from response plus independent evidence."""
    del task_text  # Reserved for task-specific validators in the next layer.
    lowered = response_text.lower()
    normalized = re.sub(r"\bno\s+(?:tests?\s+)?(?:have\s+)?failed\b", "", lowered)
    normalized = re.sub(r"\bwithout\s+(?:any\s+)?failures?\b", "", normalized)
    has_blocker = any(re.search(pattern, normalized) for pattern in _BLOCKING_PATTERNS)
    has_completion = any(re.search(pattern, lowered) for pattern in _COMPLETION_PATTERNS)
    evidence_ok = (
        evidence.tests_passed
        and evidence.required_artifacts_present
        and evidence.process_ok
    )
    if has_blocker or not evidence_ok:
        return CompletionDecision(False, "blocking_evidence")
    if has_completion or evidence.completion_verified:
        return CompletionDecision(True, "verified_completion")
    return CompletionDecision(False, "no_completion_signal")
