"""Appointment-related LangChain tool."""

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
async def get_appointments(patient_uuid: str, date_range: str = "upcoming") -> dict[str, Any]:
    """Get appointments for a patient from OpenEMR.

    Args:
        patient_uuid: The UUID of the patient in OpenEMR.
        date_range: Filter for appointments — "upcoming" (default) or "all".
    """
    client = _get_client()
    results = await client.get_appointments(patient_uuid)
    entries = results.get("entry", [])
    appointments = []
    for entry in entries:
        resource = entry.get("resource", {})
        # Parse participant for provider name
        provider = ""
        for participant in resource.get("participant", []):
            actor = participant.get("actor", {})
            if actor.get("reference", "").startswith("Practitioner"):
                provider = actor.get("display", "")
                break

        appointments.append({
            "date": resource.get("start", "").split("T")[0] if resource.get("start") else "",
            "time": resource.get("start", "").split("T")[1]
            if "T" in resource.get("start", "")
            else "",
            "provider": provider,
            "reason": resource.get("reasonCode", [{}])[0].get("text", "")
            if resource.get("reasonCode")
            else "",
            "status": resource.get("status", ""),
        })
    return {"status": "success", "data": {"appointments": appointments, "total": len(appointments)}}
