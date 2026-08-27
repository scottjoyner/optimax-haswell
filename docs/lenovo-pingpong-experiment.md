# Lenovo bounded ping-pong experiment: async single-flight cache

Date: 2026-08-27

## Experiment

Two independent model conversations were started against the production Lenovo
lanes. The task was to implement and test a Python 3.11 asyncio single-flight
cache with requirements covering duplicate suppression, shared successful
results, exception eviction, waiter cancellation, timeout cleanup, and
concurrent different-key loads.

The protocol was:

1. LFM and Ling independently solve the task.
2. Each model receives the other model's answer and produces a critique.
3. Each model receives the other model's critique and produces a revised final.

LFM used a 768-token cap. Ling used a 2048-token cap. Calls within each exchange
were simultaneous, but each model lane remained single-slot.

## Live measurements

| Model | Exchange | Time | Finish | Content chars | Reasoning chars |
|---|---|---:|---|---:|---:|
| LFM | independent | 311.673 s | length | 3058 | 0 |
| Ling | independent | 392.374 s | length | 0 | 8826 |
| LFM | cross-critique | 310.790 s | length | 2916 | 0 |
| Ling | cross-critique | 471.427 s | length | 0 | 8216 |
| LFM | revised final | 331.926 s | length | 3118 | 0 |
| Ling | revised final | 492.156 s | length | 0 | 9448 |

All six HTTP calls returned model responses without transport errors. The
experiment harness failed while serializing the final JSON because of a local
Python variable-name bug after the final calls completed. Therefore final answer
text was not persisted and no correctness claim is made from this run.

## Finding

The naïve full-prose ping-pong protocol is not practical on this node. One full
three-exchange debate consumed approximately 33 minutes of model wall time,
and Ling never emitted final content at its 2048-token cap on any of its three
turns. Forwarding full implementation prose caused each critique/revision to
become another long reasoning task rather than a compact verification step.

This does not disprove the complementary-model idea. It rejects this protocol
shape. A useful protocol must make inter-model turns structurally small and
machine-checkable:

- LFM first pass with a bounded answer;
- Ling receives only a compact claim list, selected code, and explicit rubric;
- Ling returns JSON findings only: `pass`, `fail`, `uncertain`, `issue_ids`, and
  `required_fixes`;
- LFM revises only the identified issues;
- at most one Ling adjudication turn;
- hard stop on empty final content or `finish_reason=length`;
- a deterministic test runner, not the other model, decides executable
  correctness where possible.

A future ping-pong benchmark should use a smaller task with a known oracle,
strict JSON critique output, 2-3 total model turns, and a wall-clock budget.
The current production role remains unchanged: LFM for bounded work and Ling
for deliberately scoped long-horizon escalation.
