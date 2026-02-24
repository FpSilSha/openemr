"""Vital signs LangChain tool."""

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
        raise RuntimeError("OpenEMR client not initialized — call set_client() first")
    return _client


@tool
@tool_error_handler
async def get_vitals(patient_uuid: str) -> dict[str, Any]:
    """Get the most recent vital signs for a patient including blood pressure,
    heart rate, temperature, weight, and BMI.

    Args:
        patient_uuid: The UUID of the patient in OpenEMR.
    """
    client = _get_client()
    results = await client.get_vitals(patient_uuid)
    entries = results.get("entry", [])
    vitals = []
    for entry in entries:
        resource = entry.get("resource", {})
        code_obj = resource.get("code", {})
        value_quantity = resource.get("valueQuantity", {})
        vitals.append({
            "type": code_obj.get("text", code_obj.get("coding", [{}])[0].get("display", "")),
            "value": value_quantity.get("value", resource.get("valueString", "")),
            "unit": value_quantity.get("unit", ""),
            "date": resource.get("effectiveDateTime", ""),
        })
    return {"status": "success", "data": {"vitals": vitals, "total": len(vitals)}}
