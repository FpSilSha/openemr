"""Verify that drug interaction checks were performed when medications are discussed."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

# Patterns that suggest medication discussion
_MED_PATTERNS = re.compile(
    r"\b("
    r"medication|drug|prescription|dose|dosage|mg|mcg|ml|tablet|capsule"
    r"|aspirin|warfarin|metformin|lisinopril|ibuprofen|acetaminophen"
    r"|amoxicillin|omeprazole|atorvastatin|amlodipine|losartan"
    r"|interaction|contraindic"
    r")\b",
    re.IGNORECASE,
)


def _mentions_medications(text: str) -> bool:
    """Return True if text contains medication-related keywords."""
    return bool(_MED_PATTERNS.search(text))


def _drug_check_was_called(messages: list[BaseMessage]) -> bool:
    """Return True if drug_interaction_check appears in tool call history."""
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            for tc in msg.tool_calls or []:
                if tc.get("name") == "drug_interaction_check":
                    return True
        if isinstance(msg, ToolMessage):
            if getattr(msg, "name", "") == "drug_interaction_check":
                return True
    return False


def check_drug_interaction_coverage(
    messages: list[BaseMessage],
) -> dict[str, Any]:
    """Check if medication discussion was accompanied by interaction check.

    Returns:
        Dict with ``passed`` bool and ``reason`` string.
    """
    if not messages:
        return {"passed": True, "reason": "No messages to check."}

    # Look at the final AI response
    ai_response = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str):
            ai_response = msg.content
            break

    if not ai_response:
        return {"passed": True, "reason": "No AI response found."}

    if not _mentions_medications(ai_response):
        return {"passed": True, "reason": "No medication discussion detected."}

    if _drug_check_was_called(messages):
        return {
            "passed": True,
            "reason": "Drug interaction check was performed.",
        }

    return {
        "passed": False,
        "reason": (
            "Response discusses medications but no drug interaction "
            "check was performed. Consider running drug_interaction_check."
        ),
    }
