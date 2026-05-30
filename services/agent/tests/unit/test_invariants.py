"""Unit tests for every invariant function."""

from __future__ import annotations

from datetime import date

import pytest

from agent.invariants.base import InvariantViolation, run_invariants
from agent.invariants.step_invariants import (
    enrich_invariants,
    ingest_invariants,
    match_invariants,
    post_invariants,
    validate_invariants,
)
from agent.schemas.models import (
    EnrichedTransaction,
    EnrichOutput,
    IngestOutput,
    InvariantResult,
    MatchDecision,
    MatchOutput,
    ParseError,
    PostOutput,
    RawTransaction,
    ValidateOutput,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_raw_txn(row_index: int = 0) -> RawTransaction:
    return RawTransaction(
        row_index=row_index,
        date=date(2024, 1, 15),
        amount_cents=150000,
        description="Acme Corp",
        account="checking",
    )


def make_enriched(txn_id: str = "txn-1", amount: int = 150000) -> EnrichedTransaction:
    return EnrichedTransaction(
        transaction_id=txn_id,
        run_id="run-1",
        date=date(2024, 1, 15),
        amount_cents=amount,
        normalized_amount_cents=amount,
        description="Acme Corp",
        normalized_merchant="acme corp",
        account="checking",
        raw_row={},
    )


def make_decision(
    txn_id: str = "txn-1",
    invoice_id: str | None = "inv-1",
    confidence: float = 0.95,
    escalate: bool = False,
) -> MatchDecision:
    return MatchDecision(
        transaction_id=txn_id,
        invoice_id=invoice_id,
        confidence=confidence,
        method="rule_based",
        reasoning="test",
        candidates=[],
        escalate=escalate,
    )


# ── Ingest invariants ─────────────────────────────────────────────────────────


def test_ingest_row_count_passes():
    output = IngestOutput(
        run_id="r1",
        valid_rows=[make_raw_txn()],
        parse_errors=[ParseError(row_index=1, raw_row={}, error="bad date")],
    )
    results = ingest_invariants(output, expected_total=2)
    assert all(r.passed for r in results)


def test_ingest_row_count_fails():
    output = IngestOutput(run_id="r1", valid_rows=[make_raw_txn()], parse_errors=[])
    results = ingest_invariants(output, expected_total=5)
    assert not results[0].passed
    assert "5" in (results[0].detail or "")


# ── Enrich invariants ─────────────────────────────────────────────────────────


def test_enrich_amounts_preserved_pass():
    e = make_enriched()
    output = EnrichOutput(run_id="r1", transactions=[e])
    results = enrich_invariants(output, expected=1)
    assert all(r.passed for r in results)


def test_enrich_amounts_preserved_model_validation():
    """EnrichedTransaction itself rejects amount mismatch."""
    with pytest.raises(ValueError, match="Normalization changed amount"):
        EnrichedTransaction(
            transaction_id="t1",
            run_id="r1",
            date=date(2024, 1, 15),
            amount_cents=150000,
            normalized_amount_cents=149999,  # different!
            description="test",
            normalized_merchant="test",
            account="checking",
            raw_row={},
        )


def test_enrich_row_count_fails():
    output = EnrichOutput(run_id="r1", transactions=[make_enriched()])
    results = enrich_invariants(output, expected=3)
    assert not results[1].passed


# ── Match invariants ──────────────────────────────────────────────────────────


def test_match_no_duplicates_pass():
    output = MatchOutput(
        run_id="r1",
        decisions=[
            make_decision("t1", "inv-1"),
            make_decision("t2", "inv-2"),
        ],
    )
    results = match_invariants(output, expected=2)
    assert results[0].passed


def test_match_duplicate_invoice_fails():
    output = MatchOutput(
        run_id="r1",
        decisions=[
            make_decision("t1", "inv-1"),
            make_decision("t2", "inv-1"),  # same invoice!
        ],
    )
    results = match_invariants(output, expected=2)
    assert not results[0].passed
    assert "inv-1" in (results[0].detail or "")


def test_match_count_mismatch_fails():
    output = MatchOutput(run_id="r1", decisions=[make_decision("t1", "inv-1")])
    results = match_invariants(output, expected=5)
    assert not results[1].passed


# ── Validate invariants ───────────────────────────────────────────────────────


def test_validate_low_confidence_not_escalated_fails():
    output = ValidateOutput(
        run_id="r1",
        decisions=[make_decision(confidence=0.5, escalate=False)],
        invariant_results=[],
        all_passed=False,
    )
    results = validate_invariants(output)
    assert not results[0].passed


def test_validate_low_confidence_escalated_passes():
    output = ValidateOutput(
        run_id="r1",
        decisions=[make_decision(confidence=0.5, escalate=True)],
        invariant_results=[],
        all_passed=False,
    )
    results = validate_invariants(output)
    assert results[0].passed


def test_validate_no_duplicate_invoices():
    output = ValidateOutput(
        run_id="r1",
        decisions=[
            make_decision("t1", "inv-1", escalate=False),
            make_decision("t2", "inv-1", escalate=False),
        ],
        invariant_results=[],
        all_passed=False,
    )
    results = validate_invariants(output)
    assert not results[1].passed


# ── Post invariants ───────────────────────────────────────────────────────────


def test_post_count_balance_passes():
    output = PostOutput(
        run_id="r1",
        ledger_entries_created=3,
        review_queue_created=2,
        total_input=5,
    )
    results = post_invariants(output)
    assert results[0].passed


def test_post_count_balance_model_validation():
    with pytest.raises(ValueError, match="Output count mismatch"):
        PostOutput(
            run_id="r1",
            ledger_entries_created=3,
            review_queue_created=2,
            total_input=6,  # 3+2 != 6
        )


# ── run_invariants raises on violation ────────────────────────────────────────


def test_run_invariants_raises_on_violation():
    def bad_fn(x: int) -> InvariantResult:
        return InvariantResult(name="test", passed=False, detail="oops")

    with pytest.raises(InvariantViolation):
        run_invariants([bad_fn], 1)


def test_run_invariants_returns_results_on_pass():
    def good_fn(x: int) -> InvariantResult:
        return InvariantResult(name="test", passed=True)

    results = run_invariants([good_fn], 1)
    assert len(results) == 1
    assert results[0].passed
