"""PubMed search LangChain tool."""

from typing import Any

from langchain_core.tools import tool

from app.clients.pubmed_client import PubMedClient
from app.tools.base import tool_error_handler

_client: PubMedClient | None = None


def set_client(client: PubMedClient) -> None:
    global _client
    _client = client


def _get_client() -> PubMedClient:
    if _client is None:
        raise RuntimeError("PubMed client not initialized")
    return _client


@tool
@tool_error_handler
async def pubmed_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search PubMed for medical literature relevant to a clinical question.

    Args:
        query: A medical/clinical search query (e.g. "aspirin cardiovascular prevention").
        max_results: Maximum number of articles to return (default 5).
    """
    client = _get_client()
    results = await client.search(query, max_results=max_results)
    return {"status": "success", "data": {"articles": results}}
