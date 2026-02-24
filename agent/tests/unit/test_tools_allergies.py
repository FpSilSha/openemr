"""Unit tests for the allergies LangChain tool."""

from unittest.mock import AsyncMock

import pytest

import app.tools.allergies as allergies_module
from app.tools.allergies import get_allergies_detailed, set_client

# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_allergy_with_reaction(mock_openemr_client):
    """Standard fixture returns one Penicillin allergy with all fields correctly parsed."""
    set_client(mock_openemr_client)

    result = await get_allergies_detailed.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    allergies = result["data"]["allergies"]
    assert len(allergies) == 1
    assert result["data"]["total"] == 1

    allergy = allergies[0]
    assert allergy["substance"] == "Penicillin"
    assert allergy["type"] == "allergy"
    assert allergy["criticality"] == "high"
    assert allergy["onset"] == "2020-03-15"
    assert allergy["clinical_status"] == "active"

    assert len(allergy["reactions"]) == 1
    reaction = allergy["reactions"][0]
    assert reaction["manifestation"] == "Hives"
    assert reaction["severity"] == "severe"


@pytest.mark.asyncio
async def test_multiple_allergies_parsed():
    """A bundle with two allergy entries produces two parsed allergy dicts."""
    client = AsyncMock()
    client.get_allergies.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Penicillin"},
                    "type": "allergy",
                    "criticality": "high",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                    "onsetDateTime": "2020-03-15",
                    "reaction": [{"manifestation": [{"text": "Hives"}], "severity": "severe"}],
                }
            },
            {
                "resource": {
                    "code": {"text": "Sulfa"},
                    "type": "allergy",
                    "criticality": "low",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                    "onsetDateTime": "2019-06-01",
                    "reaction": [{"manifestation": [{"text": "Rash"}], "severity": "mild"}],
                }
            },
        ],
    }
    set_client(client)

    result = await get_allergies_detailed.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    allergies = result["data"]["allergies"]
    assert len(allergies) == 2
    assert result["data"]["total"] == 2

    substances = [a["substance"] for a in allergies]
    assert "Penicillin" in substances
    assert "Sulfa" in substances

    sulfa = next(a for a in allergies if a["substance"] == "Sulfa")
    assert sulfa["criticality"] == "low"
    assert sulfa["reactions"][0]["manifestation"] == "Rash"
    assert sulfa["reactions"][0]["severity"] == "mild"


@pytest.mark.asyncio
async def test_allergy_with_no_reactions():
    """An allergy resource with no 'reaction' key produces an empty reactions list."""
    client = AsyncMock()
    client.get_allergies.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Latex"},
                    "type": "allergy",
                    "criticality": "high",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                    "onsetDateTime": "2018-05-10",
                }
            }
        ],
    }
    set_client(client)

    result = await get_allergies_detailed.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    allergy = result["data"]["allergies"][0]
    assert allergy["substance"] == "Latex"
    assert allergy["reactions"] == []


@pytest.mark.asyncio
async def test_missing_criticality_defaults_to_empty():
    """An allergy resource without a 'criticality' field returns an empty string for criticality."""
    client = AsyncMock()
    client.get_allergies.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Aspirin"},
                    "type": "allergy",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                    "onsetDateTime": "2021-01-01",
                    "reaction": [],
                }
            }
        ],
    }
    set_client(client)

    result = await get_allergies_detailed.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    allergy = result["data"]["allergies"][0]
    assert allergy["criticality"] == ""


@pytest.mark.asyncio
async def test_missing_onset_defaults_to_empty():
    """An allergy resource without 'onsetDateTime' returns an empty string for onset."""
    client = AsyncMock()
    client.get_allergies.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Ibuprofen"},
                    "type": "allergy",
                    "criticality": "low",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                    "reaction": [],
                }
            }
        ],
    }
    set_client(client)

    result = await get_allergies_detailed.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    allergy = result["data"]["allergies"][0]
    assert allergy["onset"] == ""


@pytest.mark.asyncio
async def test_substance_falls_back_to_coding_display():
    """When code.text is absent, substance falls back to coding[0].display."""
    client = AsyncMock()
    client.get_allergies.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {
                        "coding": [{"system": "http://snomed.info/sct", "display": "Codeine"}]
                    },
                    "type": "allergy",
                    "criticality": "moderate",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                    "onsetDateTime": "2017-11-20",
                    "reaction": [],
                }
            }
        ],
    }
    set_client(client)

    result = await get_allergies_detailed.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    allergy = result["data"]["allergies"][0]
    assert allergy["substance"] == "Codeine"


@pytest.mark.asyncio
async def test_empty_bundle_returns_empty_list():
    """A bundle with an empty 'entry' list produces an empty allergies list with total=0."""
    client = AsyncMock()
    client.get_allergies.return_value = {"resourceType": "Bundle", "entry": []}
    set_client(client)

    result = await get_allergies_detailed.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    assert result["data"]["allergies"] == []
    assert result["data"]["total"] == 0


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_client_raises_runtime_error():
    """Calling the tool before set_client() returns a structured error containing 'RuntimeError'."""
    allergies_module._client = None

    result = await get_allergies_detailed.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "RuntimeError" in result["error"]
