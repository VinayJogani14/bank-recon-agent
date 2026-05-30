"""Unit tests for match and validate steps."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from agent.schemas.models import (
    EnrichedTransaction,
    MatchCandidate,
    MatchDecision,
    MatchOutput,
)
from agent.steps.enrich import _normalize_merchant
from agent.steps.match import _rule_match


def _make_txn(
    txn_id: str = "txn-1",
    amount: int = 150000,
    merchant: str = "acme corp",
    txn_date: date = date(2024, 1, 15),
) -> EnrichedTransaction:
    return EnrichedTransaction(
        transaction_id=txn_id,
        run_id="run-1",
        date=txn_date,
        amount_cents=amount,
        normalized_amount_cents=amount,
        description="Acme Corp",
        normalized_merchant=merchant,
        account="checking",
        raw_row={},
    )


def _make_candidate(
    inv_id: str = "inv-1",
    amount: int = 150000,
    vendor_sim: float = 95.0,
    days_diff: int = 0,
) -> MatchCandidate:
    return MatchCandidate(
        invoice_id=inv_id,
        vendor="Acme Corp LLC",
        amount_cents=amount,
        issued_date=date(2024, 1, 15),
        due_date=date(2024, 1, 30),
        amount_diff_cents=abs(150000 - amount),
        date_diff_days=days_diff,
        vendor_similarity=vendor_sim,
    )


# ── Rule match tests ──────────────────────────────────────────────────────────


def test_rule_match_exact_returns_decision():
    txn = _make_txn()
    candidates = [_make_candidate()]
    decision = _rule_match(txn, candidates)
    assert decision is not None
    assert decision.invoice_id == "inv-1"
    assert decision.method == "rule_based"
    assert decision.confidence >= 0.85


def test_rule_match_wrong_amount_returns_none():
    txn = _make_txn(amount=100000)
    # amount_diff_cents must reflect actual difference from txn
    candidate = MatchCandidate(
        invoice_id="inv-1",
        vendor="Acme Corp LLC",
        amount_cents=150000,
        issued_date=date(2024, 1, 15),
        due_date=date(2024, 1, 30),
        amount_diff_cents=50000,  # 150000 - 100000
        date_diff_days=0,
        vendor_similarity=95.0,
    )
    decision = _rule_match(txn, [candidate])
    assert decision is None


def test_rule_match_low_vendor_similarity_returns_none():
    txn = _make_txn(merchant="completely different vendor")
    candidates = [_make_candidate(vendor_sim=20.0)]
    decision = _rule_match(txn, candidates)
    assert decision is None


def test_rule_match_date_too_far_returns_none():
    txn = _make_txn()
    # date_diff_days > 7
    candidates = [_make_candidate(days_diff=15)]
    decision = _rule_match(txn, candidates)
    assert decision is None


def test_rule_match_date_within_window_passes():
    txn = _make_txn()
    candidates = [_make_candidate(days_diff=5)]
    decision = _rule_match(txn, candidates)
    assert decision is not None


# ── Validate step tests ───────────────────────────────────────────────────────


@patch("agent.steps.validate.trace_step")
def test_validate_marks_low_confidence_for_escalation(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.validate import run_validate

    decisions = [
        MatchDecision(
            transaction_id="t1",
            invoice_id="inv-1",
            confidence=0.5,  # below threshold
            method="llm",
            reasoning="test",
            candidates=[],
            escalate=False,
        )
    ]
    match_out = MatchOutput(run_id="r1", decisions=decisions)
    validate_out = run_validate("r1", match_out)
    # Low confidence -> should be marked for escalation
    assert validate_out.decisions[0].escalate is True
    assert validate_out.all_passed


@patch("agent.steps.validate.trace_step")
def test_validate_high_confidence_passes(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.validate import run_validate

    decisions = [
        MatchDecision(
            transaction_id="t1",
            invoice_id="inv-1",
            confidence=0.95,
            method="rule_based",
            reasoning="exact match",
            candidates=[],
            escalate=False,
        )
    ]
    match_out = MatchOutput(run_id="r1", decisions=decisions)
    validate_out = run_validate("r1", match_out)
    assert not validate_out.decisions[0].escalate
    assert validate_out.all_passed


# ── Enrich normalization edge cases ───────────────────────────────────────────


def test_normalize_multiple_suffixes():
    result = _normalize_merchant("Acme Corp LLC Ltd")
    assert "ltd" not in result.lower()
    assert "acme" in result.lower()


def test_normalize_numbers_preserved():
    result = _normalize_merchant("Vendor 123 Inc")
    assert "123" in result


def test_normalize_handles_unicode():
    result = _normalize_merchant("Müller GmbH")
    assert result  # should not crash or be empty
