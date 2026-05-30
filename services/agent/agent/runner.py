from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from agent.config import settings
from agent.db import get_client
from agent.invariants import InvariantViolation
from agent.metrics import (
    ESCALATION_RATE,
    INVARIANT_VIOLATIONS,
    RETRY_COUNT,
    STEP_LATENCY,
)
from agent.schemas.models import PostOutput, RunSummary
from agent.steps import run_enrich, run_ingest, run_match, run_post, run_validate

log = structlog.get_logger()

# Temperature schedule for LLM retries
_TEMPERATURES = [0.0, 0.3, 0.7]


def _update_run(run_id: str, fields: dict[str, Any]) -> None:
    try:
        get_client().table("runs").update(fields).eq("id", run_id).execute()
    except Exception:
        log.exception("run_update_failed", run_id=run_id)


def execute_run(run_id: str, csv_bytes: bytes, csv_filename: str) -> PostOutput:
    """
    Orchestrate the 5-step pipeline with retry, fallback, and full trace persistence.
    Each step is retried up to settings.max_retries times on InvariantViolation.
    LLM steps increment temperature on each retry.
    """
    log.info("run_start", run_id=run_id, csv_filename=csv_filename)
    _update_run(run_id, {"status": "running", "csv_filename": csv_filename})

    try:
        # ── Step 1: Ingest ────────────────────────────────────────────────────
        ingest_output = _retry_step(
            "ingest",
            lambda attempt: run_ingest(run_id, csv_bytes, attempt),
        )

        # Persist transactions
        db = get_client()
        txn_rows = [
            {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "date": str(t.date),
                "amount_cents": t.amount_cents,
                "description": t.description,
                "account": t.account,
                "raw_row": {"row_index": t.row_index},
            }
            for t in ingest_output.valid_rows
        ]
        if txn_rows:
            db.table("bank_transactions").insert(txn_rows).execute()
            # Patch transaction_ids into enrich step by aligning order
            for i, row in enumerate(txn_rows):
                ingest_output.valid_rows[i].__dict__["_db_id"] = row["id"]

        # ── Step 2: Enrich ────────────────────────────────────────────────────
        enrich_output = _retry_step(
            "enrich",
            lambda attempt: run_enrich(run_id, ingest_output, attempt),
        )

        # Sync DB transaction IDs into enriched transactions
        for i, txn in enumerate(enrich_output.transactions):
            if i < len(txn_rows):
                object.__setattr__(txn, "transaction_id", txn_rows[i]["id"])

        # Update normalized merchant in DB
        for txn in enrich_output.transactions:
            db.table("bank_transactions").update(
                {"normalized_merchant": txn.normalized_merchant}
            ).eq("id", txn.transaction_id).execute()

        # ── Step 3: Match ─────────────────────────────────────────────────────
        match_output = _retry_step(
            "match",
            lambda attempt: run_match(
                run_id,
                enrich_output,
                attempt,
                temperature=_TEMPERATURES[min(attempt - 1, len(_TEMPERATURES) - 1)],
            ),
            is_llm_step=True,
        )

        # ── Step 4: Validate ──────────────────────────────────────────────────
        validate_output = _retry_step(
            "validate",
            lambda attempt: run_validate(run_id, match_output, attempt),
        )

        # ── Step 5: Post ──────────────────────────────────────────────────────
        post_output = _retry_step(
            "post",
            lambda attempt: run_post(run_id, validate_output, attempt),
        )

        # ── Finalize run ──────────────────────────────────────────────────────
        total_rows = len(ingest_output.valid_rows) + len(ingest_output.parse_errors)
        escalated = post_output.review_queue_created

        ESCALATION_RATE.set(escalated / max(total_rows, 1))

        _update_run(
            run_id,
            {
                "status": "completed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "total_rows": total_rows,
                "matched": post_output.ledger_entries_created,
                "escalated": escalated,
            },
        )
        log.info("run_complete", run_id=run_id, matched=post_output.ledger_entries_created)
        return post_output

    except Exception as exc:
        _update_run(
            run_id,
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        log.exception("run_failed", run_id=run_id, error=str(exc))
        raise


def _retry_step(
    step_name: str,
    fn: Any,
    is_llm_step: bool = False,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(1, settings.max_retries + 1):
        t0 = time.monotonic()
        try:
            result = fn(attempt)
            STEP_LATENCY.labels(step=step_name).observe(time.monotonic() - t0)
            return result
        except InvariantViolation as exc:
            elapsed = time.monotonic() - t0
            STEP_LATENCY.labels(step=step_name).observe(elapsed)
            INVARIANT_VIOLATIONS.labels(step=step_name).inc()
            last_exc = exc
            if attempt < settings.max_retries:
                RETRY_COUNT.labels(step=step_name).inc()
                wait = 0.5 * (2 ** (attempt - 1))
                log.warning(
                    "invariant_violation_retry",
                    step=step_name,
                    attempt=attempt,
                    wait_s=wait,
                    error=str(exc),
                )
                time.sleep(wait)
            else:
                log.error(
                    "invariant_violation_max_retries",
                    step=step_name,
                    error=str(exc),
                )

    raise last_exc or RuntimeError(f"Step {step_name} failed after {settings.max_retries} retries")


def replay_step(run_id: str, step_name: str) -> Any:
    """Re-execute a step using its original trace input."""
    db = get_client()
    resp = (
        db.table("step_traces")
        .select("input_json, attempt")
        .eq("run_id", run_id)
        .eq("step_name", step_name)
        .order("attempt", desc=False)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        raise ValueError(f"No trace found for run {run_id}, step {step_name}")

    original_input = rows[0]["input_json"]
    original_attempt = rows[0]["attempt"]

    log.info("replay_step", run_id=run_id, step=step_name)

    # Dispatch to the correct step handler with original input
    # Steps that need raw bytes (ingest) must have csv stored elsewhere;
    # for replay we re-fetch from bank_transactions raw_row.
    if step_name == "ingest":
        raise NotImplementedError("Ingest replay requires re-uploading the original CSV")
    elif step_name == "enrich":
        from agent.steps.enrich import run_enrich as _run
        from agent.schemas.models import IngestOutput, RawTransaction

        raw_txns = (
            db.table("bank_transactions")
            .select("*")
            .eq("run_id", run_id)
            .execute()
            .data or []
        )
        valid_rows = [
            RawTransaction(
                row_index=r["raw_row"].get("row_index", 0),
                date=r["date"],
                amount_cents=r["amount_cents"],
                description=r["description"],
                account=r["account"],
            )
            for r in raw_txns
        ]
        ingest_output = IngestOutput(run_id=run_id, valid_rows=valid_rows, parse_errors=[])
        return _run(run_id, ingest_output, attempt=original_attempt + 1)

    raise ValueError(f"Replay not implemented for step: {step_name}")


def create_run(csv_filename: str) -> RunSummary:
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db = get_client()
    db.table("runs").insert(
        {
            "id": run_id,
            "started_at": now,
            "status": "pending",
            "csv_filename": csv_filename,
        }
    ).execute()
    return RunSummary(
        id=run_id,
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        status="pending",
        csv_filename=csv_filename,
        total_rows=None,
        matched=None,
        escalated=None,
        total_cost_usd=None,
    )
