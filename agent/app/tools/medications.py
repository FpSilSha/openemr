"""Medication-related LangChain tools."""

from typing import Any

from langchain_core.tools import tool

from app.clients.openemr import OpenEMRClient
from app.clients.openfda import DrugInteractionClient
from app.tools.base import tool_error_handler

_openemr_client: OpenEMRClient | None = None
_drug_client: DrugInteractionClient | None = None


def set_clients(
    openemr: OpenEMRClient, drug: DrugInteractionClient
) -> None:
    global _openemr_client, _drug_client
    _openemr_client = openemr
    _drug_client = drug


def _get_openemr() -> OpenEMRClient:
    if _openemr_client is None:
        raise RuntimeError("OpenEMR client not initialized")
    return _openemr_client


def _get_drug() -> DrugInteractionClient:
    if _drug_client is None:
        raise RuntimeError("Drug interaction client not initialized")
    return _drug_client


@tool
@tool_error_handler
async def get_medications(patient_uuid: str) -> dict[str, Any]:
    """Get all current medications for a patient from OpenEMR.

    Args:
        patient_uuid: The UUID of the patient in OpenEMR.
    """
    client = _get_openemr()
    results = await client.get_medications(patient_uuid)
    entries = results.get("entry", [])
    medications = []
    for entry in entries:
        resource = entry.get("resource", {})
        med_ref = resource.get("medicationCodeableConcept", {})
        medications.append({
            "medication": med_ref.get("text", med_ref.get("coding", [{}])[0].get("display", "")),
            "status": resource.get("status", ""),
            "intent": resource.get("intent", ""),
        })
    return {"status": "success", "data": {"medications": medications}}


@tool
@tool_error_handler
async def drug_interaction_check(drug_names: list[str]) -> dict[str, Any]:
    """Check for known drug-drug interactions between a list of medications.

    Args:
        drug_names: List of drug names to check for interactions (e.g. ["aspirin", "warfarin"]).
    """
    client = _get_drug()
    rxcuis = []
    resolved = {}
    for name in drug_names:
        rxcui = await client.get_rxcui(name)
        if rxcui:
            rxcuis.append(rxcui)
            resolved[name] = rxcui

    if len(rxcuis) < 2:
        return {
            "status": "success",
            "data": {
                "interactions": [],
                "note": "Need at least 2 resolved drugs to check interactions.",
                "resolved": resolved,
            },
        }

    interactions = await client.check_multi_interactions(rxcuis)
    return {
        "status": "success",
        "data": {
            "interactions": interactions,
            "resolved_drugs": resolved,
        },
    }
