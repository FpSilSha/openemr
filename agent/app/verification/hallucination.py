"""Detect hallucinated clinical claims not backed by tool output data."""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)

# Patterns that indicate concrete clinical claims (numbers, units, dates)
_CLAIM_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|bpm|mmHg|%|kg|lb|mmol|mg/dL|"
    r"g/dL|U/L|IU/L|mEq/L|cells/mcL)\b",
    re.IGNORECASE,
)


def _extract_tool_data(messages: list[BaseMessage]) -> str:
    """Concatenate all tool message content into a single reference string."""
    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            parts.append(content)
    return "\n".join(parts)


def _extract_claims(text: str) -> list[str]:
    """Extract concrete clinical value claims from AI response text."""
    claims: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if _CLAIM_PATTERN.search(line):
            claims.append(line)
    return claims


def _claim_supported_by_data(claim: str, tool_data: str) -> bool:
    """Check if numbers in a claim appear in tool output data."""
    numbers = re.findall(r"\d+(?:\.\d+)?", claim)
    if not numbers:
        return True
    return any(num in tool_data for num in numbers)


async def check_hallucination(
    messages: list[BaseMessage],
    *,
    verification_model: Any | None = None,
) -> dict[str, Any]:
    """Check AI response for claims not supported by tool output.

    Uses heuristic matching by default. If a verification_model is provided,
    delegates nuanced judgment to the model for flagged claims.

    Returns:
        Dict with ``passed``, ``flagged_claims``, and ``reason``.
    """
    if not messages:
        return {
            "passed": True,
            "flagged_claims": [],
            "reason": "No messages to check.",
        }

    # Find last AI response
    ai_response = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str):
            ai_response = msg.content
            break

    if not ai_response:
        return {
            "passed": True,
            "flagged_claims": [],
            "reason": "No AI response found.",
        }

    tool_data = _extract_tool_data(messages)

    if not tool_data:
        # No tool data to compare against — pass if no concrete claims
        claims = _extract_claims(ai_response)
        if claims:
            return {
                "passed": False,
                "flagged_claims": claims,
                "reason": (
                    "AI response contains clinical values but "
                    "no tool data was retrieved to verify them."
                ),
            }
        return {
            "passed": True,
            "flagged_claims": [],
            "reason": "No tool data and no concrete claims.",
        }

    claims = _extract_claims(ai_response)
    flagged: list[str] = []

    for claim in claims:
        if not _claim_supported_by_data(claim, tool_data):
            flagged.append(claim)

    # If model is available and there are flagged claims, ask for judgment
    if flagged and verification_model is not None:
        try:
            prompt = (
                "You are a clinical data verification agent. "
                "Check if the following claims from an AI assistant's "
                "response are supported by the tool output data.\n\n"
                f"Tool data:\n{tool_data}\n\n"
                f"Flagged claims:\n" + "\n".join(flagged) + "\n\n"
                "For each claim, respond with SUPPORTED or UNSUPPORTED. "
                "Return only the unsupported claims, one per line. "
                "If all are supported, respond with 'ALL_SUPPORTED'."
            )
            model_response = await verification_model.ainvoke(
                [HumanMessage(content=prompt)]
            )
            response_text = (
                model_response.content
                if isinstance(model_response.content, str)
                else str(model_response.content)
            )
            if "ALL_SUPPORTED" in response_text:
                flagged = []
            else:
                # Keep only claims the model confirmed as unsupported
                remaining = []
                for claim in flagged:
                    # Check if any number from the claim appears in the
                    # model's unsupported list
                    numbers = re.findall(r"\d+(?:\.\d+)?", claim)
                    if any(num in response_text for num in numbers):
                        remaining.append(claim)
                flagged = remaining if remaining else flagged
        except Exception:
            logger.warning("Verification model call failed, using heuristic")

    if flagged:
        return {
            "passed": False,
            "flagged_claims": flagged,
            "reason": (
                f"{len(flagged)} claim(s) could not be verified "
                "against tool output data."
            ),
        }

    return {
        "passed": True,
        "flagged_claims": [],
        "reason": "All clinical claims verified against tool data.",
    }
