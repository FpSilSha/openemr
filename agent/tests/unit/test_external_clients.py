"""Unit tests for external API clients with mocked HTTP responses."""

import httpx
import pytest

from app.clients.icd10_client import ICD10Client
from app.clients.openfda import DrugInteractionClient
from app.clients.pubmed_client import PubMedClient

# --- DrugInteractionClient ---


@pytest.fixture
def drug_client():
    return DrugInteractionClient()


@pytest.mark.asyncio
async def test_get_rxcui(drug_client, httpx_mock):
    httpx_mock.add_response(
        url=httpx.URL(
            "https://rxnav.nlm.nih.gov/REST/rxcui.json",
            params={"name": "aspirin", "search": "0"},
        ),
        json={"idGroup": {"rxnormId": ["1191"]}},
    )
    rxcui = await drug_client.get_rxcui("aspirin")
    assert rxcui == "1191"


@pytest.mark.asyncio
async def test_get_rxcui_not_found(drug_client, httpx_mock):
    httpx_mock.add_response(
        url=httpx.URL(
            "https://rxnav.nlm.nih.gov/REST/rxcui.json",
            params={"name": "fakemed", "search": "0"},
        ),
        json={"idGroup": {"name": "fakemed"}},
    )
    rxcui = await drug_client.get_rxcui("fakemed")
    assert rxcui is None


@pytest.mark.asyncio
async def test_check_interactions(drug_client, httpx_mock):
    httpx_mock.add_response(
        url="https://rxnav.nlm.nih.gov/REST/interaction/interaction.json?rxcui=1191",
        json={
            "interactionTypeGroup": [
                {
                    "interactionType": [
                        {
                            "interactionPair": [
                                {
                                    "severity": "high",
                                    "description": "Increased bleeding risk",
                                    "interactionConcept": [
                                        {"minConceptItem": {"name": "aspirin"}},
                                        {"minConceptItem": {"name": "warfarin"}},
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        },
    )
    results = await drug_client.check_interactions("1191")
    assert len(results) == 1
    assert results[0]["severity"] == "high"
    assert "aspirin" in results[0]["drugs"]
    assert "warfarin" in results[0]["drugs"]


@pytest.mark.asyncio
async def test_check_multi_interactions_too_few(drug_client):
    results = await drug_client.check_multi_interactions(["1191"])
    assert results == []


@pytest.mark.asyncio
async def test_check_multi_interactions(drug_client, httpx_mock):
    httpx_mock.add_response(
        url=httpx.URL(
            "https://rxnav.nlm.nih.gov/REST/interaction/list.json",
            params={"rxcuis": "1191+2670"},
        ),
        json={
            "fullInteractionTypeGroup": [
                {
                    "fullInteractionType": [
                        {
                            "interactionPair": [
                                {
                                    "severity": "moderate",
                                    "description": "May reduce effect",
                                    "interactionConcept": [
                                        {"minConceptItem": {"name": "aspirin"}},
                                        {"minConceptItem": {"name": "ibuprofen"}},
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        },
    )
    results = await drug_client.check_multi_interactions(["1191", "2670"])
    assert len(results) == 1
    assert results[0]["severity"] == "moderate"


# --- ICD10Client ---


@pytest.fixture
def icd10_client():
    return ICD10Client()


@pytest.mark.asyncio
async def test_icd10_search(icd10_client, httpx_mock):
    httpx_mock.add_response(
        json=[
            2,
            ["E11.9", "E11.65"],
            {},
            [
                ["E11.9", "Type 2 diabetes mellitus without complications"],
                ["E11.65", "Type 2 diabetes mellitus with hyperglycemia"],
            ],
        ]
    )
    results = await icd10_client.search("diabetes type 2")
    assert len(results) == 2
    assert results[0]["code"] == "E11.9"
    assert "diabetes" in results[0]["description"].lower()


@pytest.mark.asyncio
async def test_icd10_search_empty(icd10_client, httpx_mock):
    httpx_mock.add_response(json=[0, [], {}, []])
    results = await icd10_client.search("xyznonexistent")
    assert results == []


# --- PubMedClient ---


@pytest.fixture
def pubmed_client():
    return PubMedClient()


@pytest.mark.asyncio
async def test_pubmed_search(pubmed_client, httpx_mock):
    # esearch response
    httpx_mock.add_response(
        json={"esearchresult": {"idlist": ["12345678"]}},
    )
    # esummary response
    httpx_mock.add_response(
        json={
            "result": {
                "uids": ["12345678"],
                "12345678": {
                    "title": "Aspirin for cardiovascular prevention",
                    "authors": [
                        {"name": "Smith J"},
                        {"name": "Doe A"},
                    ],
                    "source": "JAMA",
                    "pubdate": "2024 Jan",
                },
            }
        },
    )
    results = await pubmed_client.search("aspirin cardiovascular")
    assert len(results) == 1
    assert results[0]["pmid"] == "12345678"
    assert "aspirin" in results[0]["title"].lower()
    assert results[0]["source"] == "JAMA"


@pytest.mark.asyncio
async def test_pubmed_search_empty(pubmed_client, httpx_mock):
    httpx_mock.add_response(
        json={"esearchresult": {"idlist": []}},
    )
    results = await pubmed_client.search("xyznonexistent12345")
    assert results == []
