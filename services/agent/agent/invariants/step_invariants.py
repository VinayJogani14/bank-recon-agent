from __future__ import annotations

from agent.schemas.models import (
    EnrichOutput,
    IngestOutput,
    InvariantResult,
    MatchOutput,
    PostOutput,
    ValidateOutput,
)

from .base import check_invariant

CONFIDENCE_THRESHOLD = 0.85


# ── Ingest ────────────────────────────────────────────────────────────────────

def _ingest_row_count(output: IngestOutput, expected_total: int) -> InvariantResult:
    actual = len(output.valid_rows) + len(output.parse_errors)
    return check_invariant(
        "ingest.row_count",
        actual == expected_total,
        f"expected {expected_total} rows, got {actual}",
    )


def ingest_invariants(output: IngestOutput, expected_total: int) -> list[InvariantResult]:
    return [_ingest_row_count(output, expected_total)]


# ── Enrich ────────────────────────────────────────────────────────────────────

def _enrich_amounts_preserved(output: EnrichOutput) -> InvariantResult:
    mismatches = [
        t.transaction_id
        for t in output.transactions
        if t.amount_cents != t.normalized_amount_cents
    ]
    return check_invariant(
        "enrich.amounts_preserved",
        len(mismatches) == 0,
        f"amount changed for transactions: {mismatches}",
    )


def _enrich_row_count(output: EnrichOutput, expected: int) -> InvariantResult:
    return check_invariant(
        "enrich.row_count",
        len(output.transactions) == expected,
        f"expected {expected}, got {len(output.transactions)}",
    )


def enrich_invariants(output: EnrichOutput, expected: int) -> list[InvariantResult]:
    return [
        _enrich_amounts_preserved(output),
        _enrich_row_count(output, expected),
    ]


# ── Match ─────────────────────────────────────────────────────────────────────

def _match_no_duplicate_invoices(output: MatchOutput) -> InvariantResult:
    matched_ids = [d.invoice_id for d in output.decisions if d.invoice_id]
    has_dupes = len(matched_ids) != len(set(matched_ids))
    dupes = [iid for iid in set(matched_ids) if matched_ids.count(iid) > 1]
    return check_invariant(
        "match.no_duplicate_invoices",
        not has_dupes,
        f"duplicate invoice matches: {dupes}",
    )


def _match_all_have_decisions(output: MatchOutput, expected: int) -> InvariantResult:
    return check_invariant(
        "match.all_transactions_decided",
        len(output.decisions) == expected,
        f"expected {expected} decisions, got {len(output.decisions)}",
    )


def match_invariants(output: MatchOutput, expected: int) -> list[InvariantResult]:
    return [
        _match_no_duplicate_invoices(output),
        _match_all_have_decisions(output, expected),
    ]


# ── Validate ──────────────────────────────────────────────────────────────────

def _validate_confidence_or_escalated(output: ValidateOutput) -> InvariantResult:
    violators = [
        d.transaction_id
        for d in output.decisions
        if d.invoice_id and d.confidence < CONFIDENCE_THRESHOLD and not d.escalate
    ]
    return check_invariant(
        "validate.confidence_threshold",
        len(violators) == 0,
        f"low-confidence matches not escalated: {violators}",
    )


def _validate_no_duplicate_invoices(output: ValidateOutput) -> InvariantResult:
    matched_ids = [d.invoice_id for d in output.decisions if d.invoice_id and not d.escalate]
    dupes = [iid for iid in set(matched_ids) if matched_ids.count(iid) > 1]
    return check_invariant(
        "validate.no_duplicate_invoices",
        len(dupes) == 0,
        f"duplicate invoice ids: {dupes}",
    )


def validate_invariants(output: ValidateOutput) -> list[InvariantResult]:
    return [
        _validate_confidence_or_escalated(output),
        _validate_no_duplicate_invoices(output),
    ]


# ── Post ──────────────────────────────────────────────────────────────────────

def _post_count_balance(output: PostOutput) -> InvariantResult:
    total = output.ledger_entries_created + output.review_queue_created
    return check_invariant(
        "post.count_balance",
        total == output.total_input,
        f"ledger({output.ledger_entries_created}) + queue({output.review_queue_created}) "
        f"!= input({output.total_input})",
    )


def post_invariants(output: PostOutput) -> list[InvariantResult]:
    return [_post_count_balance(output)]
