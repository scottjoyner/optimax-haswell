# Structured Lenovo ping-pong experiment

Date: 2026-08-27

## Protocol

A compact, evidence-grounded routing task was sent to the two production models.
The prompt required strict JSON containing bounded-task routing, long-horizon
routing, deadline policy, concurrency policy, caveats, and explicit fallback
behavior. The models independently answered, then each was asked to critique the
other model's JSON. LFM then produced a final JSON decision from both answers and
critiques.

LFM used a 512-token cap; Ling used a 1024-token cap. Calls within an exchange
were concurrent, with one request per model lane.

## Measurements

| Model | Phase | Time | Finish | Final content | Reasoning chars |
|---|---|---:|---|---:|---:|
| LFM | independent | 54.931 s | stop | 510 chars | 0 |
| Ling | independent | 157.058 s | length | 0 chars | 3536 |
| LFM | critique | 65.030 s | stop | 511 chars | 0 |
| Ling | critique | 166.346 s | length | 0 chars | 4356 |
| LFM | final | 25.446 s | stop | 510 chars | 0 |

## Semantic score

The final LFM JSON was syntactically valid and included generic routing
language, but it did not explicitly identify LFM as the bounded-task provider,
Ling as the long-horizon provider, or the required one-slot Ling policy. It did
mention fallback on `finish_reason=length`.

Manual rubric: 1/5 substantive requirements passed, with fallback only partial.
A loose keyword checker incorrectly reported 2/5 because it treated generic
words such as “immediate” and “future planning” as model-specific routing.

## Findings

1. Strict JSON does not guarantee correct or evidence-grounded JSON.
2. Ling again failed to emit usable final content at 1024 tokens, even on a
   compact routing task.
3. A final LFM synthesis can complete quickly after the Ling failure, but it may
   silently omit the missing critic's contribution unless the orchestrator
   records that the critic was unavailable.
4. Deterministic scoring must use explicit fields/enums and semantic checks, not
   keyword presence.
5. The orchestrator should reject a model response that omits required enum
   values rather than accepting vague equivalents.

## Revised protocol recommendation

For future experiments, constrain output to explicit enums:

- `bounded_provider`: `lfm`
- `long_horizon_provider`: `ling`
- `ling_slots`: `1`
- `hard_deadline_fallback`: `lfm`
- `length_or_empty_fallback`: `retry_or_lfm`
- `confidence`: numeric

The model should return only these fields and a short `rationale_codes` array.
A deterministic validator should reject missing or invalid enum values. Ling
should be used as a critic only when it returns parseable output before its
budget deadline. If Ling fails, the final result must expose `ling_unavailable`
rather than silently treating the exchange as a successful two-model decision.

The production model roles remain unchanged. This experiment was a protocol
qualification exercise, not a routing-policy change.
