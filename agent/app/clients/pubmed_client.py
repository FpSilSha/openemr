"""PubMed search client using NCBI E-utilities."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedClient:
    """Searches PubMed via E-utilities (esearch + esummary). Free, no key required."""

    def __init__(self, api_key: str = "", timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.http = httpx.AsyncClient(timeout=timeout)

    def _base_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    async def search(
        self, query: str, max_results: int = 5
    ) -> list[dict[str, Any]]:
        """Search PubMed and return article summaries.

        Returns list of {"pmid", "title", "authors", "source", "pubdate"} dicts.
        """
        # Step 1: esearch to get PMIDs
        search_params = {
            **self._base_params(),
            "db": "pubmed",
            "term": query,
            "retmax": str(max_results),
            "retmode": "json",
        }
        resp = await self.http.get(f"{EUTILS_BASE}/esearch.fcgi", params=search_params)
        resp.raise_for_status()
        search_data = resp.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # Step 2: esummary for article details
        summary_params = {
            **self._base_params(),
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json",
        }
        resp = await self.http.get(
            f"{EUTILS_BASE}/esummary.fcgi", params=summary_params
        )
        resp.raise_for_status()
        summary_data = resp.json()

        results: list[dict[str, Any]] = []
        result_block = summary_data.get("result", {})
        for pmid in id_list:
            article = result_block.get(pmid, {})
            if not article:
                continue
            authors = [
                a.get("name", "") for a in article.get("authors", [])[:3]
            ]
            results.append({
                "pmid": pmid,
                "title": article.get("title", ""),
                "authors": authors,
                "source": article.get("source", ""),
                "pubdate": article.get("pubdate", ""),
            })
        return results

    async def close(self) -> None:
        await self.http.aclose()
