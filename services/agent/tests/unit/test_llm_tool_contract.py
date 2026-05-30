"""Contract tests: LLM tool schemas must match expected structure."""

from __future__ import annotations

from agent.tools.llm_match import PICK_MATCH_TOOL


def test_pick_match_tool_has_required_name():
    assert PICK_MATCH_TOOL["name"] == "pick_match"


def test_pick_match_tool_has_input_schema():
    schema = PICK_MATCH_TOOL["input_schema"]
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "required" in schema


def test_pick_match_tool_required_fields():
    required = set(PICK_MATCH_TOOL["input_schema"]["required"])
    assert required == {"invoice_id", "confidence", "reasoning"}


def test_pick_match_tool_invoice_id_nullable():
    props = PICK_MATCH_TOOL["input_schema"]["properties"]
    invoice_id_type = props["invoice_id"]["type"]
    assert isinstance(invoice_id_type, list)
    assert "null" in invoice_id_type


def test_pick_match_tool_confidence_bounded():
    props = PICK_MATCH_TOOL["input_schema"]["properties"]
    conf = props["confidence"]
    assert conf["minimum"] == 0
    assert conf["maximum"] == 1
    assert conf["type"] == "number"


def test_pick_match_tool_has_description():
    assert len(PICK_MATCH_TOOL["description"]) > 10
