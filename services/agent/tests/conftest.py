"""Shared pytest fixtures."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _build_db() -> MagicMock:
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value.data = []
    db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    db.table.return_value.update.return_value.in_.return_value.execute.return_value = MagicMock()
    return db


# All locations that import get_client directly (from agent.db import get_client)
_DB_PATCH_TARGETS = [
    "agent.db.get_client",
    "agent.traces.get_client",
    "agent.steps.match.get_client",
    "agent.steps.post.get_client",
    "agent.runner.get_client",
    "api.main.get_client",
]


@pytest.fixture()
def mock_supabase() -> MagicMock:
    """Mock Supabase client across all import sites."""
    db = _build_db()
    patches = [patch(t, return_value=db) for t in _DB_PATCH_TARGETS]
    for p in patches:
        p.start()
    yield db
    for p in patches:
        p.stop()
