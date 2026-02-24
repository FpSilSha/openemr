"""Unit tests for the clinical note drafting LangChain tool (agent/app/tools/clinical_notes.py)."""

from datetime import datetime, timezone

import pytest

from app.tools.clinical_notes import VALID_NOTE_TYPES, create_clinical_note


@pytest.mark.asyncio
async def test_happy_path_soap_note():
    """Valid SOAP note returns success with all required draft fields and confirmation flag."""
    result = await create_clinical_note.ainvoke(
        {
            "patient_uuid": "uuid-1",
            "note_type": "SOAP",
            "content": "S: Patient reports headache. O: BP 120/80. "
            "A: Tension headache. P: Ibuprofen.",
        }
    )

    assert result["status"] == "success"
    draft = result["data"]["draft"]
    assert draft["patient_uuid"] == "uuid-1"
    assert draft["note_type"] == "SOAP"
    assert "headache" in draft["content"]
    assert "created_at" in draft
    assert result["data"]["requires_human_confirmation"] is True
    assert "message" in result["data"]


@pytest.mark.asyncio
async def test_all_valid_note_types_accepted():
    """Every type in VALID_NOTE_TYPES is accepted and returns a success response."""
    for note_type in VALID_NOTE_TYPES:
        result = await create_clinical_note.ainvoke(
            {
                "patient_uuid": "uuid-2",
                "note_type": note_type,
                "content": f"Sample content for {note_type} note.",
            }
        )
        assert result["status"] == "success", (
            f"Expected success for note_type='{note_type}', got: {result}"
        )
        assert result["data"]["draft"]["note_type"] == note_type


@pytest.mark.asyncio
async def test_invalid_note_type_returns_error():
    """Supplying an unrecognised note_type returns an error that lists the valid types."""
    result = await create_clinical_note.ainvoke(
        {
            "patient_uuid": "uuid-3",
            "note_type": "InvalidType",
            "content": "Some content.",
        }
    )

    assert result["status"] == "error"
    error_message = result["error"]
    assert "InvalidType" in error_message
    # At least one valid type name must appear in the error message
    assert any(valid_type in error_message for valid_type in VALID_NOTE_TYPES)


@pytest.mark.asyncio
async def test_empty_content_returns_error():
    """An empty string for content returns a structured error about empty content."""
    result = await create_clinical_note.ainvoke(
        {
            "patient_uuid": "uuid-4",
            "note_type": "Progress",
            "content": "",
        }
    )

    assert result["status"] == "error"
    assert "cannot be empty" in result["error"]


@pytest.mark.asyncio
async def test_whitespace_only_content_returns_error():
    """Content consisting solely of whitespace is treated as empty and returns an error."""
    result = await create_clinical_note.ainvoke(
        {
            "patient_uuid": "uuid-5",
            "note_type": "Progress",
            "content": "   ",
        }
    )

    assert result["status"] == "error"
    assert "cannot be empty" in result["error"]


@pytest.mark.asyncio
async def test_content_is_stripped():
    """Content with leading and trailing whitespace is stripped in the returned draft."""
    raw_content = "  Leading and trailing spaces  "

    result = await create_clinical_note.ainvoke(
        {
            "patient_uuid": "uuid-6",
            "note_type": "Consultation",
            "content": raw_content,
        }
    )

    assert result["status"] == "success"
    stored_content = result["data"]["draft"]["content"]
    assert stored_content == raw_content.strip()
    assert not stored_content.startswith(" ")
    assert not stored_content.endswith(" ")


@pytest.mark.asyncio
async def test_draft_includes_utc_timestamp():
    """The draft includes a created_at field that is a valid ISO-format UTC timestamp string."""
    before = datetime.now(timezone.utc)

    result = await create_clinical_note.ainvoke(
        {
            "patient_uuid": "uuid-7",
            "note_type": "Discharge",
            "content": "Patient discharged in stable condition.",
        }
    )

    after = datetime.now(timezone.utc)

    assert result["status"] == "success"
    created_at_str = result["data"]["draft"]["created_at"]
    assert isinstance(created_at_str, str)

    # Must parse as a valid ISO timestamp
    created_at = datetime.fromisoformat(created_at_str)
    assert before <= created_at <= after


@pytest.mark.asyncio
async def test_draft_message_mentions_review():
    """The message field instructs that the draft must be reviewed/approved by a clinician."""
    result = await create_clinical_note.ainvoke(
        {
            "patient_uuid": "uuid-8",
            "note_type": "Procedure",
            "content": "Procedure performed without complications.",
        }
    )

    assert result["status"] == "success"
    message = result["data"]["message"].lower()
    assert "reviewed" in message or "approved" in message
    assert "clinician" in message
