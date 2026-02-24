"""Unit tests for the vital signs LangChain tool (agent/app/tools/vitals.py)."""

from unittest.mock import AsyncMock

import pytest

import app.tools.vitals as vitals_module
from app.tools.vitals import get_vitals, set_client


@pytest.mark.asyncio
async def test_happy_path_single_vital(mock_openemr_client):
    """Happy path: single vital with all fields populated from fixture data."""
    set_client(mock_openemr_client)

    result = await get_vitals.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    vitals = result["data"]["vitals"]
    assert len(vitals) == 1
    assert result["data"]["total"] == 1
    assert vitals[0]["type"] == "Blood Pressure"
    assert vitals[0]["value"] == 120
    assert vitals[0]["unit"] == "mmHg"
    assert vitals[0]["date"] == "2026-01-15"


@pytest.mark.asyncio
async def test_multiple_vitals_parsed(mock_openemr_client):
    """Three vitals in the bundle — BP, HR, and Temp — are all parsed correctly."""
    mock_openemr_client.get_vitals.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Blood Pressure"},
                    "valueQuantity": {"value": 118, "unit": "mmHg"},
                    "effectiveDateTime": "2026-01-15",
                }
            },
            {
                "resource": {
                    "code": {"text": "Heart Rate"},
                    "valueQuantity": {"value": 72, "unit": "bpm"},
                    "effectiveDateTime": "2026-01-15",
                }
            },
            {
                "resource": {
                    "code": {"text": "Temperature"},
                    "valueQuantity": {"value": 98.6, "unit": "degF"},
                    "effectiveDateTime": "2026-01-15",
                }
            },
        ],
    }
    set_client(mock_openemr_client)

    result = await get_vitals.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    vitals = result["data"]["vitals"]
    assert len(vitals) == 3
    assert result["data"]["total"] == 3
    assert vitals[0]["type"] == "Blood Pressure"
    assert vitals[0]["value"] == 118
    assert vitals[1]["type"] == "Heart Rate"
    assert vitals[1]["value"] == 72
    assert vitals[1]["unit"] == "bpm"
    assert vitals[2]["type"] == "Temperature"
    assert vitals[2]["value"] == 98.6
    assert vitals[2]["unit"] == "degF"


@pytest.mark.asyncio
async def test_empty_bundle_returns_empty_list(mock_openemr_client):
    """An empty entry list in the bundle produces an empty vitals list with total=0."""
    mock_openemr_client.get_vitals.return_value = {
        "resourceType": "Bundle",
        "entry": [],
    }
    set_client(mock_openemr_client)

    result = await get_vitals.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    assert result["data"]["vitals"] == []
    assert result["data"]["total"] == 0


@pytest.mark.asyncio
async def test_missing_value_quantity_falls_back_to_value_string():
    """When valueQuantity is absent but valueString is present, value is set to valueString."""
    client = AsyncMock()
    client.get_vitals.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Respiratory Quality"},
                    "valueString": "Normal",
                    "effectiveDateTime": "2026-02-01",
                }
            }
        ],
    }
    set_client(client)

    result = await get_vitals.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    vitals = result["data"]["vitals"]
    assert len(vitals) == 1
    assert vitals[0]["type"] == "Respiratory Quality"
    assert vitals[0]["value"] == "Normal"
    assert vitals[0]["unit"] == ""


@pytest.mark.asyncio
async def test_missing_code_text_falls_back_to_coding_display():
    """When code.text is absent, the vital type falls back to coding[0].display."""
    client = AsyncMock()
    client.get_vitals.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {
                        "coding": [
                            {"code": "8867-4", "display": "Heart Rate"}
                        ]
                    },
                    "valueQuantity": {"value": 68, "unit": "bpm"},
                    "effectiveDateTime": "2026-02-10",
                }
            }
        ],
    }
    set_client(client)

    result = await get_vitals.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    vitals = result["data"]["vitals"]
    assert len(vitals) == 1
    assert vitals[0]["type"] == "Heart Rate"
    assert vitals[0]["value"] == 68


@pytest.mark.asyncio
async def test_missing_effective_date_defaults_to_empty():
    """When effectiveDateTime is absent from a resource, the date field defaults to empty string."""
    client = AsyncMock()
    client.get_vitals.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Oxygen Saturation"},
                    "valueQuantity": {"value": 98, "unit": "%"},
                }
            }
        ],
    }
    set_client(client)

    result = await get_vitals.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    vitals = result["data"]["vitals"]
    assert len(vitals) == 1
    assert vitals[0]["type"] == "Oxygen Saturation"
    assert vitals[0]["date"] == ""


@pytest.mark.asyncio
async def test_client_error_returns_structured_error(mock_openemr_client):
    """ConnectionError from client returns a structured error dict."""
    mock_openemr_client.get_vitals.side_effect = ConnectionError("fail")
    set_client(mock_openemr_client)

    result = await get_vitals.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "error" in result
    assert "fail" in result["error"]


@pytest.mark.asyncio
async def test_no_client_raises_runtime_error():
    """Uninitialized client returns a structured error with RuntimeError."""
    vitals_module._client = None

    result = await get_vitals.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "error" in result
    assert "RuntimeError" in result["error"] or "not initialized" in result["error"]
