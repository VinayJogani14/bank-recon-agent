"""Unit tests for FastAPI endpoints using TestClient."""

from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _run_row() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "started_at": "2024-01-15T10:00:00Z",
        "finished_at": "2024-01-15T10:01:00Z",
        "status": "completed",
        "csv_filename": "test.csv",
        "total_rows": 10,
        "matched": 8,
        "escalated": 2,
        "total_cost_usd": 0.005,
    }


def test_health(mock_supabase: MagicMock):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_metrics(mock_supabase: MagicMock):
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_list_runs_empty(mock_supabase: MagicMock):
    mock_supabase.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_runs_returns_data(mock_supabase: MagicMock):
    row = _run_row()
    mock_supabase.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        row
    ]
    resp = client.get("/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == row["id"]


def test_get_run_not_found(mock_supabase: MagicMock):
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    resp = client.get(f"/runs/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_run_success(mock_supabase: MagicMock):
    row = _run_row()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        row
    ]
    resp = client.get(f"/runs/{row['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == row["id"]


def test_get_traces_empty(mock_supabase: MagicMock):
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    resp = client.get(f"/runs/{uuid.uuid4()}/traces")
    assert resp.status_code == 200
    assert resp.json() == []


def test_post_runs_requires_csv(mock_supabase: MagicMock):
    resp = client.post("/runs", files={"file": ("test.txt", b"not csv", "text/plain")})
    assert resp.status_code == 400


def test_post_runs_accepts_csv(mock_supabase: MagicMock):
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "run-1"}
    ]
    csv_content = b"date,amount,description,account\n2024-01-15,1500.00,Acme,checking"
    with patch("api.main.execute_run"):
        resp = client.post(
            "/runs",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
    assert resp.status_code == 202
    assert "run_id" in resp.json()


def test_eval_results_empty(mock_supabase: MagicMock):
    mock_supabase.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    resp = client.get("/evals/results")
    assert resp.status_code == 200
    assert resp.json() == []
