"""OpenEMR FHIR/REST client with OAuth2 auto-registration and token management."""

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class OpenEMRClient:
    """Async client for OpenEMR FHIR R4 and REST APIs.

    On first authenticate(), auto-registers an OAuth2 client via RFC 7591
    dynamic client registration, then obtains a token via password grant.
    Automatically retries on 401 (token expiry).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._access_token: str | None = None

        # TLS verification logic
        is_https = settings.openemr_base_url.startswith("https")
        verify = settings.openemr_verify_ssl if is_https else True
        if is_https and not settings.openemr_verify_ssl:
            logger.warning(
                "TLS verification disabled — dev only, do NOT use in production"
            )
        if not is_https and not settings.openemr_base_url.startswith(
            "http://openemr:"
        ):
            logger.warning(
                "Connecting to OpenEMR over plain HTTP outside Docker network"
            )

        self.http = httpx.AsyncClient(
            timeout=settings.tool_timeout_seconds,
            verify=verify,
        )

    # --- OAuth2 ---

    async def _register_client(self) -> None:
        """Dynamic client registration (RFC 7591). No auth required."""
        url = f"{self.settings.openemr_base_url}/oauth2/default/registration"
        payload = {
            "client_name": "AgentForge",
            "redirect_uris": [f"http://localhost:{self.settings.agent_port}/callback"],
            "application_type": "private",
            "scope": "openid api:oemr api:fhir",
            "grant_types": ["password"],
            "token_endpoint_auth_method": "client_secret_post",
        }
        resp = await self.http.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        self._client_id = data["client_id"]
        self._client_secret = data["client_secret"]
        logger.info("OAuth2 client registered: %s", self._client_id)

    async def _token_request(self) -> None:
        """Password grant token request."""
        url = f"{self.settings.openemr_base_url}/oauth2/default/token"
        payload = {
            "grant_type": "password",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "username": self.settings.openemr_username,
            "password": self.settings.openemr_password,
            "scope": "openid api:oemr api:fhir",
        }
        resp = await self.http.post(
            url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        logger.info("OAuth2 token obtained")

    async def authenticate(self) -> None:
        """Register client (if needed) and obtain access token."""
        if not self._client_id:
            await self._register_client()
        await self._token_request()

    def _auth_headers(self) -> dict[str, str]:
        if not self._access_token:
            raise RuntimeError("Not authenticated — call authenticate() first")
        return {"Authorization": f"Bearer {self._access_token}"}

    # --- HTTP helpers ---

    async def _fhir_get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        """GET from the FHIR API with auto-retry on 401."""
        url = f"{self.settings.openemr_fhir_url}/{path}"
        resp = await self.http.get(url, headers=self._auth_headers(), params=params)
        if resp.status_code == 401:
            logger.info("Token expired, re-authenticating")
            await self.authenticate()
            resp = await self.http.get(url, headers=self._auth_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    async def _api_get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        """GET from the REST API with auto-retry on 401."""
        url = f"{self.settings.openemr_api_url}/{path}"
        resp = await self.http.get(url, headers=self._auth_headers(), params=params)
        if resp.status_code == 401:
            logger.info("Token expired, re-authenticating")
            await self.authenticate()
            resp = await self.http.get(url, headers=self._auth_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    # --- FHIR resource methods ---

    async def get_patient(self, patient_uuid: str) -> dict[str, Any]:
        """Fetch a single Patient resource by UUID."""
        return await self._fhir_get(f"Patient/{patient_uuid}")

    async def search_patients(
        self, name: str | None = None, **params: str
    ) -> dict[str, Any]:
        """Search patients. Accepts FHIR search parameters."""
        search_params: dict[str, str] = {}
        if name:
            search_params["name"] = name
        search_params.update(params)
        return await self._fhir_get("Patient", params=search_params)

    async def get_conditions(self, patient_uuid: str) -> dict[str, Any]:
        """Fetch Condition resources for a patient."""
        return await self._fhir_get("Condition", params={"patient": patient_uuid})

    async def get_medications(self, patient_uuid: str) -> dict[str, Any]:
        """Fetch MedicationRequest resources for a patient."""
        return await self._fhir_get(
            "MedicationRequest", params={"patient": patient_uuid}
        )

    async def get_observations(
        self, patient_uuid: str, category: str | None = None
    ) -> dict[str, Any]:
        """Fetch Observation resources (labs, vitals) for a patient."""
        params: dict[str, str] = {"patient": patient_uuid}
        if category:
            params["category"] = category
        return await self._fhir_get("Observation", params=params)

    async def get_allergies(self, patient_uuid: str) -> dict[str, Any]:
        """Fetch AllergyIntolerance resources for a patient."""
        return await self._fhir_get(
            "AllergyIntolerance", params={"patient": patient_uuid}
        )

    async def get_vitals(self, patient_uuid: str) -> dict[str, Any]:
        """Fetch vital signs (Observation category=vital-signs)."""
        return await self.get_observations(patient_uuid, category="vital-signs")

    async def close(self) -> None:
        await self.http.aclose()
