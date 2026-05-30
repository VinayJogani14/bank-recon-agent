"""Unit tests for the ingest step."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_csv(rows: list[str]) -> bytes:
    header = "date,amount,description,account"
    return "\n".join([header] + rows).encode()


@patch("agent.steps.ingest.trace_step")
def test_ingest_valid_rows(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.ingest import run_ingest

    csv = _make_csv([
        "2024-01-15,1500.00,Acme Corp,checking",
        "2024-01-16,2200.00,Beta Solutions,checking",
    ])
    output = run_ingest("run-1", csv)

    assert len(output.valid_rows) == 2
    assert len(output.parse_errors) == 0
    assert output.valid_rows[0].amount_cents == 150000
    assert output.valid_rows[1].amount_cents == 220000


@patch("agent.steps.ingest.trace_step")
def test_ingest_malformed_date_creates_parse_error(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.ingest import run_ingest

    csv = _make_csv([
        "not-a-date,1500.00,Acme Corp,checking",
        "2024-01-16,2200.00,Beta Solutions,checking",
    ])
    output = run_ingest("run-1", csv)
    assert len(output.valid_rows) == 1
    assert len(output.parse_errors) == 1


@patch("agent.steps.ingest.trace_step")
def test_ingest_missing_column_raises(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.ingest import run_ingest

    csv = b"date,amount,description\n2024-01-15,1500.00,Acme Corp"
    with pytest.raises(ValueError, match="missing required columns"):
        run_ingest("run-1", csv)


@patch("agent.steps.ingest.trace_step")
def test_ingest_dollar_sign_in_amount(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.ingest import run_ingest

    csv = _make_csv(["2024-01-15,$1500.00,Acme Corp,checking"])
    output = run_ingest("run-1", csv)
    assert output.valid_rows[0].amount_cents == 150000


@patch("agent.steps.ingest.trace_step")
def test_ingest_row_count_invariant(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.ingest import run_ingest

    csv = _make_csv([
        "2024-01-15,1500.00,Acme Corp,checking",
        "bad-date,500.00,Beta,checking",
        "2024-01-17,800.00,Gamma,checking",
    ])
    output = run_ingest("run-1", csv)
    total = len(output.valid_rows) + len(output.parse_errors)
    assert total == 3


@patch("agent.steps.ingest.trace_step")
def test_ingest_comma_formatted_amount(mock_ctx: MagicMock) -> None:
    writer = MagicMock()
    mock_ctx.return_value.__enter__ = MagicMock(return_value=writer)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    from agent.steps.ingest import run_ingest

    csv = b"date,amount,description,account\n2024-01-15,\"1,500.00\",Acme Corp,checking\n"
    output = run_ingest("run-1", csv)
    assert output.valid_rows[0].amount_cents == 150000
