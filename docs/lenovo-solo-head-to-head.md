# Lenovo solo LFM vs Ling head-to-head

Date: 2026-08-27

This is a solo benchmark of the two production chat models on Lenovo. Each model
was run through the complete case set before the other model was tested. The
models were not competing with one another during these measurements. Streaming
was enabled, temperature was 0, and the case-specific maximum completion budget
is shown below.

## Results

| Model | Case | Max tokens | Finish | Total time | Completion tokens | Decode rate | Final content |
|---|---|---:|---|---:|---:|---:|---|
| LFM CPU | arithmetic | 256 | stop | 17.788 s | 218 | 12.26 tok/s | correct: 760 |
| LFM CPU | logic | 512 | stop | 27.120 s | 316 | 11.65 tok/s | correct |
| LFM CPU | logic | 1024 | stop | 26.592 s | 316 | 11.88 tok/s | correct |
| LFM CPU | logic | 2048 | stop | 27.162 s | 316 | 11.63 tok/s | correct |
| LFM CPU | rollout planning | 1024 | length | 90.686 s | 1024 | 11.29 tok/s | incomplete |
| LFM CPU | rollout planning | 2048 | stop | 111.070 s | not retained | not computed | completed plan |
| Ling iGPU | arithmetic | 256 | length | 30.714 s | 256 | 8.33 tok/s | no final content |
| Ling iGPU | logic | 512 | length | 59.594 s | 512 | 8.59 tok/s | no final content |
| Ling iGPU | logic | 1024 | length | 117.917 s | 1024 | 8.68 tok/s | no final content |
| Ling iGPU | logic | 2048 | stop | 176.707 s | 1477 | 8.36 tok/s | correct |
| Ling iGPU | rollout planning | 1024 | length | 120.873 s | 1024 | 8.47 tok/s | no final content |
| Ling iGPU | rollout planning | 2048 | length | 257.845 s | 2048 | not computed | no final content |

The 2048-token logic run is the important Ling result: it used 4,825 reasoning
characters and then emitted a correct 1,127-character answer. The 512- and
1024-token runs exhausted the budget in `reasoning_content` without any final
`content`.

The arithmetic and logic prompts were deliberately soloed again after the first
concurrent comparison. The first run's ambiguous 5%/756-box case was replaced
with an exact-integer case (800 total, 40 damaged, 760 undamaged).

## Operational interpretation

LFM is the bounded/fast model. It completed arithmetic and logic in roughly
18-27 seconds and did not use its larger logic budgets. It is useful for normal
work, quick checks, and final-answer verification. It begins to hit its budget
boundary on a broad operational rollout plan at 1024 tokens, but completes the
same task at 2048 tokens in about 111 seconds.

Ling is the long-horizon specialist. It generates at approximately 8.3-8.7
tok/s on this solo envelope, but its reasoning loop consumes a large budget
before final output. A 2048-token budget was sufficient for the logic task but
not sufficient for the rollout plan, which still ended with `finish_reason=length`
after 257.845 seconds. Ling therefore needs task-specific generous budgets and
must be treated as incomplete whenever final content is absent or the finish
reason is `length`.

These are warm, sequential endpoint measurements. TTFT is affected by prompt
prefix caching in repeated cases and should not be treated as a cold-start
benchmark. The total completion and finish reason are the more useful routing
signals here.

## Proposed two-model "be super sure" experiment

The proposed ping-pong workflow is technically testable, but should be bounded:

1. Start two independent conversations with the same task and a shared opaque
   experiment ID.
2. Let LFM produce a first bounded solution and explicit uncertainty/claims.
3. Send LFM's answer to Ling as a critic, asking it to check facts, calculations,
   assumptions, and missing cases rather than blindly continue the task.
4. Send Ling's critique back to LFM for a concise revision and disagreement list.
5. Optionally give Ling one final adjudication turn with a strict output schema:
   `decision`, `corrected_answer`, `confidence`, `unresolved_questions`.
6. Stop after a maximum of four cross-model turns or when both models agree on a
   machine-checkable answer. Never allow unbounded conversation ping-pong.

Measure the pair against single-model baselines using correctness, useful final
content, time to first usable answer, total wall time, total tokens, number of
turns, disagreement resolution, and failure modes. The pair is only better if
it improves correctness or catches material errors enough to justify its added
latency. A disagreement should be visible, not silently resolved by whichever
model speaks last.

This is an experiment design, not production routing policy. The Ling provider
remains a one-slot specialist, and the LFM provider remains the normal bounded
provider.
