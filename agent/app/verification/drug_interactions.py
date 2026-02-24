"""Verify that drug interaction checks were performed when medications are discussed."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

# Generic medication terms (need a specific drug name too)
_GENERIC_MED_TERMS = re.compile(
    r"\b(medication|drug|prescription|dose|dosage|tablet|capsule"
    r"|interaction|contraindic)\b",
    re.IGNORECASE,
)

# Specific drug names or dosage units that indicate real medication discussion
_SPECIFIC_MED_PATTERNS = re.compile(
    r"\b("
    r"aspirin|warfarin|metformin|lisinopril|ibuprofen|acetaminophen"
    r"|amoxicillin|omeprazole|atorvastatin|amlodipine|losartan"
    r"|hydrochlorothiazide|prednisone|gabapentin|levothyroxine"
    r"|oxycodone|tramadol|clopidogrel|simvastatin|pantoprazole"
    r")\b",
    re.IGNORECASE,
)

# Dosage pattern (e.g., "500mg", "10 mg", "0.5 mcg")
_DOSAGE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|units?)\b",
    re.IGNORECASE,
)


def _mentions_medications(text: str) -> bool:
    """Return True if text discusses specific medications (not just listing capabilities)."""
    # Require a specific drug name OR a dosage pattern
    has_specific = bool(_SPECIFIC_MED_PATTERNS.search(text))
    has_dosage = bool(_DOSAGE_PATTERN.search(text))
    return has_specific or has_dosage


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
