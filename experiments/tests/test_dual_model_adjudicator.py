import asyncio

import pytest

from experiments.dual_model_adjudicator import DualModelAdjudicator


@pytest.mark.asyncio
async def test_runs_initial_models_concurrently_and_final_lfm_sees_both_responses():
    calls = []
    started = asyncio.Event()
    release = asyncio.Event()

    async def provider(model, messages, phase):
        calls.append((model, phase, messages))
        if phase == "initial":
            if len([c for c in calls if c[1] == "initial"]) == 2:
                started.set()
            await release.wait()
            yield {"content": f"{model}-answer", "finish_reason": "stop"}
        else:
            yield {"content": "final-answer", "finish_reason": "stop"}

    async def release_after_both_started():
        await asyncio.wait_for(started.wait(), timeout=1)
        # The implementation must start both initial calls before either is released.
        assert {model for model, phase, _ in calls if phase == "initial"} == {"lfm", "ling"}
        release.set()

    (result, _), _ = await asyncio.gather(
        DualModelAdjudicator(provider, ling_timeout_s=1).run("solve this"),
        release_after_both_started(),
    )

    assert result.status == "complete"
    assert result.final_answer == "final-answer"
    assert result.ling_available is True
    final_call = next(c for c in calls if c[1] == "final")
    final_messages = final_call[2]
    joined = "\n".join(m["content"] for m in final_messages)
    assert "lfm-answer" in joined
    assert "ling-answer" in joined


@pytest.mark.asyncio
async def test_ling_timeout_is_explicit_and_lfm_can_finish_without_claiming_review():
    async def provider(model, messages, phase):
        if model == "ling":
            await asyncio.sleep(0.05)
            if False:
                yield {}
            return
        if phase == "initial":
            yield {"content": "draft", "finish_reason": "stop"}
        else:
            yield {"content": "fallback-final", "finish_reason": "stop"}

    result, events = await DualModelAdjudicator(provider, ling_timeout_s=0.01).run("task")

    assert result.status == "complete"
    assert result.final_answer == "fallback-final"
    assert result.ling_available is False
    assert "ling_unavailable" in result.flags
    unavailable = next(event for event in events if event["type"] == "ling_unavailable")
    assert unavailable["model"] == "ling"
    assert unavailable["phase"] == "initial"


@pytest.mark.asyncio
async def test_reasoning_and_content_are_preserved_separately_for_ling():
    async def provider(model, messages, phase):
        if phase == "initial" and model == "ling":
            yield {"reasoning_content": "deep thought", "content": "answer", "finish_reason": "stop"}
        elif phase == "initial":
            yield {"content": "draft", "finish_reason": "stop"}
        else:
            yield {"content": "final", "finish_reason": "stop"}

    result, _ = await DualModelAdjudicator(provider).run("task")

    assert result.ling_available is True
    ling_response = result.ling_analysis_response
    assert ling_response is not None
    assert ling_response.content == "answer"
    assert ling_response.reasoning == "deep thought"
