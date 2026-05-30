from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class RunDetailResponse(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    csv_filename: str
    total_rows: int | None = None
    matched: int | None = None
    escalated: int | None = None
    total_cost_usd: float | None = None


class TraceResponse(BaseModel):
    id: str
    run_id: str
    step_name: str
    attempt: int
    input_json: dict[str, Any]
    output_json: dict[str, Any] | None = None
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    status: str
    invariant_results: list[dict[str, Any]] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    created_at: datetime


class ReplayResponse(BaseModel):
    run_id: str
    step_name: str
    status: str
    output: dict[str, Any]


class EvalResultResponse(BaseModel):
    id: str
    ran_at: datetime
    total_cases: int
    passed: int
    accuracy: float | None = None
    precision_score: float | None = None
    recall_score: float | None = None
    f1_score: float | None = None
    avg_cost_usd: float | None = None
    p95_latency_ms: int | None = None
    regressions: list[str] | None = None
