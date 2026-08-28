"""Experimental LFM/Ling dual-model adjudication controller.

This module is intentionally provider-agnostic and is not wired into production
routing.  It owns the logical adjudication state machine while callers supply an
async streaming provider function.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

Chunk = dict[str, Any]
Provider = Callable[[str, list[dict[str, str]], str], AsyncIterator[Chunk]]


@dataclass
class ProviderResponse:
    model: str
    phase: str
    content: str = ""
    reasoning: str = ""
    finish_reason: str | None = None
    elapsed_s: float = 0.0
    error: str | None = None

    @property
    def usable(self) -> bool:
        return self.finish_reason == "stop" and bool(self.content.strip())

    @property
    def analysis_text(self) -> str:
        parts = []
        if self.content:
            parts.append("Final content:\n" + self.content)
        if self.reasoning:
            parts.append("Reasoning content (not independently verified):\n" + self.reasoning)
        return "\n\n".join(parts)


@dataclass
class AdjudicationResult:
    session_id: str
    status: str
    final_answer: str = ""
    lfm_draft: ProviderResponse | None = None
    ling_analysis_response: ProviderResponse | None = None
    ling_available: bool = False
    flags: list[str] = field(default_factory=list)


class DualModelAdjudicator:
    """Run parallel drafts, then one final LFM synthesis.

    ``provider`` must return an async iterator of OpenAI-compatible delta-like
    dictionaries.  Each chunk may contain ``content``, ``reasoning_content``,
    and ``finish_reason``.  A callback receives every captured chunk so a relay
    can persist or display the streams without mutating an active prompt.
    """

    def __init__(
        self,
        provider: Provider,
        *,
        ling_timeout_s: float = 300.0,
        lfm_timeout_s: float = 180.0,
        event_sink: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ) -> None:
        self.provider = provider
        self.ling_timeout_s = ling_timeout_s
        self.lfm_timeout_s = lfm_timeout_s
        self.event_sink = event_sink

    async def _emit(self, event: dict[str, Any]) -> None:
        if self.event_sink is None:
            return
        result = self.event_sink(event)
        if asyncio.iscoroutine(result):
            await result

    async def _consume(
        self,
        model: str,
        messages: list[dict[str, str]],
        phase: str,
        timeout_s: float,
        session_id: str,
    ) -> ProviderResponse:
        started = time.monotonic()
        content: list[str] = []
        reasoning: list[str] = []
        finish_reason: str | None = None
        error: str | None = None

        async def read_stream() -> None:
            nonlocal finish_reason
            async for chunk in self.provider(model, messages, phase):
                content_part = str(chunk.get("content") or "")
                reasoning_part = str(chunk.get("reasoning_content") or "")
                content.append(content_part)
                reasoning.append(reasoning_part)
                finish_reason = chunk.get("finish_reason") or finish_reason
                await self._emit(
                    {
                        "type": "token",
                        "session_id": session_id,
                        "model": model,
                        "phase": phase,
                        "content": content_part,
                        "reasoning_content": reasoning_part,
                        "finish_reason": chunk.get("finish_reason"),
                    }
                )

        try:
            await asyncio.wait_for(read_stream(), timeout=timeout_s)
        except asyncio.TimeoutError:
            error = f"timeout after {timeout_s:.3f}s"
            await self._emit(
                {
                    "type": f"{model}_unavailable",
                    "session_id": session_id,
                    "model": model,
                    "phase": phase,
                    "reason": error,
                }
            )
        except Exception as exc:  # provider boundary: preserve failure in result
            error = f"{type(exc).__name__}: {exc}"
            await self._emit(
                {
                    "type": f"{model}_unavailable",
                    "session_id": session_id,
                    "model": model,
                    "phase": phase,
                    "reason": error,
                }
            )

        response = ProviderResponse(
            model=model,
            phase=phase,
            content="".join(content),
            reasoning="".join(reasoning),
            finish_reason=finish_reason,
            elapsed_s=time.monotonic() - started,
            error=error,
        )
        if not response.usable and error is None:
            await self._emit(
                {
                    "type": f"{model}_unavailable",
                    "session_id": session_id,
                    "model": model,
                    "phase": phase,
                    "reason": response.finish_reason or "empty final content",
                }
            )
        return response

    async def run(self, user_prompt: str, *, session_id: str | None = None) -> tuple[AdjudicationResult, list[dict[str, Any]]]:
        session_id = session_id or f"adj-{int(time.time() * 1000)}"
        events: list[dict[str, Any]] = []

        original_sink = self.event_sink

        async def sink(event: dict[str, Any]) -> None:
            events.append(event)
            if original_sink is not None:
                result = original_sink(event)
                if asyncio.iscoroutine(result):
                    await result

        self.event_sink = sink
        try:
            initial_messages = [{"role": "user", "content": user_prompt}]
            lfm_task = asyncio.create_task(
                self._consume("lfm", initial_messages, "initial", self.lfm_timeout_s, session_id)
            )
            ling_task = asyncio.create_task(
                self._consume("ling", initial_messages, "initial", self.ling_timeout_s, session_id)
            )
            lfm_draft, ling = await asyncio.gather(lfm_task, ling_task)

            flags: list[str] = []
            if not ling.usable:
                flags.append("ling_unavailable")
            ling_payload = ling.analysis_text if ling.analysis_text else "[Ling unavailable or empty]"
            final_prompt = (
                "You are the final adjudicator. Answer the original user request. "
                "Compare the preliminary LFM answer with Ling's independent analysis; "
                "either may be wrong. Do not expose internal reasoning unless requested.\n\n"
                f"ORIGINAL REQUEST:\n{user_prompt}\n\n"
                f"LFM PRELIMINARY ANSWER:\n{lfm_draft.analysis_text or '[LFM unavailable or empty]'}\n\n"
                f"LING ANALYSIS:\n{ling_payload}\n\n"
                f"INTERNAL FLAGS: {', '.join(flags) or 'none'}"
            )
            final = await self._consume(
                "lfm",
                [{"role": "user", "content": final_prompt}],
                "final",
                self.lfm_timeout_s,
                session_id,
            )
            if not final.usable:
                flags.append("final_unavailable")
            result = AdjudicationResult(
                session_id=session_id,
                status="complete" if final.usable else "failed",
                final_answer=final.content,
                lfm_draft=lfm_draft,
                ling_analysis_response=ling,
                ling_available=ling.usable,
                flags=flags,
            )
            return result, events
        finally:
            self.event_sink = original_sink
