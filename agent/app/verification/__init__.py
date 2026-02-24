"""Verification layer — runs post-response checks before final output."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import BaseMessage

from app.verification.confidence import compute_confidence
from app.verification.drug_interactions import check_drug_interaction_coverage
from app.verification.hallucination import check_hallucination
from app.verification.output_validator import validate_output

logger = logging.getLogger(__name__)


async def run_verification(
    messages: list[BaseMessage],
    *,
    verification_model: Any | None = None,
) -> dict[str, Any]:
    """Execute all verification checks and return a combined result.

    Args:
        messages: Full conversation message history including tool results.
        verification_model: Optional ChatAnthropic instance for hallucination check.

    Returns:
        Dict with ``passed`` bool and individual check results.
    """
    drug_result = check_drug_interaction_coverage(messages)
    hallucination_result = await check_hallucination(
        messages, verification_model=verification_model
    )
    confidence_result = compute_confidence(messages)
    output_result = validate_output(messages)

    checks = {
        "drug_interactions": drug_result,
        "hallucination": hallucination_result,
        "confidence": confidence_result,
        "output_validation": output_result,
    }

    all_passed = all(c["passed"] for c in checks.values())

    if not all_passed:
        failed = [k for k, v in checks.items() if not v["passed"]]
        logger.warning("Verification failed checks: %s", failed)

    return {"passed": all_passed, "checks": checks}
