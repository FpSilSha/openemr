"""Unit tests for patient LangChain tools (agent/app/tools/patient.py)."""


import pytest

from app.tools.patient import get_patient_summary, search_patients, set_client

# ---------------------------------------------------------------------------
# get_patient_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_patient_summary_happy_path(mock_openemr_client):
    """Summary tool assembles all five sub-calls into a single success dict."""
    set_client(mock_openemr_client)

    result = await get_patient_summary.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    data = result["data"]
    assert data["patient"]["id"] == "uuid-1"
    assert data["patient"]["name"][0]["family"] == "Doe"

    # Conditions bundle forwarded as-is
    assert data["conditions"]["resourceType"] == "Bundle"
    assert len(data["conditions"]["entry"]) == 1
    assert data["conditions"]["entry"][0]["resource"]["code"]["coding"][0]["code"] == "E11.9"

    # Medications bundle contains both meds
    assert len(data["medications"]["entry"]) == 2
    med_texts = [
        e["resource"]["medicationCodeableConcept"]["text"]
        for e in data["medications"]["entry"]
    ]
    assert "Metformin 500mg" in med_texts
    assert "Lisinopril 10mg" in med_texts

    # Allergies bundle
    assert len(data["allergies"]["entry"]) == 1
    assert data["allergies"]["entry"][0]["resource"]["code"]["text"] == "Penicillin"

    # Vitals bundle
    assert data["vitals"]["entry"][0]["resource"]["code"]["text"] == "Blood Pressure"


@pytest.mark.asyncio
async def test_get_patient_summary_calls_all_five_endpoints(mock_openemr_client):
    """Verify each OpenEMR endpoint is called exactly once with the correct UUID."""
    set_client(mock_openemr_client)

    await get_patient_summary.ainvoke({"patient_uuid": "uuid-1"})

    mock_openemr_client.get_patient.assert_awaited_once_with("uuid-1")
    mock_openemr_client.get_conditions.assert_awaited_once_with("uuid-1")
    mock_openemr_client.get_medications.assert_awaited_once_with("uuid-1")
    mock_openemr_client.get_allergies.assert_awaited_once_with("uuid-1")
    mock_openemr_client.get_vitals.assert_awaited_once_with("uuid-1")


@pytest.mark.asyncio
async def test_get_patient_summary_client_error_returns_structured_error(
    mock_openemr_client,
):
    """When any sub-call raises, tool_error_handler returns a structured error dict."""
    mock_openemr_client.get_conditions.side_effect = ConnectionError("API unreachable")
    set_client(mock_openemr_client)

    result = await get_patient_summary.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "get_patient_summary" in result["error"]
    assert "ConnectionError" in result["error"]
    assert "API unreachable" in result["error"]


@pytest.mark.asyncio
async def test_get_patient_summary_timeout_returns_structured_error(
    mock_openemr_client,
):
    """TimeoutError is caught and returns a structured timeout error."""
    mock_openemr_client.get_vitals.side_effect = TimeoutError()
    set_client(mock_openemr_client)

    result = await get_patient_summary.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "timed out" in result["error"].lower()
    assert "get_patient_summary" in result["error"]


@pytest.mark.asyncio
async def test_get_patient_summary_no_client_raises_runtime_error():
    """Calling set_client(None) causes _get_client() to raise, surfaced as structured error."""
    set_client(None)  # type: ignore[arg-type]

    result = await get_patient_summary.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "RuntimeError" in result["error"]
    assert "not initialized" in result["error"]


# ---------------------------------------------------------------------------
# search_patients
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_patients_happy_path(mock_openemr_client):
    """Search returns a properly shaped patient list with name assembled from FHIR parts."""
    set_client(mock_openemr_client)

    result = await search_patients.ainvoke({"name": "Doe"})

    assert result["status"] == "success"
    data = result["data"]
    assert data["total"] == 1
    patient = data["patients"][0]
    assert patient["uuid"] == "uuid-1"
    assert patient["name"] == "John Doe"
    assert patient["birthDate"] == "1980-01-15"
    assert patient["gender"] == "male"


@pytest.mark.asyncio
async def test_search_patients_multiple_results(mock_openemr_client):
    """All entries in the FHIR Bundle are parsed and returned."""
    mock_openemr_client.search_patients.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "id": "uuid-1",
                    "name": [{"family": "Doe", "given": ["John"]}],
                    "birthDate": "1980-01-15",
                    "gender": "male",
                }
            },
            {
                "resource": {
                    "id": "uuid-2",
                    "name": [{"family": "Doe", "given": ["Jane"]}],
                    "birthDate": "1985-06-20",
                    "gender": "female",
                }
            },
        ],
    }
    set_client(mock_openemr_client)

    result = await search_patients.ainvoke({"name": "Doe"})

    assert result["status"] == "success"
    assert result["data"]["total"] == 2
    names = [p["name"] for p in result["data"]["patients"]]
    assert "John Doe" in names
    assert "Jane Doe" in names


@pytest.mark.asyncio
async def test_search_patients_empty_bundle_returns_empty_list(mock_openemr_client):
    """A Bundle with no entries returns an empty patient list with total=0."""
    mock_openemr_client.search_patients.return_value = {
        "resourceType": "Bundle",
        "entry": [],
    }
    set_client(mock_openemr_client)

    result = await search_patients.ainvoke({"name": "Nobody"})

    assert result["status"] == "success"
    assert result["data"]["patients"] == []
    assert result["data"]["total"] == 0


@pytest.mark.asyncio
async def test_search_patients_missing_entry_key(mock_openemr_client):
    """A Bundle missing the 'entry' key entirely is handled gracefully (no crash)."""
    mock_openemr_client.search_patients.return_value = {"resourceType": "Bundle"}
    set_client(mock_openemr_client)

    result = await search_patients.ainvoke({"name": "Doe"})

    assert result["status"] == "success"
    assert result["data"]["patients"] == []
    assert result["data"]["total"] == 0


@pytest.mark.asyncio
async def test_search_patients_missing_given_name(mock_openemr_client):
    """When the 'given' field is absent, family name alone is used without crashing."""
    mock_openemr_client.search_patients.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "id": "uuid-3",
                    "name": [{"family": "Smith"}],
                    "birthDate": "1970-03-10",
                    "gender": "male",
                }
            }
        ],
    }
    set_client(mock_openemr_client)

    result = await search_patients.ainvoke({"name": "Smith"})

    assert result["status"] == "success"
    patient = result["data"]["patients"][0]
    assert patient["name"] == "Smith"
    assert patient["uuid"] == "uuid-3"


@pytest.mark.asyncio
async def test_search_patients_missing_name_array(mock_openemr_client):
    """When the 'name' array is absent, display_name falls back to empty string."""
    mock_openemr_client.search_patients.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "id": "uuid-4",
                    "birthDate": "1990-07-22",
                    "gender": "unknown",
                }
            }
        ],
    }
    set_client(mock_openemr_client)

    result = await search_patients.ainvoke({"name": "unknown"})

    assert result["status"] == "success"
    patient = result["data"]["patients"][0]
    assert patient["name"] == ""
    assert patient["uuid"] == "uuid-4"


@pytest.mark.asyncio
async def test_search_patients_client_error_returns_structured_error(
    mock_openemr_client,
):
    """When search_patients raises, tool_error_handler returns a structured error dict."""
    mock_openemr_client.search_patients.side_effect = ValueError("Bad search param")
    set_client(mock_openemr_client)

    result = await search_patients.ainvoke({"name": "Doe"})

    assert result["status"] == "error"
    assert "search_patients" in result["error"]
    assert "ValueError" in result["error"]
    assert "Bad search param" in result["error"]
