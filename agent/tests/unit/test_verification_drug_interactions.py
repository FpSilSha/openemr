"""Unit tests for the drug interaction coverage verification module."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.verification.drug_interactions import check_drug_interaction_coverage


def _ai(content, tool_calls=None):
    """Create an AIMessage, optionally with tool_calls."""
    msg = AIMessage(content=content)
    if tool_calls:
        msg.tool_calls = tool_calls
    return msg


def _tool(content, name="some_tool"):
    """Create a ToolMessage."""
    return ToolMessage(content=content, tool_call_id="tc-1", name=name)


def test_meds_mentioned_with_interaction_check_passes():
    """Medications discussed + drug_interaction_check called → pass."""
    messages = [
        HumanMessage(content="Check aspirin and warfarin interactions"),
        _ai("Let me check.", tool_calls=[
            {"name": "drug_interaction_check", "args": {}, "id": "tc-1"}
        ]),
        _tool('{"status": "success"}', name="drug_interaction_check"),
        _ai("Aspirin and warfarin have a high interaction risk."),
    ]
    result = check_drug_interaction_coverage(messages)
    assert result["passed"] is True


def test_meds_mentioned_without_interaction_check_fails():
    """Medications discussed + no drug_interaction_check → fail."""
    messages = [
        HumanMessage(content="Tell me about the patient"),
        _ai("The patient takes metformin 500mg and lisinopril 10mg."),
    ]
    result = check_drug_interaction_coverage(messages)
    assert result["passed"] is False
    assert "drug_interaction_check" in result["reason"]


def test_no_meds_mentioned_passes():
    """No medication keywords → pass (not applicable)."""
    messages = [
        HumanMessage(content="What are the lab results?"),
        _ai("The patient's hemoglobin A1c is 6.5%."),
    ]
    result = check_drug_interaction_coverage(messages)
    assert result["passed"] is True


def test_drug_names_case_insensitive():
    """Drug names in various cases are detected."""
    messages = [
        HumanMessage(content="Check meds"),
        _ai("Patient is taking ASPIRIN and Warfarin daily.",
             tool_calls=[
                 {"name": "drug_interaction_check", "args": {}, "id": "tc-1"}
             ]),
        _tool('{"status":"success"}', name="drug_interaction_check"),
        _ai("ASPIRIN and Warfarin have a known interaction."),
    ]
    result = check_drug_interaction_coverage(messages)
    assert result["passed"] is True


def test_empty_messages_passes():
    """Empty message list → pass."""
    result = check_drug_interaction_coverage([])
    assert result["passed"] is True
