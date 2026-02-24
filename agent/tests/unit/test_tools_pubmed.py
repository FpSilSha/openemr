"""Unit tests for the PubMed search LangChain tool (agent/app/tools/pubmed.py)."""

from unittest.mock import AsyncMock

import pytest

from app.tools.pubmed import pubmed_search, set_client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_article(
    pmid: str = "12345678",
    title: str = "A clinical study",
    authors: list[str] | None = None,
    source: str = "NEJM",
    pubdate: str = "2025",
) -> dict:
    return {
        "pmid": pmid,
        "title": title,
        "authors": authors if authors is not None else ["Smith J", "Jones A"],
        "source": source,
        "pubdate": pubdate,
    }


# ---------------------------------------------------------------------------
# Search with multiple results — all fields present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_with_multiple_results_all_fields_present():
    """Multiple articles are returned and every expected field is present."""
    articles = [
        _make_article(
            pmid="11111111", title="Diabetes management",
            authors=["Brown K"], source="Lancet", pubdate="2024",
        ),
        _make_article(
            pmid="22222222", title="Insulin therapy review",
            authors=["White L", "Green M"], source="JAMA", pubdate="2023",
        ),
        _make_article(
            pmid="33333333", title="HbA1c targets",
            authors=["Black R"], source="BMJ", pubdate="2022",
        ),
    ]
    client = AsyncMock()
    client.search.return_value = articles
    set_client(client)

    result = await pubmed_search.ainvoke({"query": "diabetes treatment"})

    assert result["status"] == "success"
    returned_articles = result["data"]["articles"]
    assert len(returned_articles) == 3

    for article in returned_articles:
        assert "pmid" in article
        assert "title" in article
        assert "authors" in article
        assert "source" in article
        assert "pubdate" in article

    pmids = [a["pmid"] for a in returned_articles]
    assert "11111111" in pmids
    assert "22222222" in pmids
    assert "33333333" in pmids


# ---------------------------------------------------------------------------
# Search with no results — empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_with_no_results_returns_empty_articles():
    """An empty result from the client is returned as an empty articles list."""
    client = AsyncMock()
    client.search.return_value = []
    set_client(client)

    result = await pubmed_search.ainvoke({"query": "nonexistent disease xyzzy"})

    assert result["status"] == "success"
    assert result["data"]["articles"] == []


# ---------------------------------------------------------------------------
# Single result — verify all fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_result_all_fields_correct():
    """A single-article response contains all required fields with correct values."""
    article = _make_article(
        pmid="99887766",
        title="Hypertension guidelines 2025",
        authors=["Patel S", "Kumar A", "Lee C"],
        source="Circulation",
        pubdate="2025",
    )
    client = AsyncMock()
    client.search.return_value = [article]
    set_client(client)

    result = await pubmed_search.ainvoke({"query": "hypertension guidelines"})

    assert result["status"] == "success"
    articles = result["data"]["articles"]
    assert len(articles) == 1

    a = articles[0]
    assert a["pmid"] == "99887766"
    assert a["title"] == "Hypertension guidelines 2025"
    assert a["authors"] == ["Patel S", "Kumar A", "Lee C"]
    assert a["source"] == "Circulation"
    assert a["pubdate"] == "2025"


# ---------------------------------------------------------------------------
# Custom max_results — verify it's passed through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_max_results_passed_to_client():
    """A custom max_results value is forwarded to client.search as a keyword argument."""
    client = AsyncMock()
    client.search.return_value = [_make_article()]
    set_client(client)

    await pubmed_search.ainvoke({"query": "cancer immunotherapy", "max_results": 3})

    client.search.assert_awaited_once_with("cancer immunotherapy", max_results=3)


# ---------------------------------------------------------------------------
# Default max_results — verify default 5 is passed through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_max_results_is_five():
    """When max_results is not provided, client.search is called with the default of 5."""
    client = AsyncMock()
    client.search.return_value = []
    set_client(client)

    await pubmed_search.ainvoke({"query": "atrial fibrillation"})

    client.search.assert_awaited_once_with("atrial fibrillation", max_results=5)


# ---------------------------------------------------------------------------
# Client raises a generic exception — structured error returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_exception_returns_structured_error():
    """When client.search raises a generic exception, a structured error dict is returned."""
    client = AsyncMock()
    client.search.side_effect = ConnectionError("PubMed API unreachable")
    set_client(client)

    result = await pubmed_search.ainvoke({"query": "stroke prevention"})

    assert result["status"] == "error"
    assert "pubmed_search" in result["error"]
    assert "ConnectionError" in result["error"]
    assert "PubMed API unreachable" in result["error"]


# ---------------------------------------------------------------------------
# Client raises TimeoutError — structured timeout error returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_timeout_returns_structured_timeout_error():
    """When client.search raises TimeoutError, a structured timeout error is returned."""
    client = AsyncMock()
    client.search.side_effect = TimeoutError()
    set_client(client)

    result = await pubmed_search.ainvoke({"query": "heart failure management"})

    assert result["status"] == "error"
    assert "timed out" in result["error"].lower()
    assert "pubmed_search" in result["error"]


# ---------------------------------------------------------------------------
# Articles with empty/missing fields — graceful handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_articles_with_empty_and_missing_fields_handled_gracefully():
    """Articles with empty authors list and missing optional fields do not cause errors."""
    articles = [
        {
            "pmid": "55555555",
            "title": "Anonymous study",
            "authors": [],
            "source": "",
            "pubdate": "",
        },
        {
            "pmid": "66666666",
            "title": "",
            "authors": ["Solo Author"],
            "source": "Nature Medicine",
            "pubdate": "2026",
        },
    ]
    client = AsyncMock()
    client.search.return_value = articles
    set_client(client)

    result = await pubmed_search.ainvoke({"query": "rare disease"})

    assert result["status"] == "success"
    returned = result["data"]["articles"]
    assert len(returned) == 2

    # First article — empty authors and source/pubdate
    first = next(a for a in returned if a["pmid"] == "55555555")
    assert first["authors"] == []
    assert first["source"] == ""
    assert first["title"] == "Anonymous study"

    # Second article — empty title
    second = next(a for a in returned if a["pmid"] == "66666666")
    assert second["title"] == ""
    assert second["authors"] == ["Solo Author"]
