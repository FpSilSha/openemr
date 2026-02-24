"""ICD-10 code lookup using NLM Clinical Tables API."""

import logging

import httpx

logger = logging.getLogger(__name__)

ICD10_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"


class ICD10Client:
    """Searches ICD-10-CM codes via the NLM Clinical Tables API (no auth required)."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.http = httpx.AsyncClient(timeout=timeout)

    async def search(
        self, query: str, max_results: int = 10
    ) -> list[dict[str, str]]:
        """Search ICD-10-CM codes by keyword or code prefix.

        Returns list of {"code": "...", "description": "..."} dicts.
        """
        resp = await self.http.get(
            ICD10_BASE,
            params={"sf": "code,name", "terms": query, "maxList": max_results},
        )
        resp.raise_for_status()
        data = resp.json()
        # Response format: [total, codes_list, extra_info, display_strings_list]
        codes = data[1] if len(data) > 1 else []
        displays = data[3] if len(data) > 3 else []
        results: list[dict[str, str]] = []
        for i, code in enumerate(codes):
            desc = displays[i][1] if i < len(displays) and len(displays[i]) > 1 else ""
            results.append({"code": code, "description": desc})
        return results

    async def close(self) -> None:
        await self.http.aclose()
