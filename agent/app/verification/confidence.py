"""Compute a confidence score for the agent's response based on heuristic signals."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

# Default threshold — responses below this get a low-confidence caveat
CONFIDENCE_THRESHOLD = 0.5

# Scoring weights
_TOOL_USE_WEIGHT = 0.3
_DATA_COMPLETENESS_WEIGHT = 0.3
_RESPONSE_QUALITY_WEIGHT = 0.2
_NO_ERRORS_WEIGHT = 0.2


def _count_tool_uses(messages: list[BaseMessage]) -> int:
    """Count distinct tool calls in the conversation."""
    count = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            count += len(msg.tool_calls or [])
    return count


def _has_tool_errors(messages: list[BaseMessage]) -> bool:
    """Return True if any tool message indicates an error."""
    for msg in messages:
        if isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if '"status": "error"' in content or '"status":"error"' in content:
                return True
    return False


def _response_length(messages: list[BaseMessage]) -> int:
    """Return character count of the final AI response."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str):
            return len(msg.content)
    return 0


def compute_confidence(messages: list[BaseMessage]) -> dict[str, Any]:
    """Compute a confidence score for the agent's response.

    Scoring signals:
    - Tool usage (0-1): more tools used → higher confidence
    - Data completeness (0-1): tool data present → higher
    - Response quality (0-1): non-trivial response → higher
    - No errors (0-1): no tool errors → higher

    Returns:
        Dict with ``score`` (0-1 float), ``passed`` bool, and ``reason``.
    """
    if not messages:
        return {
            "score": 0.0,
            "passed": False,
            "reason": "No messages to evaluate.",
        }

    tool_count = _count_tool_uses(messages)
    has_errors = _has_tool_errors(messages)
    resp_len = _response_length(messages)
    has_tool_data = any(isinstance(m, ToolMessage) for m in messages)

    # Tool use score: 0 tools=0.2, 1 tool=0.6, 2+=1.0
    if tool_count >= 2:
        tool_score = 1.0
    elif tool_count == 1:
        tool_score = 0.6
    else:
        tool_score = 0.2

    # Data completeness: tool data present and no errors
    if has_tool_data and not has_errors:
        data_score = 1.0
    elif has_tool_data:
        data_score = 0.5
    else:
        data_score = 0.3

    # Response quality: based on length (short greetings vs detailed responses)
    if resp_len > 200:
        quality_score = 1.0
    elif resp_len > 50:
        quality_score = 0.6
    else:
        quality_score = 0.3

    # Error penalty
    error_score = 0.3 if has_errors else 1.0

    score = round(
        tool_score * _TOOL_USE_WEIGHT
        + data_score * _DATA_COMPLETENESS_WEIGHT
        + quality_score * _RESPONSE_QUALITY_WEIGHT
        + error_score * _NO_ERRORS_WEIGHT,
        3,
    )

    passed = score >= CONFIDENCE_THRESHOLD

    if passed:
        reason = f"Confidence score {score:.2f} meets threshold {CONFIDENCE_THRESHOLD}."
    else:
        reason = (
            f"Confidence score {score:.2f} below threshold "
            f"{CONFIDENCE_THRESHOLD}. Response may lack sufficient "
            "data backing."
        )

    return {"score": score, "passed": passed, "reason": reason}
