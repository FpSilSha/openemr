"""Lab results LangChain tool."""

from typing import Any

from langchain_core.tools import tool

from app.clients.openemr import OpenEMRClient
from app.tools.base import tool_error_handler

_client: OpenEMRClient | None = None


def set_client(client: OpenEMRClient) -> None:
    global _client
    _client = client


def _get_client() -> OpenEMRClient:
    if _client is None:
        raise RuntimeError("OpenEMR client not initialized")
    return _client


@tool
@tool_error_handler
async def get_lab_results(patient_uuid: str) -> dict[str, Any]:
    """Get laboratory results (Observation resources) for a patient from OpenEMR.

    Args:
        patient_uuid: The UUID of the patient in OpenEMR.
    """
    client = _get_client()
    results = await client.get_observations(patient_uuid, category="laboratory")
    entries = results.get("entry", [])
    labs = []
    for entry in entries:
        resource = entry.get("resource", {})
        code_obj = resource.get("code", {})
        value_quantity = resource.get("valueQuantity", {})
        labs.append({
            "test": code_obj.get("text", code_obj.get("coding", [{}])[0].get("display", "")),
            "value": value_quantity.get("value", resource.get("valueString", "")),
            "unit": value_quantity.get("unit", ""),
            "date": resource.get("effectiveDateTime", ""),
            "status": resource.get("status", ""),
        })
    return {"status": "success", "data": {"lab_results": labs}}
