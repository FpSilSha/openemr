"""Unit tests for 4-tier drug name resolution with ingredient normalization."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.clients.openfda import DrugInteractionClient, _deduplicate_ingredients

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client_with_tiers(
    exact: dict | None = None,
    approximate: list | None = None,
    drugs: list | None = None,
    ingredient: dict | None = None,
) -> DrugInteractionClient:
    """Build a DrugInteractionClient with mocked tier methods."""
    client = DrugInteractionClient.__new__(DrugInteractionClient)
    client.http = AsyncMock()

    client.get_rxcui = AsyncMock(return_value=exact)
    client.get_approximate_match = AsyncMock(return_value=approximate or [])
    client.get_drugs_by_name = AsyncMock(return_value=drugs or [])
    client.get_ingredient_rxcui = AsyncMock(return_value=ingredient or {})

    return client


# ---------------------------------------------------------------------------
# Tier 1: Exact match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier1_exact_match():
    """Exact match resolves with tier 1 and confidence 1.0."""
    client = _make_client_with_tiers(
        exact="1191",
        ingredient={"rxcui": "1191", "name": "aspirin"},
    )

    result = await client.resolve_drug_name("aspirin")

    assert result["resolution_tier"] == 1
    assert result["confidence"] == 1.0
    assert result["rxcui"] == "1191"
    assert result["name"] == "aspirin"
    assert result["ambiguous"] is False


# ---------------------------------------------------------------------------
# Tier 2: Approximate match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier2_single_ingredient():
    """Approximate match with single ingredient → tier 2, confidence 0.85."""
    client = _make_client_with_tiers(
        exact=None,
        approximate=[
            {"rxcui": "100", "name": "Aspirin 81mg", "score": 90},
            {"rxcui": "101", "name": "Aspirin 325mg", "score": 85},
        ],
        ingredient={"rxcui": "1191", "name": "aspirin"},
    )

    result = await client.resolve_drug_name("Aspirin 81mg")

    assert result["resolution_tier"] == 2
    assert result["confidence"] == 0.85
    assert result["rxcui"] == "1191"
    assert result["ambiguous"] is False
    assert len(result["candidates"]) == 2


@pytest.mark.asyncio
async def test_tier2_ambiguous_multiple_ingredients():
    """Approximate match with different ingredients → ambiguous, confidence 0.4."""
    client = DrugInteractionClient.__new__(DrugInteractionClient)
    client.http = AsyncMock()
    client.get_rxcui = AsyncMock(return_value=None)
    client.get_approximate_match = AsyncMock(
        return_value=[
            {"rxcui": "100", "name": "Drug A", "score": 90},
            {"rxcui": "200", "name": "Drug B", "score": 85},
        ]
    )
    client.get_drugs_by_name = AsyncMock(return_value=[])

    # Return different ingredients for each candidate
    call_count = 0

    async def mock_ingredient(rxcui):
        nonlocal call_count
        call_count += 1
        if rxcui == "100":
            return {"rxcui": "1000", "name": "Ingredient A"}
        return {"rxcui": "2000", "name": "Ingredient B"}

    client.get_ingredient_rxcui = mock_ingredient

    result = await client.resolve_drug_name("ambiguous drug")

    assert result["resolution_tier"] == 2
    assert result["confidence"] == 0.4
    assert result["ambiguous"] is True


# ---------------------------------------------------------------------------
# Tier 3: Brand/synonym search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier3_brand_name():
    """Brand name resolves via drugs.json → tier 3, confidence 0.6."""
    client = _make_client_with_tiers(
        exact=None,
        approximate=[],
        drugs=[{"rxcui": "5000", "name": "Tylenol Extra Strength"}],
        ingredient={"rxcui": "161", "name": "acetaminophen"},
    )

    result = await client.resolve_drug_name("Tylenol")

    assert result["resolution_tier"] == 3
    assert result["confidence"] == 0.6
    assert result["rxcui"] == "161"
    assert result["name"] == "acetaminophen"


# ---------------------------------------------------------------------------
# Tier 4: Unresolved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier4_unresolvable():
    """Completely unresolvable drug → tier 4, confidence 0.0."""
    client = _make_client_with_tiers(
        exact=None,
        approximate=[],
        drugs=[],
    )

    result = await client.resolve_drug_name("xyzfakedrug123")

    assert result["resolution_tier"] == 4
    assert result["confidence"] == 0.0
    assert result["rxcui"] is None
    assert result["original_name"] == "xyzfakedrug123"


# ---------------------------------------------------------------------------
# Ingredient normalization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingredient_normalization():
    """Different strengths of same drug normalize to same ingredient."""
    client = _make_client_with_tiers(
        exact="100",
        ingredient={"rxcui": "1191", "name": "aspirin"},
    )

    result1 = await client.resolve_drug_name("Aspirin 81mg")
    # Reset mock to return a different exact match but same ingredient
    client.get_rxcui = AsyncMock(return_value="200")
    result2 = await client.resolve_drug_name("Aspirin 325mg")

    assert result1["rxcui"] == result2["rxcui"] == "1191"
    assert result1["name"] == result2["name"] == "aspirin"


# ---------------------------------------------------------------------------
# check_interactions_by_names integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_interactions_all_resolved():
    """All drugs resolved → check_complete: true, no warning."""
    client = _make_client_with_tiers(
        exact="1191",
        ingredient={"rxcui": "1191", "name": "aspirin"},
    )
    client.check_multi_interactions = AsyncMock(return_value=[
        {"severity": "high", "description": "Bleeding risk", "drugs": ["aspirin", "warfarin"]},
    ])

    # Mock resolve_drug_name to return resolved for each
    async def mock_resolve(name):
        return {
            "rxcui": {"aspirin": "1191", "warfarin": "11289"}[name],
            "name": name,
            "resolution_tier": 1,
            "confidence": 1.0,
            "candidates": [],
            "ambiguous": False,
            "original_name": name,
        }

    client.resolve_drug_name = mock_resolve

    result = await client.check_interactions_by_names(["aspirin", "warfarin"])

    assert result["check_complete"] is True
    assert result["warning"] is None
    assert len(result["interactions"]) == 1
    assert result["unresolved"] == []


@pytest.mark.asyncio
async def test_check_interactions_unresolved_drug_warns():
    """Unresolved drug → check_complete: false, warning present."""
    client = _make_client_with_tiers()
    client.check_multi_interactions = AsyncMock(return_value=[])

    async def mock_resolve(name):
        if name == "aspirin":
            return {
                "rxcui": "1191",
                "name": "aspirin",
                "resolution_tier": 1,
                "confidence": 1.0,
                "candidates": [],
                "ambiguous": False,
                "original_name": name,
            }
        return {
            "rxcui": None,
            "name": name,
            "resolution_tier": 4,
            "confidence": 0.0,
            "candidates": [],
            "ambiguous": False,
            "original_name": name,
        }

    client.resolve_drug_name = mock_resolve

    result = await client.check_interactions_by_names(["aspirin", "unknowndrug"])

    assert result["check_complete"] is False
    assert result["warning"] is not None
    assert "unknowndrug" in result["warning"]
    assert result["unresolved"] == ["unknowndrug"]


@pytest.mark.asyncio
async def test_check_interactions_mixed_resolved_partial():
    """Mix of resolved and unresolved → partial results + warning."""
    client = _make_client_with_tiers()
    client.check_multi_interactions = AsyncMock(return_value=[])

    resolve_map = {
        "aspirin": {"rxcui": "1191", "resolution_tier": 1, "confidence": 1.0},
        "warfarin": {"rxcui": "11289", "resolution_tier": 1, "confidence": 1.0},
        "fakedrug": {"rxcui": None, "resolution_tier": 4, "confidence": 0.0},
    }

    async def mock_resolve(name):
        r = resolve_map.get(name, {"rxcui": None, "resolution_tier": 4, "confidence": 0.0})
        return {
            **r,
            "name": name,
            "candidates": [],
            "ambiguous": False,
            "original_name": name,
        }

    client.resolve_drug_name = mock_resolve

    result = await client.check_interactions_by_names(
        ["aspirin", "warfarin", "fakedrug"]
    )

    assert result["check_complete"] is False
    assert "fakedrug" in result["unresolved"]
    # Still called check_multi with 2 resolved drugs
    client.check_multi_interactions.assert_called_once_with(["1191", "11289"])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier1_api_error_falls_through():
    """API error in tier 1 gracefully falls to tier 2+."""
    client = DrugInteractionClient.__new__(DrugInteractionClient)
    client.http = AsyncMock()
    client.get_rxcui = AsyncMock(side_effect=ConnectionError("API down"))
    client.get_approximate_match = AsyncMock(return_value=[])
    client.get_drugs_by_name = AsyncMock(return_value=[])
    client.get_ingredient_rxcui = AsyncMock(return_value={})

    result = await client.resolve_drug_name("aspirin")

    # Should fall through to tier 4 since all tiers fail
    assert result["resolution_tier"] == 4
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# _deduplicate_ingredients helper
# ---------------------------------------------------------------------------


def test_deduplicate_ingredients_removes_duplicates():
    """Duplicate RxCUIs are collapsed to a single entry."""
    ingredients = [
        {"rxcui": "1191", "name": "aspirin"},
        {"rxcui": "1191", "name": "aspirin"},
        {"rxcui": "6809", "name": "metformin"},
    ]
    result = _deduplicate_ingredients(ingredients)
    assert len(result) == 2
    rxcuis = [r["rxcui"] for r in result]
    assert "1191" in rxcuis
    assert "6809" in rxcuis


def test_deduplicate_ingredients_empty_list():
    """Empty list returns empty list."""
    assert _deduplicate_ingredients([]) == []
