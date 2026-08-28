# Lenovo planted-error collaboration experiment

Date: 2026-08-27

## Purpose

Test whether Ling can catch deliberate errors in an LFM answer and whether LFM
can apply the critique without introducing new errors.

Protocol per case:

1. LFM reviews a seeded answer containing known mistakes.
2. Ling receives the LFM baseline and returns a compact critique.
3. LFM receives the critique and produces a revision.

LFM used a 768-token cap. Ling used a 2048-token cap.

## Results

| Case | LFM baseline | Ling critique | LFM revision |
|---|---|---|---|
| asyncio single-flight cache | 65.749 s, `length` | 351.886 s, `length`, no content | 68.389 s, `stop` |
| Lenovo routing policy | 28.638 s, `stop` | 308.764 s, `length`, no content | 54.443 s, `stop` |

Ling produced only reasoning on both critiques: 8,861 and 9,357 reasoning
characters respectively, with no usable structured output.

## Semantic result

### Async cache

The seeded implementation had known defects around race safety, shared-loader
cancellation, failure eviction, and timeout cleanup. LFM's baseline recognized
some problems but proposed invalid/incomplete corrections. Its revision still
contained an incorrect implementation and falsely claimed that timeout and
cancellation were handled. Ling was unavailable as a critic.

Result: failed. No correctness improvement.

### Routing policy

The seeded recommendation falsely claimed Ling should be the default, that two
Ling slots improve throughput, and that deadlines should be ignored. LFM's
baseline did identify these major problems. However, because Ling returned no
critique, the LFM revision became vague and introduced a false interpretation
that Ling's 177-second logic result was compatible with a 60-second bounded
task. It did not clearly state the one-slot policy.

Result: baseline caught the planted errors, but the collaboration did not
produce a trustworthy corrected final.

## Engineering conclusion

A model must not be allowed to certify executable correctness by prose. The
controller needs deterministic gates:

- run code answers through an actual test suite;
- validate routing answers against explicit measured enums and thresholds;
- reject Ling when it returns empty content or `finish_reason=length`;
- do not let LFM silently claim that an unavailable critique was applied;
- compare the revised answer against the LFM baseline and reject regressions;
- expose `ling_unavailable` and preserve the baseline when the critic fails.

The useful production architecture is therefore a bounded optional verifier, not
an always-on debate:

1. LFM produces a candidate.
2. A deterministic checker runs first.
3. Ling is called only for tasks where a second opinion is worth several minutes.
4. Ling returns compact issue findings or is marked unavailable.
5. LFM revises only validated issues.
6. The deterministic checker runs again.
7. The revision is accepted only if it passes and does not regress the baseline.

This experiment changed no production routing.
