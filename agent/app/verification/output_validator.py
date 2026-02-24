"""Validate the agent's final output for formatting and safety issues."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

# Patterns that suggest raw API/JSON data leaked into the response
_RAW_JSON_PATTERN = re.compile(
    r'\{\s*"(?:resourceType|status|entry|error)"', re.IGNORECASE
)

# Patterns that suggest swallowed tool errors
_SWALLOWED_ERROR_PATTERNS = [
    re.compile(r"Tool '[\w]+' failed:", re.IGNORECASE),
    re.compile(r"Tool '[\w]+' timed out", re.IGNORECASE),
    re.compile(r"ConnectionError:", re.IGNORECASE),
    re.compile(r"TimeoutError:", re.IGNORECASE),
]


def validate_output(messages: list[BaseMessage]) -> dict[str, Any]:
    """Validate the final AI response for quality and safety.

    Checks:
    - Response is non-empty
    - No raw JSON/API data leaked into response
    - No tool error messages silently passed through

    Returns:
        Dict with ``passed`` bool and ``issues`` list.
    """
    if not messages:
        return {"passed": False, "issues": ["No messages to validate."]}

    # Find last AI response
    ai_response = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str):
            ai_response = msg.content
            break

    issues: list[str] = []

    # Check 1: Non-empty response
    if not ai_response or not ai_response.strip():
        issues.append("Response is empty.")
        return {"passed": False, "issues": issues}

    # Check 2: No raw JSON data leaked
    if _RAW_JSON_PATTERN.search(ai_response):
        issues.append("Response contains raw JSON/API data.")

    # Check 3: No swallowed tool errors
    for pattern in _SWALLOWED_ERROR_PATTERNS:
        if pattern.search(ai_response):
            issues.append(
                f"Response contains tool error message: "
                f"{pattern.pattern}"
            )
            break  # One error message finding is enough

    passed = len(issues) == 0
    return {"passed": passed, "issues": issues}
