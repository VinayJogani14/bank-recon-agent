from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from agent.db import get_client
from agent.metrics import EVAL_ACCURACY
from agent.runner import create_run, execute_run

log = structlog.get_logger()

GOLDEN_DIR = Path(__file__).parent / "golden_dataset"


@dataclass
class CaseResult:
    name: str
    passed: bool
    expected_matches: int
    actual_matches: int
    expected_escalations: int
    actual_escalations: int
    latency_ms: int
    cost_usd: float
    error: str | None = None


@dataclass
class EvalReport:
    total_cases: int
    passed: int
    failed: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    avg_cost_usd: float
    p95_latency_ms: int
    case_results: list[CaseResult] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)


def _load_golden_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        with open(path) as f:
            cases.append(json.load(f))
    return cases


def _run_case(case: dict[str, Any]) -> CaseResult:
    name: str = case["name"]
    csv_text: str = case["input_csv"]
    expected_matches: list[str] = case["expected_matches"]
    expected_escalations: list[str] = case["expected_escalations"]

    t0 = time.monotonic()
    cost = 0.0
    error: str | None = None
    actual_matches = 0
    actual_escalations = 0

    try:
        run = create_run(f"eval_{name}.csv")
        post_output = execute_run(run.id, csv_text.encode(), f"eval_{name}.csv")
        actual_matches = post_output.ledger_entries_created
        actual_escalations = post_output.review_queue_created

        # Fetch cost from run record
        resp = get_client().table("runs").select("total_cost_usd").eq("id", run.id).execute()
        if resp.data:
            cost = float(resp.data[0].get("total_cost_usd") or 0)
    except Exception as exc:
        error = str(exc)
        log.warning("eval_case_failed", case=name, error=error)

    latency_ms = int((time.monotonic() - t0) * 1000)

    passed = (
        error is None
        and actual_matches == len(expected_matches)
        and actual_escalations == len(expected_escalations)
    )

    return CaseResult(
        name=name,
        passed=passed,
        expected_matches=len(expected_matches),
        actual_matches=actual_matches,
        expected_escalations=len(expected_escalations),
        actual_escalations=actual_escalations,
        latency_ms=latency_ms,
        cost_usd=cost,
        error=error,
    )


def run_evals() -> EvalReport:
    cases = _load_golden_cases()
    if not cases:
        raise RuntimeError(f"No golden cases found in {GOLDEN_DIR}")

    results: list[CaseResult] = []
    for case in cases:
        log.info("eval_case_start", name=case["name"])
        result = _run_case(case)
        results.append(result)
        log.info(
            "eval_case_done",
            name=result.name,
            passed=result.passed,
            latency_ms=result.latency_ms,
        )

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    accuracy = passed / total if total else 0.0

    # Precision / recall over match decisions
    tp = sum(min(r.actual_matches, r.expected_matches) for r in results)
    fp = sum(max(0, r.actual_matches - r.expected_matches) for r in results)
    fn = sum(max(0, r.expected_matches - r.actual_matches) for r in results)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    avg_cost = sum(r.cost_usd for r in results) / total if total else 0.0
    sorted_latencies = sorted(r.latency_ms for r in results)
    p95_idx = int(0.95 * len(sorted_latencies))
    p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]

    # Detect regressions against last run
    regressions: list[str] = []
    last_run = _fetch_last_eval_result()
    if last_run and last_run.get("accuracy") and accuracy < float(last_run["accuracy"]) - 0.02:
        regressions.append(f"accuracy dropped from {last_run['accuracy']:.4f} to {accuracy:.4f}")

    report = EvalReport(
        total_cases=total,
        passed=passed,
        failed=total - passed,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        avg_cost_usd=avg_cost,
        p95_latency_ms=p95_latency,
        case_results=results,
        regressions=regressions,
    )

    _persist_eval_result(report)
    EVAL_ACCURACY.set(accuracy)
    return report


def _fetch_last_eval_result() -> dict[str, Any] | None:
    try:
        resp = (
            get_client()
            .table("evals_results")
            .select("accuracy, f1_score")
            .order("ran_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def _persist_eval_result(report: EvalReport) -> None:
    try:
        db = get_client()
        db.table("evals_results").insert(
            {
                "ran_at": datetime.now(UTC).isoformat(),
                "total_cases": report.total_cases,
                "passed": report.passed,
                "accuracy": report.accuracy,
                "precision_score": report.precision,
                "recall_score": report.recall,
                "f1_score": report.f1,
                "avg_cost_usd": report.avg_cost_usd,
                "p95_latency_ms": report.p95_latency_ms,
                "regressions": report.regressions,
            }
        ).execute()
    except Exception:
        log.exception("eval_persist_failed")
