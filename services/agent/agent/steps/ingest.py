from __future__ import annotations

import io
from typing import Any

import pandas as pd
import structlog

from agent.invariants import ingest_invariants, run_invariants
from agent.schemas.models import IngestOutput, ParseError, RawTransaction
from agent.traces import trace_step

log = structlog.get_logger()

REQUIRED_COLUMNS = {"date", "amount", "description", "account"}


def _parse_amount_cents(raw: Any) -> int:
    """Convert dollar string or float to integer cents."""
    val = str(raw).strip().replace("$", "").replace(",", "")
    return round(float(val) * 100)


def run_ingest(run_id: str, csv_bytes: bytes, attempt: int = 1) -> IngestOutput:
    with trace_step(run_id, "ingest", attempt) as tracer:
        input_data: dict[str, Any] = {"run_id": run_id, "csv_size_bytes": len(csv_bytes)}

        try:
            df = pd.read_csv(io.BytesIO(csv_bytes))
        except Exception as exc:
            tracer.write(
                input_json=input_data,
                output_json=None,
                status="failure",
            )
            raise ValueError(f"CSV parse failed: {exc}") from exc

        df.columns = [c.strip().lower() for c in df.columns]
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            tracer.write(
                input_json=input_data,
                output_json=None,
                status="failure",
            )
            raise ValueError(f"CSV missing required columns: {missing}")

        valid_rows: list[RawTransaction] = []
        parse_errors: list[ParseError] = []
        total_rows = len(df)

        for idx, row in df.iterrows():
            raw: dict[str, Any] = row.to_dict()
            try:
                parsed_date = pd.to_datetime(str(row["date"])).date()
                amount_cents = _parse_amount_cents(row["amount"])
                txn = RawTransaction(
                    row_index=int(str(idx)),
                    date=parsed_date,
                    amount_cents=amount_cents,
                    description=str(row["description"]).strip(),
                    account=str(row["account"]).strip(),
                )
                valid_rows.append(txn)
            except Exception as exc:
                parse_errors.append(
                    ParseError(row_index=int(str(idx)), raw_row=raw, error=str(exc))
                )

        output = IngestOutput(run_id=run_id, valid_rows=valid_rows, parse_errors=parse_errors)
        def _ingest_inv(o: IngestOutput, t: int = total_rows) -> Any:
            return ingest_invariants(o, t)[0]

        invariant_results = run_invariants([_ingest_inv], output)

        tracer.write(
            input_json=input_data,
            output_json={
                "valid_count": len(valid_rows),
                "error_count": len(parse_errors),
                "errors": [e.model_dump() for e in parse_errors],
            },
            status="success",
            invariant_results=invariant_results,
        )

        log.info(
            "ingest_complete",
            run_id=run_id,
            valid=len(valid_rows),
            errors=len(parse_errors),
            total=total_rows,
        )
        return output
