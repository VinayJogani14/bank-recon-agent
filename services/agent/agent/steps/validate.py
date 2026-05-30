from __future__ import annotations

from typing import Any

import structlog

from agent.invariants import run_invariants, validate_invariants
from agent.schemas.models import MatchDecision, MatchOutput, ValidateOutput
from agent.traces import trace_step

log = structlog.get_logger()


def _mark_low_confidence_for_escalation(decisions: list[MatchDecision]) -> list[MatchDecision]:
    """Ensure any low-confidence match is flagged for escalation."""
    updated: list[MatchDecision] = []
    for d in decisions:
        if d.invoice_id and d.confidence < 0.85 and not d.escalate:
            updated.append(d.model_copy(update={"escalate": True}))
        else:
            updated.append(d)
    return updated


def run_validate(
    run_id: str, match_output: MatchOutput, attempt: int = 1
) -> ValidateOutput:
    with trace_step(run_id, "validate", attempt) as tracer:
        decisions = _mark_low_confidence_for_escalation(match_output.decisions)

        input_data: dict[str, Any] = {
            "run_id": run_id,
            "decision_count": len(decisions),
        }

        output = ValidateOutput(
            run_id=run_id,
            decisions=decisions,
            invariant_results=[],
            all_passed=False,
        )

        try:
            invariant_results = run_invariants(
                [
                    lambda o: validate_invariants(o)[0],
                    lambda o: validate_invariants(o)[1],
                ],
                output,
            )
            output = output.model_copy(
                update={"invariant_results": invariant_results, "all_passed": True}
            )
            status = "success"
        except Exception as exc:
            log.warning("validate_invariant_violation", run_id=run_id, error=str(exc))
            output = output.model_copy(update={"all_passed": False})
            status = "retry"
            raise

        tracer.write(
            input_json=input_data,
            output_json={
                "all_passed": output.all_passed,
                "matched": sum(1 for d in decisions if d.invoice_id and not d.escalate),
                "escalated": sum(1 for d in decisions if d.escalate),
            },
            status=status,
            invariant_results=output.invariant_results,
        )
        return output
