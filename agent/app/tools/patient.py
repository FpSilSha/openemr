"""Patient-related LangChain tools."""

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
async def get_patient_summary(patient_uuid: str) -> dict[str, Any]:
    """Get a comprehensive summary for a patient including demographics, conditions,
    medications, allergies, and recent vitals.

    Args:
        patient_uuid: The UUID of the patient in OpenEMR.
    """
    client = _get_client()
    patient = await client.get_patient(patient_uuid)
    conditions = await client.get_conditions(patient_uuid)
    medications = await client.get_medications(patient_uuid)
    allergies = await client.get_allergies(patient_uuid)
    vitals = await client.get_vitals(patient_uuid)

    return {
        "status": "success",
        "data": {
            "patient": patient,
            "conditions": conditions,
            "medications": medications,
            "allergies": allergies,
            "vitals": vitals,
        },
    }


@tool
@tool_error_handler
async def search_patients(name: str) -> dict[str, Any]:
    """Search for patients by name in OpenEMR.

    Args:
        name: The patient name (or partial name) to search for.
    """
    client = _get_client()
    results = await client.search_patients(name=name)
    entries = results.get("entry", [])
    patients = []
    for entry in entries:
        resource = entry.get("resource", {})
        names = resource.get("name", [{}])
        display_name = ""
        if names:
            given = " ".join(names[0].get("given", []))
            family = names[0].get("family", "")
            display_name = f"{given} {family}".strip()
        patients.append({
            "uuid": resource.get("id", ""),
            "name": display_name,
            "birthDate": resource.get("birthDate", ""),
            "gender": resource.get("gender", ""),
        })
    return {"status": "success", "data": {"patients": patients, "total": len(patients)}}
