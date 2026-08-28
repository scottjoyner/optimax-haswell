# Dual-model adjudicator prototype

Status: experiment-only; not wired into production routing.

## Location

- `experiments/dual_model_adjudicator.py`
- `experiments/tests/test_dual_model_adjudicator.py`

## Contract

The controller accepts an injected async streaming provider with the shape:

```python
async def provider(model, messages, phase):
    yield {
        "content": "...",
        "reasoning_content": "...",
        "finish_reason": "stop",
    }
```

It then:

1. starts LFM and Ling initial streams concurrently;
2. records content and reasoning separately for each model;
3. emits per-chunk events to a relay/event sink;
4. waits for both initial streams or the configured timeouts;
5. marks Ling unavailable on timeout, provider error, empty content, or a
   non-`stop` finish reason;
6. constructs one final LFM prompt containing the original request, LFM's
   preliminary answer, Ling's complete captured response, and internal flags;
7. streams the final LFM answer;
8. returns a result with provenance, timing, model responses, and failure flags.

## Deliberate boundaries

This prototype does not mutate an active model context. Ling tokens are captured
and can be displayed or persisted as they arrive, but they are included in the
final LFM prompt only after Ling's stream completes. This matches the current
OpenAI-compatible llama.cpp request model.

It does not perform deterministic task scoring, code execution, or automatic
revision acceptance. Those are required before production use.

It is not integrated with AssistX, Redis, Neo4j, or the router. The provider
callback is injected so transport and orchestration can be tested independently.

## Productionization gates

Before integration, add:

- durable session/event persistence with sequence numbers;
- idempotent resume and cancellation;
- provider-level concurrency and wall-clock budgets;
- deterministic validators for structured responses;
- a regression gate comparing final output to the LFM baseline;
- live task-family evaluation against LFM-only and Ling-only baselines;
- a feature flag disabled by default;
- routed lifecycle proof through the real AssistX task path;
- explicit observability for Ling unavailable, empty content, truncation, and
  final synthesis failure.

The prototype's tests verify initial concurrency, complete dual-response prompt
assembly, separate reasoning/content preservation, and explicit Ling failure
handling.
