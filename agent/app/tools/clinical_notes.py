"""Clinical note drafting LangChain tool."""

from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import tool

from app.tools.base import tool_error_handler

VALID_NOTE_TYPES = {"SOAP", "Progress", "Procedure", "Discharge", "Consultation"}


@tool
@tool_error_handler
async def create_clinical_note(
    patient_uuid: str, note_type: str, content: str
) -> dict[str, Any]:
    """Draft a clinical note for clinician review. This does NOT save the note —
    it returns a draft that must be approved by a clinician before being committed
    to the patient record.

    Args:
        patient_uuid: The UUID of the patient in OpenEMR.
        note_type: Type of clinical note — one of SOAP, Progress, Procedure,
            Discharge, or Consultation.
        content: The clinical note content drafted by the agent.
    """
    if note_type not in VALID_NOTE_TYPES:
        return {
            "status": "error",
            "error": (
                f"Invalid note_type '{note_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_NOTE_TYPES))}"
            ),
        }

    if not content or not content.strip():
        return {
            "status": "error",
            "error": "Note content cannot be empty.",
        }

    return {
        "status": "success",
        "data": {
            "draft": {
                "patient_uuid": patient_uuid,
                "note_type": note_type,
                "content": content.strip(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "requires_human_confirmation": True,
            "message": (
                "This is a DRAFT clinical note. It must be reviewed and approved "
                "by a clinician before being saved to the patient record."
            ),
        },
    }
