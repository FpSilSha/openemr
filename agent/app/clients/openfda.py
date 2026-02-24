"""Drug interaction client using RxNorm (for RxCUI lookup) and NLM interaction API."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
INTERACTION_BASE = "https://rxnav.nlm.nih.gov/REST/interaction"


class DrugInteractionClient:
    """Looks up drug interactions via NLM RxNorm + Interaction APIs."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.http = httpx.AsyncClient(timeout=timeout)

    async def get_rxcui(self, drug_name: str) -> str | None:
        """Resolve a drug name to its RxNorm Concept Unique Identifier (RxCUI)."""
        resp = await self.http.get(
            f"{RXNORM_BASE}/rxcui.json",
            params={"name": drug_name},
        )
        resp.raise_for_status()
        data = resp.json()
        id_group = data.get("idGroup", {})
        rxnorm_ids = id_group.get("rxnormId")
        if rxnorm_ids:
            return rxnorm_ids[0]
        return None

    async def check_interactions(self, rxcui: str) -> list[dict[str, Any]]:
        """Get known drug interactions for a given RxCUI."""
        resp = await self.http.get(
            f"{INTERACTION_BASE}/interaction.json",
            params={"rxcui": rxcui},
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[dict[str, Any]] = []
        for group in data.get("interactionTypeGroup", []):
            for itype in group.get("interactionType", []):
                for pair in itype.get("interactionPair", []):
                    results.append({
                        "severity": pair.get("severity", "N/A"),
                        "description": pair.get("description", ""),
                        "drugs": [
                            c.get("minConceptItem", {}).get("name", "")
                            for c in pair.get("interactionConcept", [])
                        ],
                    })
        return results

    async def check_multi_interactions(
        self, rxcuis: list[str]
    ) -> list[dict[str, Any]]:
        """Check interactions between multiple drugs (by RxCUI list)."""
        if len(rxcuis) < 2:
            return []
        resp = await self.http.get(
            f"{INTERACTION_BASE}/list.json",
            params={"rxcuis": "+".join(rxcuis)},
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[dict[str, Any]] = []
        for group in data.get("fullInteractionTypeGroup", []):
            for itype in group.get("fullInteractionType", []):
                for pair in itype.get("interactionPair", []):
                    results.append({
                        "severity": pair.get("severity", "N/A"),
                        "description": pair.get("description", ""),
                        "drugs": [
                            c.get("minConceptItem", {}).get("name", "")
                            for c in pair.get("interactionConcept", [])
                        ],
                    })
        return results

    async def close(self) -> None:
        await self.http.aclose()
