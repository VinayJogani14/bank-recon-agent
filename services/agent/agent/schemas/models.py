from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class RawTransaction(BaseModel):
    row_index: int
    date: date
    amount_cents: int = Field(..., description="Amount in cents, never float")
    description: str = Field(..., min_length=1)
    account: str = Field(..., min_length=1)

    @field_validator("amount_cents")
    @classmethod
    def nonzero_amount(cls, v: int) -> int:
        if v == 0:
            raise ValueError("amount_cents must be non-zero")
        return v


class ParseError(BaseModel):
    row_index: int
    raw_row: dict[str, Any]
    error: str


class IngestOutput(BaseModel):
    run_id: str
    valid_rows: list[RawTransaction]
    parse_errors: list[ParseError]

    @model_validator(mode="after")
    def check_row_count(self) -> IngestOutput:
        # invariant enforced externally; model just carries the data
        return self


class EnrichedTransaction(BaseModel):
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    date: date
    amount_cents: int
    normalized_amount_cents: int
    description: str
    normalized_merchant: str
    account: str
    raw_row: dict[str, Any]

    @model_validator(mode="after")
    def amounts_must_match(self) -> EnrichedTransaction:
        if self.amount_cents != self.normalized_amount_cents:
            raise ValueError(
                f"Normalization changed amount: {self.amount_cents} -> {self.normalized_amount_cents}"
            )
        return self


class EnrichOutput(BaseModel):
    run_id: str
    transactions: list[EnrichedTransaction]


class MatchCandidate(BaseModel):
    invoice_id: str
    vendor: str
    amount_cents: int
    issued_date: date
    due_date: date
    amount_diff_cents: int
    date_diff_days: int
    vendor_similarity: float


class MatchDecision(BaseModel):
    transaction_id: str
    invoice_id: str | None
    confidence: float = Field(..., ge=0.0, le=1.0)
    method: str = Field(..., description="rule_based | llm | no_match")
    reasoning: str
    candidates: list[MatchCandidate]
    escalate: bool = False


class MatchOutput(BaseModel):
    run_id: str
    decisions: list[MatchDecision]


class InvariantResult(BaseModel):
    name: str
    passed: bool
    detail: str | None = None


class ValidateOutput(BaseModel):
    run_id: str
    decisions: list[MatchDecision]
    invariant_results: list[InvariantResult]
    all_passed: bool


class PostOutput(BaseModel):
    run_id: str
    ledger_entries_created: int
    review_queue_created: int
    total_input: int

    @model_validator(mode="after")
    def count_must_balance(self) -> PostOutput:
        if self.ledger_entries_created + self.review_queue_created != self.total_input:
            raise ValueError(
                f"Output count mismatch: {self.ledger_entries_created} + "
                f"{self.review_queue_created} != {self.total_input}"
            )
        return self


class StepTrace(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    step_name: str
    attempt: int = 1
    input_json: dict[str, Any]
    output_json: dict[str, Any] | None = None
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    status: str = Field(..., pattern="^(success|retry|failure|escalated)$")
    invariant_results: list[InvariantResult] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RunSummary(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    csv_filename: str
    total_rows: int | None
    matched: int | None
    escalated: int | None
    total_cost_usd: float | None
