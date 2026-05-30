from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from agent.db import get_client
from agent.runner import create_run, execute_run, replay_step
from api.models import (
    EvalResultResponse,
    ReplayResponse,
    RunDetailResponse,
    RunResponse,
    TraceResponse,
)
from evals.harness import run_evals

log = structlog.get_logger()

app = FastAPI(title="Bank Reconciliation Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Prometheus ────────────────────────────────────────────────────────────────

@app.get("/metrics")
def metrics() -> Any:
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Runs ──────────────────────────────────────────────────────────────────────

@app.get("/runs", response_model=list[RunDetailResponse])
def list_runs(limit: int = 50) -> list[RunDetailResponse]:
    db = get_client()
    resp = (
        db.table("runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [RunDetailResponse(**r) for r in (resp.data or [])]


@app.post("/runs", response_model=RunResponse, status_code=202)
async def start_run(file: UploadFile = File(...)) -> RunResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files accepted")

    csv_bytes = await file.read()
    run = create_run(file.filename)

    # Execute async in background
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, execute_run, run.id, csv_bytes, file.filename)

    return RunResponse(run_id=run.id, status="running", message="Run started")


@app.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: str) -> RunDetailResponse:
    db = get_client()
    resp = db.table("runs").select("*").eq("id", run_id).execute()
    if not resp.data:
        raise HTTPException(404, f"Run {run_id} not found")
    row = resp.data[0]
    return RunDetailResponse(**row)


@app.get("/runs/{run_id}/traces", response_model=list[TraceResponse])
def get_traces(run_id: str) -> list[TraceResponse]:
    db = get_client()
    resp = (
        db.table("step_traces")
        .select("*")
        .eq("run_id", run_id)
        .order("created_at")
        .execute()
    )
    return [TraceResponse(**r) for r in (resp.data or [])]


@app.post("/runs/{run_id}/steps/{step_name}/replay", response_model=ReplayResponse)
def replay(run_id: str, step_name: str) -> ReplayResponse:
    try:
        result = replay_step(run_id, step_name)
        return ReplayResponse(
            run_id=run_id,
            step_name=step_name,
            status="success",
            output=result.model_dump(mode="json") if hasattr(result, "model_dump") else {},
        )
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        log.exception("replay_failed", run_id=run_id, step=step_name)
        raise HTTPException(500, str(exc)) from exc


# ── Evals ─────────────────────────────────────────────────────────────────────

@app.post("/evals/run")
def trigger_evals() -> dict[str, Any]:
    report = run_evals()
    return {
        "total_cases": report.total_cases,
        "passed": report.passed,
        "failed": report.failed,
        "accuracy": report.accuracy,
        "precision": report.precision,
        "recall": report.recall,
        "f1": report.f1,
        "avg_cost_usd": report.avg_cost_usd,
        "p95_latency_ms": report.p95_latency_ms,
        "regressions": report.regressions,
        "cases": [
            {
                "name": r.name,
                "passed": r.passed,
                "expected_matches": r.expected_matches,
                "actual_matches": r.actual_matches,
                "expected_escalations": r.expected_escalations,
                "actual_escalations": r.actual_escalations,
                "latency_ms": r.latency_ms,
                "cost_usd": r.cost_usd,
                "error": r.error,
            }
            for r in report.case_results
        ],
    }


@app.get("/evals/results", response_model=list[EvalResultResponse])
def get_eval_results() -> list[EvalResultResponse]:
    db = get_client()
    resp = (
        db.table("evals_results")
        .select("*")
        .order("ran_at", desc=True)
        .limit(20)
        .execute()
    )
    return [EvalResultResponse(**r) for r in (resp.data or [])]
