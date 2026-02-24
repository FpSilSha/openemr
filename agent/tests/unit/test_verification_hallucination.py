"""Unit tests for the hallucination detection verification module."""

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.verification.hallucination import check_hallucination


def _ai(content):
    return AIMessage(content=content)


def _tool(content):
    return ToolMessage(content=content, tool_call_id="tc-1", name="tool")


@pytest.mark.asyncio
async def test_all_claims_backed_by_tool_data_passes():
    """All numeric claims found in tool data → pass."""
    messages = [
        HumanMessage(content="Get vitals"),
        _tool('{"value": 120, "unit": "mmHg", "type": "Blood Pressure"}'),
        _ai("Blood pressure is 120 mmHg."),
    ]
    result = await check_hallucination(messages)
    assert result["passed"] is True
    assert result["flagged_claims"] == []


@pytest.mark.asyncio
async def test_claim_not_in_tool_output_fails():
    """Numeric claim not found in tool data → fail."""
    messages = [
        HumanMessage(content="Get vitals"),
        _tool('{"value": 120, "unit": "mmHg"}'),
        _ai("Blood pressure is 140 mmHg, which is elevated."),
    ]
    result = await check_hallucination(messages)
    assert result["passed"] is False
    assert len(result["flagged_claims"]) > 0


@pytest.mark.asyncio
async def test_no_tool_data_no_claims_passes():
    """No tool outputs and no concrete claims → pass."""
    messages = [
        HumanMessage(content="Hello"),
        _ai("Hello! How can I help you today?"),
    ]
    result = await check_hallucination(messages)
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_no_tool_data_with_claims_fails():
    """No tool data but concrete clinical values in response → fail."""
    messages = [
        HumanMessage(content="What are my vitals?"),
        _ai("Your blood pressure is 120 mmHg."),
    ]
    result = await check_hallucination(messages)
    assert result["passed"] is False
    assert len(result["flagged_claims"]) > 0


@pytest.mark.asyncio
async def test_verification_model_clears_false_positive():
    """When verification model says ALL_SUPPORTED, flagged claims are cleared."""
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = _ai("ALL_SUPPORTED")

    messages = [
        HumanMessage(content="Get labs"),
        _tool('{"value": 6.5, "unit": "%"}'),
        # 999 is not in tool data but model overrides
        _ai("The A1c result is 999 mg/dL which is very high."),
    ]
    result = await check_hallucination(
        messages, verification_model=mock_model
    )
    assert result["passed"] is True
    assert result["flagged_claims"] == []


@pytest.mark.asyncio
async def test_empty_messages_passes():
    """Empty message list → pass."""
    result = await check_hallucination([])
    assert result["passed"] is True
