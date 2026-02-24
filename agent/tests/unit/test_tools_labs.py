"""Unit tests for the lab results LangChain tool (agent/app/tools/labs.py)."""


import pytest

from app.tools.labs import get_lab_results, set_client


@pytest.mark.asyncio
async def test_single_lab_result_happy_path(mock_openemr_client):
    """Happy path: single lab with all fields populated from fixture data."""
    set_client(mock_openemr_client)

    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    labs = result["data"]["lab_results"]
    assert len(labs) == 1
    assert labs[0]["test"] == "Hemoglobin A1c"
    assert labs[0]["value"] == 6.5
    assert labs[0]["unit"] == "%"
    assert labs[0]["date"] == "2026-01-15"
    assert labs[0]["status"] == "final"


@pytest.mark.asyncio
async def test_passes_laboratory_category_to_client(mock_openemr_client):
    """Verifies the tool always passes category='laboratory' to get_observations."""
    set_client(mock_openemr_client)

    await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    mock_openemr_client.get_observations.assert_called_once_with(
        "uuid-1", category="laboratory"
    )


@pytest.mark.asyncio
async def test_multiple_lab_results(mock_openemr_client):
    """Multiple entries in the bundle are all parsed into the result list."""
    mock_openemr_client.get_observations.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Hemoglobin A1c"},
                    "valueQuantity": {"value": 6.5, "unit": "%"},
                    "effectiveDateTime": "2026-01-15",
                    "status": "final",
                }
            },
            {
                "resource": {
                    "code": {"text": "Creatinine"},
                    "valueQuantity": {"value": 0.9, "unit": "mg/dL"},
                    "effectiveDateTime": "2026-01-15",
                    "status": "final",
                }
            },
            {
                "resource": {
                    "code": {"text": "eGFR"},
                    "valueQuantity": {"value": 85.0, "unit": "mL/min/1.73m2"},
                    "effectiveDateTime": "2026-01-15",
                    "status": "final",
                }
            },
        ],
    }
    set_client(mock_openemr_client)

    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    labs = result["data"]["lab_results"]
    assert len(labs) == 3
    assert labs[0]["test"] == "Hemoglobin A1c"
    assert labs[1]["test"] == "Creatinine"
    assert labs[1]["value"] == 0.9
    assert labs[1]["unit"] == "mg/dL"
    assert labs[2]["test"] == "eGFR"


@pytest.mark.asyncio
async def test_empty_bundle_returns_empty_list(mock_openemr_client):
    """An empty entry list in the bundle produces an empty lab_results list."""
    mock_openemr_client.get_observations.return_value = {
        "resourceType": "Bundle",
        "entry": [],
    }
    set_client(mock_openemr_client)

    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    assert result["data"]["lab_results"] == []


@pytest.mark.asyncio
async def test_missing_entry_key_returns_empty_list(mock_openemr_client):
    """When the 'entry' key is entirely absent from the response, returns empty list."""
    mock_openemr_client.get_observations.return_value = {
        "resourceType": "Bundle",
    }
    set_client(mock_openemr_client)

    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    assert result["data"]["lab_results"] == []


@pytest.mark.asyncio
async def test_value_string_fallback_when_no_value_quantity(mock_openemr_client):
    """When valueQuantity is absent, the value falls back to valueString."""
    mock_openemr_client.get_observations.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Urine Culture"},
                    "valueString": "No growth",
                    "effectiveDateTime": "2026-01-20",
                    "status": "final",
                }
            }
        ],
    }
    set_client(mock_openemr_client)

    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    labs = result["data"]["lab_results"]
    assert len(labs) == 1
    assert labs[0]["test"] == "Urine Culture"
    assert labs[0]["value"] == "No growth"
    assert labs[0]["unit"] == ""


@pytest.mark.asyncio
async def test_code_from_coding_array_fallback_when_no_text(mock_openemr_client):
    """When code.text is absent, the test name falls back to coding[0].display."""
    mock_openemr_client.get_observations.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {
                        "coding": [
                            {
                                "code": "4548-4",
                                "display": "Hemoglobin A1c/Hemoglobin.total in Blood",
                            }
                        ]
                    },
                    "valueQuantity": {"value": 7.2, "unit": "%"},
                    "effectiveDateTime": "2026-02-01",
                    "status": "final",
                }
            }
        ],
    }
    set_client(mock_openemr_client)

    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    labs = result["data"]["lab_results"]
    assert len(labs) == 1
    assert labs[0]["test"] == "Hemoglobin A1c/Hemoglobin.total in Blood"
    assert labs[0]["value"] == 7.2


@pytest.mark.asyncio
async def test_missing_value_quantity_entirely_defaults_to_empty(mock_openemr_client):
    """When valueQuantity and valueString are both absent, value and unit default."""
    mock_openemr_client.get_observations.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Pending Lab"},
                    "effectiveDateTime": "2026-02-10",
                    "status": "registered",
                }
            }
        ],
    }
    set_client(mock_openemr_client)

    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    labs = result["data"]["lab_results"]
    assert len(labs) == 1
    assert labs[0]["test"] == "Pending Lab"
    assert labs[0]["value"] == ""
    assert labs[0]["unit"] == ""
    assert labs[0]["status"] == "registered"


@pytest.mark.asyncio
async def test_client_exception_returns_structured_error(mock_openemr_client):
    """When the client raises an exception, the error handler returns a structured error dict."""
    mock_openemr_client.get_observations.side_effect = RuntimeError(
        "Connection timeout"
    )
    set_client(mock_openemr_client)

    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "error" in result
    assert "Connection timeout" in result["error"]
