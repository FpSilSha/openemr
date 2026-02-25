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

    # ------------------------------------------------------------------
    # Core RxNorm API methods
    # ------------------------------------------------------------------

    async def get_rxcui(self, drug_name: str) -> str | None:
        """Resolve a drug name to its RxNorm Concept Unique Identifier (RxCUI).

        Uses exact match (search=0). Returns the first RxCUI or None.
        """
        resp = await self.http.get(
            f"{RXNORM_BASE}/rxcui.json",
            params={"name": drug_name, "search": 0},
        )
        resp.raise_for_status()
        data = resp.json()
        id_group = data.get("idGroup", {})
        rxnorm_ids = id_group.get("rxnormId")
        if rxnorm_ids:
            result: str = rxnorm_ids[0]
            return result
        return None

    async def get_approximate_match(self, term: str) -> list[dict[str, Any]]:
        """Find approximate RxNorm matches for a drug term.

        Returns a list of candidate dicts with 'rxcui', 'name', 'score'.
        """
        resp = await self.http.get(
            f"{RXNORM_BASE}/approximateTerm.json",
            params={"term": term, "maxEntries": 5},
        )
        resp.raise_for_status()
        data = resp.json()
        candidates: list[dict[str, Any]] = []
        group = data.get("approximateGroup", {})
        for item in group.get("candidate", []):
            candidates.append({
                "rxcui": item.get("rxcui", ""),
                "name": item.get("name", ""),
                "score": int(item.get("score", 0)),
            })
        return candidates

    async def get_ingredient_rxcui(self, rxcui: str) -> dict[str, Any]:
        """Normalize an RxCUI to its ingredient-level concept.

        Uses /rxcui/{rxcui}/related.json?tty=IN to find the base ingredient.
        Returns {'rxcui': str, 'name': str} or empty dict if not found.
        """
        resp = await self.http.get(
            f"{RXNORM_BASE}/rxcui/{rxcui}/related.json",
            params={"tty": "IN"},
        )
        resp.raise_for_status()
        data = resp.json()
        for group in data.get("relatedGroup", {}).get("conceptGroup", []):
            props = group.get("conceptProperties", [])
            if props:
                return {
                    "rxcui": props[0].get("rxcui", ""),
                    "name": props[0].get("name", ""),
                }
        return {}

    async def get_drugs_by_name(self, name: str) -> list[dict[str, Any]]:
        """Search for drugs by brand/synonym name.

        Uses /drugs.json to find matching drug concepts.
        Returns a list of dicts with 'rxcui' and 'name'.
        """
        resp = await self.http.get(
            f"{RXNORM_BASE}/drugs.json",
            params={"name": name},
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[dict[str, Any]] = []
        for group in data.get("drugGroup", {}).get("conceptGroup", []):
            for prop in group.get("conceptProperties", []):
                results.append({
                    "rxcui": prop.get("rxcui", ""),
                    "name": prop.get("name", ""),
                })
        return results

    # ------------------------------------------------------------------
    # 4-tier drug name resolution
    # ------------------------------------------------------------------

    async def resolve_drug_name(self, drug_name: str) -> dict[str, Any]:
        """Resolve a drug name to an RxCUI using 4-tier fallback strategy.

        Returns a dict with:
            rxcui: str | None
            name: str  (resolved name)
            resolution_tier: int (1-4)
            confidence: float (0.0-1.0)
            candidates: list  (for ambiguous matches)
            ambiguous: bool
            original_name: str
        """
        base = {
            "original_name": drug_name,
            "candidates": [],
            "ambiguous": False,
        }

        # Tier 1: Exact match
        try:
            rxcui = await self.get_rxcui(drug_name)
            if rxcui:
                ingredient = await self._safe_get_ingredient(rxcui)
                return {
                    **base,
                    "rxcui": ingredient.get("rxcui", rxcui),
                    "name": ingredient.get("name", drug_name),
                    "resolution_tier": 1,
                    "confidence": 1.0,
                }
        except Exception:
            logger.debug("Tier 1 failed for %s, trying tier 2", drug_name)

        # Tier 2: Approximate match
        try:
            candidates = await self.get_approximate_match(drug_name)
            if candidates:
                # Normalize all to ingredient level
                ingredients = await self._resolve_candidates_to_ingredients(
                    candidates
                )
                unique = _deduplicate_ingredients(ingredients)

                if len(unique) == 1:
                    ing = unique[0]
                    return {
                        **base,
                        "rxcui": ing["rxcui"],
                        "name": ing["name"],
                        "resolution_tier": 2,
                        "confidence": 0.85,
                        "candidates": candidates,
                    }
                elif len(unique) > 1:
                    # Ambiguous — multiple different ingredients
                    return {
                        **base,
                        "rxcui": unique[0]["rxcui"],
                        "name": unique[0]["name"],
                        "resolution_tier": 2,
                        "confidence": 0.4,
                        "candidates": candidates,
                        "ambiguous": True,
                    }
        except Exception:
            logger.debug("Tier 2 failed for %s, trying tier 3", drug_name)

        # Tier 3: Brand/synonym search
        try:
            drugs = await self.get_drugs_by_name(drug_name)
            if drugs:
                ingredient = await self._safe_get_ingredient(
                    drugs[0]["rxcui"]
                )
                return {
                    **base,
                    "rxcui": ingredient.get("rxcui", drugs[0]["rxcui"]),
                    "name": ingredient.get("name", drugs[0]["name"]),
                    "resolution_tier": 3,
                    "confidence": 0.6,
                    "candidates": drugs[:3],
                }
        except Exception:
            logger.debug("Tier 3 failed for %s, marking unresolved", drug_name)

        # Tier 4: Unresolved
        return {
            **base,
            "rxcui": None,
            "name": drug_name,
            "resolution_tier": 4,
            "confidence": 0.0,
        }

    async def _safe_get_ingredient(self, rxcui: str) -> dict[str, Any]:
        """Get ingredient RxCUI, returning empty dict on failure."""
        try:
            return await self.get_ingredient_rxcui(rxcui)
        except Exception:
            return {}

    async def _resolve_candidates_to_ingredients(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize a list of candidates to their ingredient-level RxCUIs."""
        ingredients = []
        for c in candidates[:5]:  # Limit API calls
            ing = await self._safe_get_ingredient(c["rxcui"])
            if ing:
                ingredients.append(ing)
        return ingredients

    # ------------------------------------------------------------------
    # Interaction checking
    # ------------------------------------------------------------------

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

    async def check_interactions_by_names(
        self, drug_names: list[str]
    ) -> dict[str, Any]:
        """Resolve drug names via tiered strategy and check interactions.

        Returns a dict with:
            interactions: list[dict]
            resolutions: dict[str, dict]  (per-drug resolution metadata)
            unresolved: list[str]
            check_complete: bool  (False if any drug unresolved)
            warning: str | None
        """
        resolutions: dict[str, dict[str, Any]] = {}
        rxcuis: list[str] = []
        unresolved: list[str] = []

        for name in drug_names:
            resolution = await self.resolve_drug_name(name)
            resolutions[name] = resolution
            if resolution["rxcui"]:
                rxcuis.append(resolution["rxcui"])
            else:
                unresolved.append(name)

        # Check interactions with resolved drugs
        interactions: list[dict[str, Any]] = []
        if len(rxcuis) >= 2:
            interactions = await self.check_multi_interactions(rxcuis)

        check_complete = len(unresolved) == 0
        warning = None
        if unresolved:
            warning = (
                f"WARNING: Could not resolve the following drug(s) to RxNorm "
                f"concepts: {', '.join(unresolved)}. Interaction check is "
                f"INCOMPLETE — dangerous interactions may be missed. Verify "
                f"these medications manually."
            )

        return {
            "interactions": interactions,
            "resolutions": resolutions,
            "unresolved": unresolved,
            "check_complete": check_complete,
            "warning": warning,
        }

    async def close(self) -> None:
        await self.http.aclose()


def _deduplicate_ingredients(
    ingredients: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicate ingredients by RxCUI."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for ing in ingredients:
        rxcui = ing.get("rxcui", "")
        if rxcui and rxcui not in seen:
            seen.add(rxcui)
            unique.append(ing)
    return unique
