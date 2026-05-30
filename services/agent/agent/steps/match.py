from __future__ import annotations

from datetime import timedelta
from typing import Any

import structlog
from rapidfuzz import fuzz

from agent.config import settings
from agent.db import get_client
from agent.invariants import match_invariants, run_invariants
from agent.schemas.models import (
    EnrichedTransaction,
    EnrichOutput,
    MatchCandidate,
    MatchDecision,
    MatchOutput,
)
from agent.tools import LLMMatchInput, llm_pick_match
from agent.traces import trace_step

log = structlog.get_logger()


def _fetch_invoice_candidates(
    txn: EnrichedTransaction,
) -> list[MatchCandidate]:
    """Pull invoices from Supabase within date window and rank by similarity."""
    db = get_client()
    window_start = txn.date - timedelta(days=settings.date_window_days)
    window_end = txn.date + timedelta(days=settings.date_window_days)

    resp = (
        db.table("invoices")
        .select("id, vendor, normalized_vendor, amount_cents, issued_date, due_date")
        .eq("status", "open")
        .gte("issued_date", str(window_start))
        .lte("issued_date", str(window_end))
        .execute()
    )
    rows: list[dict[str, Any]] = resp.data or []

    candidates: list[MatchCandidate] = []
    for row in rows:
        sim = fuzz.token_sort_ratio(txn.normalized_merchant, row["normalized_vendor"])
        candidates.append(
            MatchCandidate(
                invoice_id=row["id"],
                vendor=row["vendor"],
                amount_cents=row["amount_cents"],
                issued_date=row["issued_date"],
                due_date=row["due_date"],
                amount_diff_cents=abs(txn.amount_cents - row["amount_cents"]),
                date_diff_days=abs((txn.date - row["issued_date"]).days),
                vendor_similarity=sim,
            )
        )
    return sorted(candidates, key=lambda c: c.vendor_similarity, reverse=True)


def _rule_match(txn: EnrichedTransaction, candidates: list[MatchCandidate]) -> MatchDecision | None:
    """Exact amount + date window + fuzzy vendor threshold."""
    for c in candidates:
        if (
            c.amount_diff_cents == 0
            and c.date_diff_days <= settings.date_window_days
            and c.vendor_similarity >= settings.fuzzy_match_threshold
        ):
            return MatchDecision(
                transaction_id=txn.transaction_id,
                invoice_id=c.invoice_id,
                confidence=min(0.95 + c.vendor_similarity / 2000, 1.0),
                method="rule_based",
                reasoning=(
                    f"Exact amount, {c.date_diff_days}d date diff, "
                    f"{c.vendor_similarity:.1f}% vendor similarity"
                ),
                candidates=candidates,
            )
    return None


def _decide_for_transaction(
    txn: EnrichedTransaction,
    matched_invoice_ids: set[str],
    temperature: float = 0.0,
    total_tokens: list[int] | None = None,
    total_cost: list[float] | None = None,
) -> MatchDecision:
    candidates = _fetch_invoice_candidates(txn)
    # exclude already-matched invoices in this run
    candidates = [c for c in candidates if c.invoice_id not in matched_invoice_ids]

    # 1. Rule-based
    decision = _rule_match(txn, candidates)
    if decision:
        return decision

    # 2. LLM fallback
    if candidates:
        try:
            llm_input = LLMMatchInput(
                transaction_id=txn.transaction_id,
                date=str(txn.date),
                amount_cents=txn.amount_cents,
                normalized_merchant=txn.normalized_merchant,
                description=txn.description,
                candidates=[c.model_dump(mode="json") for c in candidates[:5]],
            )
            result = llm_pick_match(llm_input, temperature=temperature)
            if total_tokens is not None:
                total_tokens[0] += result.tokens_in + result.tokens_out
            if total_cost is not None:
                total_cost[0] += result.cost_usd

            escalate = (
                result.invoice_id is None or result.confidence < settings.confidence_threshold
            )
            return MatchDecision(
                transaction_id=txn.transaction_id,
                invoice_id=result.invoice_id,
                confidence=result.confidence,
                method="llm",
                reasoning=result.reasoning,
                candidates=candidates,
                escalate=escalate,
            )
        except Exception as exc:
            log.warning("llm_match_failed", transaction_id=txn.transaction_id, error=str(exc))

    # 3. No match
    return MatchDecision(
        transaction_id=txn.transaction_id,
        invoice_id=None,
        confidence=0.0,
        method="no_match",
        reasoning="No candidates found or LLM failed",
        candidates=candidates,
        escalate=True,
    )


def run_match(
    run_id: str, enrich_output: EnrichOutput, attempt: int = 1, temperature: float = 0.0
) -> MatchOutput:
    with trace_step(run_id, "match", attempt) as tracer:
        transactions = enrich_output.transactions
        input_data: dict[str, Any] = {
            "run_id": run_id,
            "transaction_count": len(transactions),
            "temperature": temperature,
        }

        matched_ids: set[str] = set()
        decisions: list[MatchDecision] = []
        total_tokens = [0]
        total_cost = [0.0]

        for txn in transactions:
            decision = _decide_for_transaction(
                txn, matched_ids, temperature, total_tokens, total_cost
            )
            if decision.invoice_id and not decision.escalate:
                matched_ids.add(decision.invoice_id)
            decisions.append(decision)

        output = MatchOutput(run_id=run_id, decisions=decisions)
        expected = len(transactions)

        def _inv0(o: MatchOutput, e: int = expected) -> Any:
            return match_invariants(o, e)[0]

        def _inv1(o: MatchOutput, e: int = expected) -> Any:
            return match_invariants(o, e)[1]

        invariant_results = run_invariants([_inv0, _inv1], output)

        tracer.write(
            input_json=input_data,
            output_json={
                "matched": sum(1 for d in decisions if d.invoice_id and not d.escalate),
                "escalated": sum(1 for d in decisions if d.escalate),
                "no_match": sum(1 for d in decisions if d.method == "no_match"),
            },
            status="success",
            invariant_results=invariant_results,
            tokens_in=total_tokens[0],
            cost_usd=total_cost[0],
            llm_provider="anthropic",
            llm_model=settings.llm_model,
        )
        return output
