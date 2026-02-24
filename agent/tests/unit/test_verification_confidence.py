"""Unit tests for the confidence scoring verification module."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.verification.confidence import CONFIDENCE_THRESHOLD, compute_confidence


def _ai(content, tool_calls=None):
    msg = AIMessage(content=content)
    if tool_calls:
        msg.tool_calls = tool_calls
    return msg


def _tool(content):
    return ToolMessage(content=content, tool_call_id="tc-1", name="tool")


def test_multiple_tools_complete_data_high_score():
    """Multiple tools used, complete data, long response → high score."""
    messages = [
        HumanMessage(content="Get patient summary"),
        _ai("Calling tools.", tool_calls=[
            {"name": "get_patient_summary", "args": {}, "id": "tc-1"},
            {"name": "get_medications", "args": {}, "id": "tc-2"},
        ]),
        _tool('{"status": "success", "data": {"name": "John Doe"}}'),
        _tool('{"status": "success", "data": {"meds": ["metformin"]}}'),
        _ai("Patient John Doe is a 45-year-old male currently taking "
            "metformin 500mg for type 2 diabetes management. " * 3),
    ]
    result = compute_confidence(messages)
    assert result["score"] > CONFIDENCE_THRESHOLD
    assert result["passed"] is True


def test_no_tools_simple_greeting_lower_score():
    """No tools used, short greeting → lower score but may pass."""
    messages = [
        HumanMessage(content="Hello"),
        _ai("Hello! How can I help you today?"),
    ]
    result = compute_confidence(messages)
    # Short response, no tools, no data → low score
    assert result["score"] < 0.5
    assert result["passed"] is False


def test_tool_errors_lower_confidence():
    """Tool errors in history → lower confidence score."""
    messages = [
        HumanMessage(content="Get vitals"),
        _ai("Calling tools.", tool_calls=[
            {"name": "get_vitals", "args": {}, "id": "tc-1"},
        ]),
        _tool('{"status": "error", "error": "Connection failed"}'),
        _ai("I encountered an error retrieving your vital signs. "
            "The system could not connect to the data source. "
            "Please try again later or contact support."),
    ]
    result = compute_confidence(messages)
    # Has tool data (even errored) but error penalty applies
    assert result["score"] < 1.0


def test_score_is_deterministic():
    """Same input produces same score every time."""
    messages = [
        HumanMessage(content="Get labs"),
        _ai("Looking up labs.", tool_calls=[
            {"name": "get_lab_results", "args": {}, "id": "tc-1"},
        ]),
        _tool('{"status": "success", "data": {"labs": []}}'),
        _ai("Your lab results show no recent entries in the system."),
    ]
    score1 = compute_confidence(messages)["score"]
    score2 = compute_confidence(messages)["score"]
    assert score1 == score2


def test_threshold_enforcement():
    """Score at exactly the threshold passes."""
    # We can't easily construct a message that hits exactly 0.5,
    # but we verify the threshold logic works
    messages = [
        HumanMessage(content="What medications am I on?"),
        _ai("Checking.", tool_calls=[
            {"name": "get_medications", "args": {}, "id": "tc-1"},
        ]),
        _tool('{"status": "success", "data": {"medications": []}}'),
        _ai("You currently have no medications on file in the system."),
    ]
    result = compute_confidence(messages)
    if result["score"] >= CONFIDENCE_THRESHOLD:
        assert result["passed"] is True
    else:
        assert result["passed"] is False
