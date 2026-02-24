"""ICD-10 lookup LangChain tool."""

from typing import Any

from langchain_core.tools import tool

from app.clients.icd10_client import ICD10Client
from app.tools.base import tool_error_handler

_client: ICD10Client | None = None


def set_client(client: ICD10Client) -> None:
    global _client
    _client = client


def _get_client() -> ICD10Client:
    if _client is None:
        raise RuntimeError("ICD-10 client not initialized")
    return _client


@tool
@tool_error_handler
async def icd10_lookup(query: str) -> dict[str, Any]:
    """Look up ICD-10-CM diagnosis codes by keyword or code prefix.

    Args:
        query: A search term like "diabetes type 2" or a code prefix like "E11".
    """
    client = _get_client()
    results = await client.search(query)
    return {"status": "success", "data": {"codes": results}}
