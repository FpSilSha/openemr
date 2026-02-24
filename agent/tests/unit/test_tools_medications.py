"""Unit tests for medication-related LangChain tools."""

from unittest.mock import AsyncMock

import pytest

import app.tools.medications as medications_module
from app.tools.medications import drug_interaction_check, get_medications, set_clients

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_medication_entry(text=None, coding_display=None, status="active", intent="order"):
    """Build a minimal FHIR MedicationRequest Bundle entry."""
    med_concept = {}
    if text is not None:
        med_concept["text"] = text
    if coding_display is not None:
        med_concept["coding"] = [{"display": coding_display}]
    return {
        "resource": {
            "medicationCodeableConcept": med_concept,
            "status": status,
            "intent": intent,
        }
    }


# ---------------------------------------------------------------------------
# get_medications — happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_medications_returns_two_meds(mock_openemr_client, mock_drug_client):
    """Standard fixture bundle with 2 medications is parsed correctly."""
    set_clients(mock_openemr_client, mock_drug_client)

    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    meds = result["data"]["medications"]
    assert len(meds) == 2

    names = [m["medication"] for m in meds]
    assert "Metformin 500mg" in names
    assert "Lisinopril 10mg" in names

    for med in meds:
        assert med["status"] == "active"
        assert med["intent"] == "order"


@pytest.mark.asyncio
async def test_get_medications_uses_coding_fallback(mock_drug_client):
    """When medicationCodeableConcept has no 'text', fall back to coding[0].display."""
    openemr_mock = AsyncMock()
    openemr_mock.get_medications.return_value = {
        "resourceType": "Bundle",
        "entry": [
            _make_medication_entry(coding_display="Aspirin 81mg", status="active", intent="plan")
        ],
    }
    set_clients(openemr_mock, mock_drug_client)

    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    meds = result["data"]["medications"]
    assert len(meds) == 1
    assert meds[0]["medication"] == "Aspirin 81mg"
    assert meds[0]["intent"] == "plan"


@pytest.mark.asyncio
async def test_get_medications_prefers_text_over_coding(mock_drug_client):
    """When both 'text' and coding are present, 'text' takes priority."""
    openemr_mock = AsyncMock()
    openemr_mock.get_medications.return_value = {
        "resourceType": "Bundle",
        "entry": [
            _make_medication_entry(
                text="Metformin 500mg", coding_display="Metformin", status="active", intent="order"
            )
        ],
    }
    set_clients(openemr_mock, mock_drug_client)

    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})

    meds = result["data"]["medications"]
    assert meds[0]["medication"] == "Metformin 500mg"


@pytest.mark.asyncio
async def test_get_medications_empty_bundle(mock_drug_client):
    """A bundle with zero entries returns an empty medications list."""
    openemr_mock = AsyncMock()
    openemr_mock.get_medications.return_value = {"resourceType": "Bundle", "entry": []}
    set_clients(openemr_mock, mock_drug_client)

    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    assert result["data"]["medications"] == []


@pytest.mark.asyncio
async def test_get_medications_missing_entry_key(mock_drug_client):
    """A bundle response without an 'entry' key returns an empty medications list."""
    openemr_mock = AsyncMock()
    openemr_mock.get_medications.return_value = {"resourceType": "Bundle"}
    set_clients(openemr_mock, mock_drug_client)

    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    assert result["data"]["medications"] == []


@pytest.mark.asyncio
async def test_get_medications_missing_medication_codeable_concept(mock_drug_client):
    """Entry with no medicationCodeableConcept resolves to an empty string for name."""
    openemr_mock = AsyncMock()
    openemr_mock.get_medications.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "status": "active",
                    "intent": "order",
                }
            }
        ],
    }
    set_clients(openemr_mock, mock_drug_client)

    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    meds = result["data"]["medications"]
    assert len(meds) == 1
    assert meds[0]["medication"] == ""


# ---------------------------------------------------------------------------
# get_medications — error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_medications_client_error_returns_structured_error(mock_drug_client):
    """When the OpenEMR client raises, the error handler returns a structured error dict."""
    openemr_mock = AsyncMock()
    openemr_mock.get_medications.side_effect = RuntimeError("Connection refused")
    set_clients(openemr_mock, mock_drug_client)

    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "RuntimeError" in result["error"]
    assert "Connection refused" in result["error"]


# ---------------------------------------------------------------------------
# drug_interaction_check — happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drug_interaction_check_known_pair_with_interactions(
    mock_openemr_client, mock_drug_client
):
    """aspirin + warfarin are both resolved and a high-severity interaction is returned."""
    set_clients(mock_openemr_client, mock_drug_client)

    result = await drug_interaction_check.ainvoke({"drug_names": ["aspirin", "warfarin"]})

    assert result["status"] == "success"
    data = result["data"]
    assert data["resolved_drugs"] == {"aspirin": "1191", "warfarin": "11289"}
    assert len(data["interactions"]) == 1
    assert data["interactions"][0]["severity"] == "high"


@pytest.mark.asyncio
async def test_drug_interaction_check_safe_pair_no_interactions(mock_openemr_client):
    """metformin + lisinopril resolve but check_multi_interactions returns no interactions."""
    drug_mock = AsyncMock()
    drug_mock.get_rxcui.side_effect = lambda name: {
        "metformin": "6809",
        "lisinopril": "29046",
    }.get(name.lower())
    drug_mock.check_multi_interactions.return_value = []

    set_clients(mock_openemr_client, drug_mock)

    result = await drug_interaction_check.ainvoke({"drug_names": ["metformin", "lisinopril"]})

    assert result["status"] == "success"
    assert result["data"]["interactions"] == []
    assert "metformin" in result["data"]["resolved_drugs"]
    assert "lisinopril" in result["data"]["resolved_drugs"]


@pytest.mark.asyncio
async def test_drug_interaction_check_mix_resolved_and_unresolved(mock_openemr_client):
    """One known drug and one unknown; only the known one resolves, so <2 RxCUIs → note."""
    drug_mock = AsyncMock()
    drug_mock.get_rxcui.side_effect = lambda name: {"aspirin": "1191"}.get(name.lower())

    set_clients(mock_openemr_client, drug_mock)

    result = await drug_interaction_check.ainvoke({"drug_names": ["aspirin", "unknowndrug"]})

    assert result["status"] == "success"
    data = result["data"]
    assert data["interactions"] == []
    assert "Need at least 2" in data["note"]
    assert data["resolved"] == {"aspirin": "1191"}


@pytest.mark.asyncio
async def test_drug_interaction_check_single_drug(mock_openemr_client, mock_drug_client):
    """A single drug cannot form an interaction pair; note is returned."""
    set_clients(mock_openemr_client, mock_drug_client)

    result = await drug_interaction_check.ainvoke({"drug_names": ["aspirin"]})

    assert result["status"] == "success"
    assert result["data"]["interactions"] == []
    assert "Need at least 2" in result["data"]["note"]


@pytest.mark.asyncio
async def test_drug_interaction_check_all_unresolved(mock_openemr_client, mock_drug_client):
    """All unrecognised drug names resolve to None; no interaction check is performed."""
    set_clients(mock_openemr_client, mock_drug_client)

    result = await drug_interaction_check.ainvoke({"drug_names": ["fakedrug1", "fakedrug2"]})

    assert result["status"] == "success"
    data = result["data"]
    assert data["interactions"] == []
    assert "Need at least 2" in data["note"]
    assert data["resolved"] == {}
    mock_drug_client.check_multi_interactions.assert_not_called()


@pytest.mark.asyncio
async def test_drug_interaction_check_empty_list(mock_openemr_client, mock_drug_client):
    """Passing an empty drug list returns the 'need at least 2' note without errors."""
    set_clients(mock_openemr_client, mock_drug_client)

    result = await drug_interaction_check.ainvoke({"drug_names": []})

    assert result["status"] == "success"
    data = result["data"]
    assert data["interactions"] == []
    assert "Need at least 2" in data["note"]
    mock_drug_client.check_multi_interactions.assert_not_called()


# ---------------------------------------------------------------------------
# drug_interaction_check — error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drug_interaction_check_client_error_returns_structured_error(mock_openemr_client):
    """When the drug client raises on get_rxcui, the error handler captures it."""
    drug_mock = AsyncMock()
    drug_mock.get_rxcui.side_effect = ConnectionError("RxNorm API unreachable")

    set_clients(mock_openemr_client, drug_mock)

    result = await drug_interaction_check.ainvoke({"drug_names": ["aspirin", "warfarin"]})

    assert result["status"] == "error"
    assert "ConnectionError" in result["error"]
    assert "RxNorm API unreachable" in result["error"]


# ---------------------------------------------------------------------------
# Client initialisation guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_medications_raises_when_client_not_set():
    """Calling get_medications without initialised clients raises RuntimeError via handler."""
    # Reset module-level state
    medications_module._openemr_client = None
    medications_module._drug_client = None

    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "RuntimeError" in result["error"]
