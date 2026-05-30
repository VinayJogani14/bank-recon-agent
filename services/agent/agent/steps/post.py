from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from agent.db import get_client
from agent.invariants import post_invariants, run_invariants
from agent.schemas.models import PostOutput, ValidateOutput
from agent.traces import trace_step

log = structlog.get_logger()


def run_post(run_id: str, validate_output: ValidateOutput, attempt: int = 1) -> PostOutput:
    with trace_step(run_id, "post", attempt) as tracer:
        decisions = validate_output.decisions
        input_data: dict[str, Any] = {
            "run_id": run_id,
            "decision_count": len(decisions),
        }

        db = get_client()
        ledger_count = 0
        queue_count = 0

        to_post = [d for d in decisions if d.invoice_id and not d.escalate]
        to_escalate = [d for d in decisions if d.escalate or not d.invoice_id]

        # Ledger entries (transactional: all or nothing per batch)
        if to_post:
            ledger_rows = [
                {
                    "transaction_id": d.transaction_id,
                    "invoice_id": d.invoice_id,
                    "amount_cents": 0,  # populated below
                    "posted_at": datetime.now(UTC).isoformat(),
                    "confidence": d.confidence,
                    "created_by_run_id": run_id,
                }
                for d in to_post
            ]

            # Fetch amounts from bank_transactions
            txn_ids = [d.transaction_id for d in to_post]
            txn_resp = (
                db.table("bank_transactions")
                .select("id, amount_cents")
                .in_("id", txn_ids)
                .execute()
            )
            amounts = {r["id"]: r["amount_cents"] for r in (txn_resp.data or [])}

            for _i, row in enumerate(ledger_rows):
                row["amount_cents"] = amounts.get(row["transaction_id"], 0)

            db.table("ledger_entries").insert(ledger_rows).execute()
            ledger_count = len(ledger_rows)

            # Mark invoices as matched
            invoice_ids = [d.invoice_id for d in to_post if d.invoice_id]
            db.table("invoices").update({"status": "matched"}).in_("id", invoice_ids).execute()

        # Review queue
        if to_escalate:
            queue_rows = [
                {
                    "transaction_id": d.transaction_id,
                    "reason": d.reasoning,
                    "candidates": [c.model_dump(mode="json") for c in d.candidates],
                    "resolved": False,
                }
                for d in to_escalate
            ]
            db.table("review_queue").insert(queue_rows).execute()
            queue_count = len(queue_rows)

        output = PostOutput(
            run_id=run_id,
            ledger_entries_created=ledger_count,
            review_queue_created=queue_count,
            total_input=len(decisions),
        )
        invariant_results = run_invariants([lambda o: post_invariants(o)[0]], output)

        tracer.write(
            input_json=input_data,
            output_json={
                "ledger_entries_created": ledger_count,
                "review_queue_created": queue_count,
            },
            status="success",
            invariant_results=invariant_results,
        )
        return output
