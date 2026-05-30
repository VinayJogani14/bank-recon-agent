"""Unit tests for merchant normalization and enrich step."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from agent.steps.enrich import _normalize_merchant


def test_normalize_strips_llc():
    assert _normalize_merchant("Acme Corp LLC") == "acme corp"


def test_normalize_strips_inc():
    result = _normalize_merchant("Beta Solutions Inc.")
    assert "beta solutions" in result


def test_normalize_lowercases():
    result = _normalize_merchant("GAMMA INC")
    assert result == result.lower()


def test_normalize_collapses_whitespace():
    result = _normalize_merchant("Acme  Corp  LLC")
    assert "  " not in result


def test_normalize_keeps_alphanumeric():
    result = _normalize_merchant("Vendor123")
    assert "vendor123" in result


def test_normalize_empty_falls_back():
    result = _normalize_merchant("LLC")
    assert result


def test_normalize_handles_unicode():
    result = _normalize_merchant("Müller GmbH")
    assert result


@patch("agent.steps.enrich.trace_step")
def test_enrich_output_count_matches_input(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.enrich import run_enrich
    from agent.schemas.models import IngestOutput, RawTransaction

    txns = [
        RawTransaction(row_index=i, date=date(2024, 1, 15), amount_cents=100000,
                       description=f"Vendor{i}", account="checking")
        for i in range(5)
    ]
    ingest = IngestOutput(run_id="r1", valid_rows=txns, parse_errors=[])
    output = run_enrich("r1", ingest)
    assert len(output.transactions) == 5


@patch("agent.steps.enrich.trace_step")
def test_enrich_amounts_never_change(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.enrich import run_enrich
    from agent.schemas.models import IngestOutput, RawTransaction

    txns = [
        RawTransaction(row_index=0, date=date(2024, 1, 15), amount_cents=999999,
                       description="Acme Corp", account="checking")
    ]
    ingest = IngestOutput(run_id="r1", valid_rows=txns, parse_errors=[])
    output = run_enrich("r1", ingest)
    assert output.transactions[0].amount_cents == 999999
    assert output.transactions[0].normalized_amount_cents == 999999


@patch("agent.steps.enrich.trace_step")
def test_enrich_normalizes_merchant(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.enrich import run_enrich
    from agent.schemas.models import IngestOutput, RawTransaction

    txns = [
        RawTransaction(row_index=0, date=date(2024, 1, 15), amount_cents=150000,
                       description="Acme Corp LLC", account="checking")
    ]
    ingest = IngestOutput(run_id="r1", valid_rows=txns, parse_errors=[])
    output = run_enrich("r1", ingest)
    assert "llc" not in output.transactions[0].normalized_merchant.lower()
