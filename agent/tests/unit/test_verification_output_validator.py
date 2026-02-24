"""Unit tests for the output validation verification module."""

from langchain_core.messages import AIMessage, HumanMessage

from app.verification.output_validator import validate_output


def _ai(content):
    return AIMessage(content=content)


def test_clean_response_passes():
    """Normal clinical text with no issues → pass."""
    messages = [
        HumanMessage(content="Tell me about the patient"),
        _ai("The patient is a 45-year-old male with type 2 diabetes. "
            "His current medications include metformin 500mg. "
            "Please consult with the attending physician."),
    ]
    result = validate_output(messages)
    assert result["passed"] is True
    assert result["issues"] == []


def test_raw_json_in_response_fails():
    """Response containing raw JSON/API data → fail."""
    messages = [
        HumanMessage(content="Get patient data"),
        _ai('Here is the data: {"resourceType": "Patient", "id": "123"}'),
    ]
    result = validate_output(messages)
    assert result["passed"] is False
    assert any("raw JSON" in issue for issue in result["issues"])


def test_empty_response_fails():
    """Empty AI response → fail."""
    messages = [
        HumanMessage(content="Hello"),
        _ai(""),
    ]
    result = validate_output(messages)
    assert result["passed"] is False
    assert any("empty" in issue.lower() for issue in result["issues"])


def test_tool_error_in_response_fails():
    """Response containing tool error message → fail."""
    messages = [
        HumanMessage(content="Get vitals"),
        _ai("Tool 'get_vitals' failed: ConnectionError: timeout"),
    ]
    result = validate_output(messages)
    assert result["passed"] is False
    assert len(result["issues"]) > 0


def test_no_messages_fails():
    """Empty message list → fail."""
    result = validate_output([])
    assert result["passed"] is False
