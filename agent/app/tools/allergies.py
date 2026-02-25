"""Detailed allergy information LangChain tool."""

import re
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
async def get_allergies_detailed(patient_uuid: str) -> dict[str, Any]:
    """Get detailed allergy information for a patient including reactions,
    severity, criticality, and onset dates.

    Args:
        patient_uuid: The UUID of the patient in OpenEMR.
    """
    client = _get_client()
    results = await client.get_allergies(patient_uuid)
    entries = results.get("entry", [])
    allergies = []
    for entry in entries:
        resource = entry.get("resource", {})
        code_obj = resource.get("code", {})
        # Robust substance extraction — OpenEMR populates different fields
        # depending on whether a coded diagnosis was selected:
        #   With code: code.coding[].display  (actual drug/allergen name)
        #   Free text only: text.div  (HTML narrative from lists.title)
        # When no coded diagnosis exists OpenEMR sets code.coding to a
        # FHIR data-absent-reason with display="Unknown" — skip those.
        substance = code_obj.get("text", "")
        if not substance:
            # text.div is the most reliable source — OpenEMR always
            # populates it from lists.title regardless of coding.
            text_div = resource.get("text", {}).get("div", "")
            if text_div:
                substance = re.sub(r"<[^>]+>", "", text_div).strip()
        if not substance:
            for coding in code_obj.get("coding", []):
                if "data-absent-reason" in coding.get("system", ""):
                    continue
                substance = coding.get("display", "") or coding.get("code", "")
                if substance:
                    break
        if not substance:
            substance = resource.get("note", [{}])[0].get("text", "") if resource.get("note") else ""
        if not substance:
            substance = "Not specified"

        # Parse reactions
        reactions = []
        for reaction in resource.get("reaction", []):
            manifestations = reaction.get("manifestation", [])
            manifestation_text = ""
            if manifestations:
                m = manifestations[0]
                manifestation_text = m.get("text", "")
                if not manifestation_text:
                    for coding in m.get("coding", []):
                        manifestation_text = coding.get("display", "") or coding.get("code", "")
                        if manifestation_text:
                            break
            reactions.append({
                "manifestation": manifestation_text,
                "severity": reaction.get("severity", ""),
            })

        allergies.append({
            "substance": substance,
            "type": resource.get("type", ""),
            "criticality": resource.get("criticality", ""),
            "reactions": reactions,
            "onset": resource.get("onsetDateTime", ""),
            "clinical_status": resource.get("clinicalStatus", {})
            .get("coding", [{}])[0]
            .get("code", ""),
        })
    return {"status": "success", "data": {"allergies": allergies, "total": len(allergies)}}
