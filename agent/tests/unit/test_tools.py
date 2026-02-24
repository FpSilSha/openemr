"""Unit tests for LangChain tool layer."""

from unittest.mock import AsyncMock

import pytest

from app.tools import MVP_TOOLS
from app.tools.base import tool_error_handler
from app.tools.icd10 import icd10_lookup
from app.tools.icd10 import set_client as set_icd10_client
from app.tools.labs import get_lab_results
from app.tools.labs import set_client as set_labs_client
from app.tools.medications import (
    drug_interaction_check,
    get_medications,
)
from app.tools.medications import (
    set_clients as set_med_clients,
)
from app.tools.patient import get_patient_summary, search_patients
from app.tools.patient import set_client as set_patient_client
from app.tools.pubmed import pubmed_search
from app.tools.pubmed import set_client as set_pubmed_client


def test_mvp_tools_count():
    assert len(MVP_TOOLS) == 7


def test_all_tools_have_names():
    for t in MVP_TOOLS:
        assert hasattr(t, "name")
        assert t.name


# --- Patient tools ---


@pytest.fixture
def mock_openemr():
    client = AsyncMock()
    client.get_patient.return_value = {
        "resourceType": "Patient",
        "id": "uuid-1",
        "name": [{"family": "Doe", "given": ["John"]}],
    }
    client.get_conditions.return_value = {"resourceType": "Bundle", "entry": []}
    client.get_medications.return_value = {"resourceType": "Bundle", "entry": []}
    client.get_allergies.return_value = {"resourceType": "Bundle", "entry": []}
    client.get_vitals.return_value = {"resourceType": "Bundle", "entry": []}
    client.search_patients.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "id": "uuid-1",
                    "name": [{"family": "Doe", "given": ["John"]}],
                    "birthDate": "1980-01-15",
                    "gender": "male",
                }
            }
        ],
    }
    client.get_observations.return_value = {"resourceType": "Bundle", "entry": []}
    return client


@pytest.mark.asyncio
async def test_get_patient_summary(mock_openemr):
    set_patient_client(mock_openemr)
    result = await get_patient_summary.ainvoke({"patient_uuid": "uuid-1"})
    assert result["status"] == "success"
    assert result["data"]["patient"]["id"] == "uuid-1"


@pytest.mark.asyncio
async def test_search_patients(mock_openemr):
    set_patient_client(mock_openemr)
    result = await search_patients.ainvoke({"name": "Doe"})
    assert result["status"] == "success"
    assert result["data"]["total"] == 1
    assert result["data"]["patients"][0]["name"] == "John Doe"


# --- Medication tools ---


@pytest.fixture
def mock_drug():
    client = AsyncMock()
    client.get_rxcui.side_effect = lambda name: {
        "aspirin": "1191",
        "warfarin": "11289",
    }.get(name)
    client.check_multi_interactions.return_value = [
        {
            "severity": "high",
            "description": "Increased bleeding risk",
            "drugs": ["aspirin", "warfarin"],
        }
    ]
    return client


@pytest.mark.asyncio
async def test_get_medications(mock_openemr):
    mock_openemr.get_medications.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "medicationCodeableConcept": {"text": "Aspirin 81mg"},
                    "status": "active",
                    "intent": "order",
                }
            }
        ],
    }
    set_med_clients(mock_openemr, AsyncMock())
    result = await get_medications.ainvoke({"patient_uuid": "uuid-1"})
    assert result["status"] == "success"
    assert result["data"]["medications"][0]["medication"] == "Aspirin 81mg"


@pytest.mark.asyncio
async def test_drug_interaction_check(mock_drug):
    set_med_clients(AsyncMock(), mock_drug)
    result = await drug_interaction_check.ainvoke(
        {"drug_names": ["aspirin", "warfarin"]}
    )
    assert result["status"] == "success"
    assert len(result["data"]["interactions"]) == 1
    assert result["data"]["interactions"][0]["severity"] == "high"


# --- Lab tool ---


@pytest.mark.asyncio
async def test_get_lab_results(mock_openemr):
    mock_openemr.get_observations.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Hemoglobin A1c"},
                    "valueQuantity": {"value": 6.5, "unit": "%"},
                    "effectiveDateTime": "2026-01-15",
                    "status": "final",
                }
            }
        ],
    }
    set_labs_client(mock_openemr)
    result = await get_lab_results.ainvoke({"patient_uuid": "uuid-1"})
    assert result["status"] == "success"
    assert result["data"]["lab_results"][0]["test"] == "Hemoglobin A1c"
    assert result["data"]["lab_results"][0]["value"] == 6.5


# --- ICD-10 tool ---


@pytest.mark.asyncio
async def test_icd10_lookup():
    mock = AsyncMock()
    mock.search.return_value = [
        {"code": "E11.9", "description": "Type 2 diabetes mellitus without complications"}
    ]
    set_icd10_client(mock)
    result = await icd10_lookup.ainvoke({"query": "diabetes type 2"})
    assert result["status"] == "success"
    assert result["data"]["codes"][0]["code"] == "E11.9"


# --- PubMed tool ---


@pytest.mark.asyncio
async def test_pubmed_search():
    mock = AsyncMock()
    mock.search.return_value = [
        {
            "pmid": "12345",
            "title": "Aspirin Study",
            "authors": ["Smith"],
            "source": "JAMA",
            "pubdate": "2024",
        }
    ]
    set_pubmed_client(mock)
    result = await pubmed_search.ainvoke({"query": "aspirin cardiovascular"})
    assert result["status"] == "success"
    assert result["data"]["articles"][0]["pmid"] == "12345"


# --- Error handler ---


@pytest.mark.asyncio
async def test_error_handler_catches_exceptions():
    @tool_error_handler
    async def failing_tool():
        raise ValueError("something broke")

    result = await failing_tool()
    assert result["status"] == "error"
    assert "ValueError" in result["error"]


@pytest.mark.asyncio
async def test_error_handler_catches_timeout():
    @tool_error_handler
    async def slow_tool():
        raise TimeoutError("too slow")

    result = await slow_tool()
    assert result["status"] == "error"
    assert "timed out" in result["error"]
