from __future__ import annotations

import re
import uuid
from typing import Any

import structlog

from agent.invariants import enrich_invariants, run_invariants
from agent.schemas.models import EnrichOutput, EnrichedTransaction, IngestOutput
from agent.traces import trace_step

log = structlog.get_logger()

_STRIP_SUFFIXES = re.compile(
    r"\b(llc|inc|corp|co|ltd|company|group|holdings|enterprises|services)\b\.?$",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")


def _normalize_merchant(raw: str) -> str:
    """Deterministic normalization. LLM used only if result is empty."""
    s = raw.lower().strip()
    # strip trailing punctuation and legal suffixes
    s = _STRIP_SUFFIXES.sub("", s).strip().rstrip(",.-")
    # remove special chars
    s = _NON_ALNUM.sub(" ", s)
    s = _WHITESPACE.sub(" ", s).strip()
    return s or raw.lower().strip()


def run_enrich(run_id: str, ingest_output: IngestOutput, attempt: int = 1) -> EnrichOutput:
    with trace_step(run_id, "enrich", attempt) as tracer:
        input_data: dict[str, Any] = {
            "run_id": run_id,
            "transaction_count": len(ingest_output.valid_rows),
        }

        enriched: list[EnrichedTransaction] = []
        for txn in ingest_output.valid_rows:
            normalized_merchant = _normalize_merchant(txn.description)
            enriched.append(
                EnrichedTransaction(
                    transaction_id=str(uuid.uuid4()),
                    run_id=run_id,
                    date=txn.date,
                    amount_cents=txn.amount_cents,
                    normalized_amount_cents=txn.amount_cents,  # amounts never change
                    description=txn.description,
                    normalized_merchant=normalized_merchant,
                    account=txn.account,
                    raw_row={"row_index": txn.row_index, "description": txn.description},
                )
            )

        output = EnrichOutput(run_id=run_id, transactions=enriched)
        invariant_results = run_invariants(
            [
                lambda o, e=len(ingest_output.valid_rows): enrich_invariants(o, e)[0],
                lambda o, e=len(ingest_output.valid_rows): enrich_invariants(o, e)[1],
            ],
            output,
        )

        tracer.write(
            input_json=input_data,
            output_json={"enriched_count": len(enriched)},
            status="success",
            invariant_results=invariant_results,
        )
        return output
