from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent.schemas.models import InvariantResult


class InvariantViolation(Exception):
    def __init__(self, name: str, detail: str) -> None:
        super().__init__(f"Invariant '{name}' violated: {detail}")
        self.name = name
        self.detail = detail


InvariantFn = Callable[..., InvariantResult]


def check_invariant(name: str, condition: bool, detail: str = "") -> InvariantResult:
    return InvariantResult(name=name, passed=condition, detail=detail if not condition else None)


def run_invariants(fns: list[InvariantFn], *args: Any, **kwargs: Any) -> list[InvariantResult]:
    results: list[InvariantResult] = []
    violations: list[InvariantResult] = []

    for fn in fns:
        result = fn(*args, **kwargs)
        results.append(result)
        if not result.passed:
            violations.append(result)

    if violations:
        details = "; ".join(f"{v.name}: {v.detail}" for v in violations)
        raise InvariantViolation("multiple", details)

    return results
