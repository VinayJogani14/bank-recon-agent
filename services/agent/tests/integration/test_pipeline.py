"""
Integration test: full pipeline on a fixture CSV.
Mocks Supabase and LLM calls — runs all 5 steps and verifies invariants.
"""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

FIXTURE_CSV = b"""date,amount,description,account
2024-01-15,1500.00,Acme Corp,checking
2024-01-16,2200.00,Beta Solutions,checking
2024-01-17,999.00,Unknown Vendor XYZ,checking
bad-date,500.00,Malformed Row,checking
"""

MOCK_INVOICES = [
    {
        "id": "inv-acme-1",
        "vendor": "Acme Corp LLC",
        "normalized_vendor": "acme corp",
        "amount_cents": 150000,
        "issued_date": date(2024, 1, 15),
        "due_date": date(2024, 1, 30),
        "status": "open",
    },
    {
        "id": "inv-beta-1",
        "vendor": "Beta Solutions Inc",
        "normalized_vendor": "beta solutions",
        "amount_cents": 220000,
        "issued_date": date(2024, 1, 16),
        "due_date": date(2024, 1, 31),
        "status": "open",
    },
]


def test_pipeline_end_to_end(mock_supabase: MagicMock) -> None:
    """Full pipeline: ingest -> enrich -> match -> validate -> post."""
    run_id = str(uuid.uuid4())

    # Set up mock DB to return invoices for candidate queries
    inv_resp = MagicMock()
    inv_resp.data = MOCK_INVOICES
    mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value = inv_resp

    # bank_transactions amount lookup for post step
    def table_side_effect(table_name: str) -> MagicMock:
        tbl = MagicMock()
        if table_name == "bank_transactions":
            select_chain = MagicMock()
            select_chain.in_.return_value.execute.return_value.data = []
            select_chain.eq.return_value.execute.return_value.data = []
            tbl.select.return_value = select_chain
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock()
        elif table_name == "invoices":
            tbl.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value = inv_resp
            tbl.update.return_value.in_.return_value.execute.return_value = MagicMock()
        else:
            tbl.insert.return_value.execute.return_value = MagicMock(data=[])
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock()
            tbl.update.return_value.in_.return_value.execute.return_value = MagicMock()
        return tbl

    mock_supabase.table.side_effect = table_side_effect

    from agent.steps import run_enrich, run_ingest, run_match, run_post, run_validate

    # Step 1: Ingest
    ingest_out = run_ingest(run_id, FIXTURE_CSV)
    assert len(ingest_out.valid_rows) == 3  # 1 malformed row rejected
    assert len(ingest_out.parse_errors) == 1
    assert len(ingest_out.valid_rows) + len(ingest_out.parse_errors) == 4  # invariant

    # Step 2: Enrich
    enrich_out = run_enrich(run_id, ingest_out)
    assert len(enrich_out.transactions) == 3
    for t in enrich_out.transactions:
        assert t.amount_cents == t.normalized_amount_cents  # invariant: no amount change

    # Step 3: Match (patch LLM)
    with patch("agent.steps.match.llm_pick_match") as mock_llm:
        mock_llm.return_value = MagicMock(
            invoice_id=None, confidence=0.0, reasoning="no match",
            tokens_in=10, tokens_out=5, cost_usd=0.0, model="test"
        )
        match_out = run_match(run_id, enrich_out)

    # No duplicate invoice matches (invariant)
    matched_ids = [d.invoice_id for d in match_out.decisions if d.invoice_id and not d.escalate]
    assert len(matched_ids) == len(set(matched_ids))
    assert len(match_out.decisions) == 3  # one per valid transaction

    # Step 4: Validate
    validate_out = run_validate(run_id, match_out)
    assert validate_out.all_passed

    # Step 5: Post — patch txn amount lookup
    mock_supabase.table.side_effect = None
    txn_tbl = MagicMock()
    txn_tbl.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": t.transaction_id, "amount_cents": t.amount_cents}
        for t in enrich_out.transactions
    ]
    txn_tbl.insert.return_value.execute.return_value = MagicMock(data=[])
    txn_tbl.update.return_value.eq.return_value.execute.return_value = MagicMock()
    mock_supabase.table.return_value = txn_tbl

    post_out = run_post(run_id, validate_out)
    # Core invariant: every transaction accounted for
    assert post_out.ledger_entries_created + post_out.review_queue_created == 3
