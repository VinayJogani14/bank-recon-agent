"""Unit tests for Pydantic schema validation."""

from __future__ import annotations

from datetime import date

import pytest

from agent.schemas.models import (
    MatchDecision,
    PostOutput,
    RawTransaction,
    StepTrace,
)


def test_raw_transaction_rejects_zero_amount():
    with pytest.raises(ValueError):
        RawTransaction(
            row_index=0,
            date=date(2024, 1, 1),
            amount_cents=0,
            description="test",
            account="checking",
        )


def test_raw_transaction_allows_negative():
    txn = RawTransaction(
        row_index=0,
        date=date(2024, 1, 1),
        amount_cents=-50000,
        description="refund",
        account="checking",
    )
    assert txn.amount_cents == -50000


def test_match_decision_confidence_bounds():
    with pytest.raises(ValueError):
        MatchDecision(
            transaction_id="t1",
            invoice_id=None,
            confidence=1.5,  # > 1
            method="rule_based",
            reasoning="test",
            candidates=[],
        )
    with pytest.raises(ValueError):
        MatchDecision(
            transaction_id="t1",
            invoice_id=None,
            confidence=-0.1,  # < 0
            method="rule_based",
            reasoning="test",
            candidates=[],
        )


def test_step_trace_valid_status():
    trace = StepTrace(
        run_id="r1",
        step_name="ingest",
        attempt=1,
        input_json={},
        status="success",
    )
    assert trace.status == "success"


def test_step_trace_invalid_status():
    with pytest.raises(ValueError):
        StepTrace(
            run_id="r1",
            step_name="ingest",
            attempt=1,
            input_json={},
            status="unknown_status",
        )


def test_post_output_model_validates_balance():
    with pytest.raises(ValueError):
        PostOutput(
            run_id="r1",
            ledger_entries_created=5,
            review_queue_created=5,
            total_input=9,
        )
