from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import structlog

from agent.db import get_client
from agent.schemas.models import InvariantResult, StepTrace

log = structlog.get_logger()


class TraceWriter:
    def __init__(self, run_id: str, step_name: str, attempt: int = 1) -> None:
        self.run_id = run_id
        self.step_name = step_name
        self.attempt = attempt
        self._start: float = 0.0

    def start(self) -> None:
        self._start = time.monotonic()

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)

    def write(
        self,
        *,
        input_json: dict[str, Any],
        output_json: dict[str, Any] | None,
        status: str,
        invariant_results: list[InvariantResult] | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cost_usd: float | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> StepTrace:
        trace = StepTrace(
            run_id=self.run_id,
            step_name=self.step_name,
            attempt=self.attempt,
            input_json=input_json,
            output_json=output_json,
            latency_ms=self.elapsed_ms(),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            status=status,
            invariant_results=invariant_results,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

        try:
            db = get_client()
            db.table("step_traces").insert(trace.model_dump(mode="json")).execute()
        except Exception:
            log.exception("trace_write_failed", run_id=self.run_id, step=self.step_name)

        log.info(
            "step_trace",
            run_id=self.run_id,
            step=self.step_name,
            attempt=self.attempt,
            status=status,
            latency_ms=trace.latency_ms,
        )
        return trace


@contextmanager
def trace_step(run_id: str, step_name: str, attempt: int = 1) -> Generator[TraceWriter, None, None]:
    writer = TraceWriter(run_id, step_name, attempt)
    writer.start()
    yield writer
