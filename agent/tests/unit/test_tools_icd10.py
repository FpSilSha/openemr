"""Unit tests for the ICD-10 lookup tool."""
from unittest.mock import AsyncMock

import pytest

from app.tools.icd10 import icd10_lookup, set_client


def make_client(return_value=None, side_effect=None):
    """Create a mock ICD10Client with a configured search method."""
    client = AsyncMock()
    if side_effect is not None:
        client.search = AsyncMock(side_effect=side_effect)
    else:
        client.search = AsyncMock(return_value=return_value if return_value is not None else [])
    return client


@pytest.mark.asyncio
async def test_lookup_by_code_prefix():
    """Lookup by code prefix returns matching codes."""
    codes = [
        {"code": "E11", "description": "Type 2 diabetes mellitus"},
        {"code": "E11.0", "description": "Type 2 diabetes mellitus with hyperosmolarity"},
        {"code": "E11.1", "description": "Type 2 diabetes mellitus with ketoacidosis"},
    ]
    client = make_client(return_value=codes)
    set_client(client)

    result = await icd10_lookup.ainvoke({"query": "E11"})

    assert result["status"] == "success"
    assert result["data"]["codes"] == codes
    assert len(result["data"]["codes"]) == 3


@pytest.mark.asyncio
async def test_lookup_by_description_keyword():
    """Lookup by description keyword returns multiple matching codes."""
    codes = [
        {"code": "E11", "description": "Type 2 diabetes mellitus"},
        {"code": "E11.65", "description": "Type 2 diabetes mellitus with hyperglycemia"},
        {"code": "E11.9", "description": "Type 2 diabetes mellitus without complications"},
        {
            "code": "Z86.39",
            "description": (
                "Personal history of other endocrine,"
                " nutritional and metabolic diseases"
            ),
        },
    ]
    client = make_client(return_value=codes)
    set_client(client)

    result = await icd10_lookup.ainvoke({"query": "diabetes type 2"})

    assert result["status"] == "success"
    assert len(result["data"]["codes"]) == 4
    descriptions = [c["description"] for c in result["data"]["codes"]]
    assert any("diabetes" in d.lower() for d in descriptions)


@pytest.mark.asyncio
async def test_validate_real_code():
    """Searching for a real code returns a result containing that code."""
    codes = [
        {"code": "J06.9", "description": "Acute upper respiratory infection, unspecified"},
    ]
    client = make_client(return_value=codes)
    set_client(client)

    result = await icd10_lookup.ainvoke({"query": "J06.9"})

    assert result["status"] == "success"
    returned_codes = [c["code"] for c in result["data"]["codes"]]
    assert "J06.9" in returned_codes


@pytest.mark.asyncio
async def test_validate_fake_code_returns_empty():
    """Searching for a non-existent code returns an empty codes list."""
    client = make_client(return_value=[])
    set_client(client)

    result = await icd10_lookup.ainvoke({"query": "ZZZ99.99"})

    assert result["status"] == "success"
    assert result["data"]["codes"] == []


@pytest.mark.asyncio
async def test_many_results_passed_through():
    """All results are passed through when search returns many codes."""
    codes = [{"code": f"A{i:02d}.{i}", "description": f"Disease {i}"} for i in range(50)]
    client = make_client(return_value=codes)
    set_client(client)

    result = await icd10_lookup.ainvoke({"query": "disease"})

    assert result["status"] == "success"
    assert len(result["data"]["codes"]) == 50
    assert result["data"]["codes"] == codes


@pytest.mark.asyncio
async def test_empty_results_returns_empty_codes_list():
    """When search returns an empty list, codes is an empty list."""
    client = make_client(return_value=[])
    set_client(client)

    result = await icd10_lookup.ainvoke({"query": "nonexistent condition xyz"})

    assert result["status"] == "success"
    assert result["data"]["codes"] == []


@pytest.mark.asyncio
async def test_client_exception_returns_structured_error():
    """When the client raises an exception, a structured error response is returned."""
    client = make_client(side_effect=Exception("ICD-10 service unavailable"))
    set_client(client)

    result = await icd10_lookup.ainvoke({"query": "diabetes"})

    assert result["status"] == "error"
    assert "error" in result
    assert "ICD-10 service unavailable" in result["error"]


@pytest.mark.asyncio
async def test_query_passed_correctly_to_client():
    """The query string is forwarded unchanged to client.search."""
    client = make_client(return_value=[])
    set_client(client)

    query = "heart failure with reduced ejection fraction"
    await icd10_lookup.ainvoke({"query": query})

    client.search.assert_awaited_once_with(query)
