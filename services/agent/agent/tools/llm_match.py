from __future__ import annotations

import json
from typing import Any

import anthropic
import structlog
from pydantic import BaseModel

from agent.config import settings

log = structlog.get_logger()

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ── Tool schema (contract-tested) ─────────────────────────────────────────────

PICK_MATCH_TOOL: dict[str, Any] = {
    "name": "pick_match",
    "description": (
        "Analyze a bank transaction and invoice candidates. "
        "Return the best matching invoice_id and your confidence (0-1), "
        "or no_match if none is appropriate."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": ["string", "null"],
                "description": "UUID of the best matching invoice, or null for no_match",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score between 0 and 1",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the match decision",
            },
        },
        "required": ["invoice_id", "confidence", "reasoning"],
    },
}


class LLMMatchInput(BaseModel):
    transaction_id: str
    date: str
    amount_cents: int
    normalized_merchant: str
    description: str
    candidates: list[dict[str, Any]]


class LLMMatchOutput(BaseModel):
    invoice_id: str | None
    confidence: float
    reasoning: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    model: str


def llm_pick_match(inp: LLMMatchInput, temperature: float = 0.0) -> LLMMatchOutput:
    """Call Claude with structured tool output to pick the best invoice match."""
    prompt = (
        f"Transaction to match:\n"
        f"  date: {inp.date}\n"
        f"  amount: ${inp.amount_cents / 100:.2f}\n"
        f"  merchant: {inp.normalized_merchant}\n"
        f"  description: {inp.description}\n\n"
        f"Candidate invoices:\n"
        + json.dumps(inp.candidates, indent=2, default=str)
    )

    client = _get_client()
    response = client.messages.create(  # type: ignore[call-overload]
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        temperature=temperature,
        tools=[PICK_MATCH_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract tool use block (structured output enforced by tool_choice=any)
    tool_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_block is None or tool_block.name != "pick_match":
        raise ValueError("LLM did not return pick_match tool call")

    result = tool_block.input
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = tokens_in * settings.cost_per_input_token + tokens_out * settings.cost_per_output_token

    log.info(
        "llm_match",
        transaction_id=inp.transaction_id,
        invoice_id=result.get("invoice_id"),
        confidence=result.get("confidence"),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )

    return LLMMatchOutput(
        invoice_id=result.get("invoice_id"),
        confidence=float(result["confidence"]),
        reasoning=str(result["reasoning"]),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        model=settings.llm_model,
    )
