"""Unit tests for OpenEMR client with mocked HTTP responses."""

import httpx
import pytest

from app.clients.openemr import OpenEMRClient
from app.config import Settings

REGISTRATION_RESPONSE = {
    "client_id": "test-client-id",
    "client_secret": "test-client-secret",
}

TOKEN_RESPONSE = {
    "access_token": "test-access-token",
    "token_type": "Bearer",
    "expires_in": 3600,
}

PATIENT_RESOURCE = {
    "resourceType": "Patient",
    "id": "test-uuid-123",
    "name": [{"family": "Doe", "given": ["John"]}],
}

BUNDLE_RESPONSE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 1,
    "entry": [{"resource": PATIENT_RESOURCE}],
}


@pytest.fixture
def settings():
    return Settings(
        anthropic_api_key="test",
        langchain_api_key="test",
        openemr_base_url="http://openemr:80",
        openemr_api_url="http://openemr:80/apis/default",
        openemr_fhir_url="http://openemr:80/apis/default/fhir",
    )


@pytest.fixture
def client(settings):
    return OpenEMRClient(settings)


@pytest.mark.asyncio
async def test_register_and_authenticate(client, httpx_mock):
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/registration",
        method="POST",
        json=REGISTRATION_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json=TOKEN_RESPONSE,
    )

    await client.authenticate()

    assert client._client_id == "test-client-id"
    assert client._client_secret == "test-client-secret"
    assert client._access_token == "test-access-token"


@pytest.mark.asyncio
async def test_reuses_client_id_on_reauthenticate(client, httpx_mock):
    # First auth: registration + token
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/registration",
        method="POST",
        json=REGISTRATION_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json=TOKEN_RESPONSE,
    )
    await client.authenticate()

    # Second auth: only token (no re-registration)
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json={**TOKEN_RESPONSE, "access_token": "new-token"},
    )
    await client.authenticate()

    assert client._access_token == "new-token"
    # Registration should have been called only once
    registration_requests = [
        r
        for r in httpx_mock.get_requests()
        if "registration" in str(r.url)
    ]
    assert len(registration_requests) == 1


@pytest.mark.asyncio
async def test_get_patient(client, httpx_mock):
    # Setup auth
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/registration",
        method="POST",
        json=REGISTRATION_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json=TOKEN_RESPONSE,
    )
    await client.authenticate()

    httpx_mock.add_response(
        url="http://openemr:80/apis/default/fhir/Patient/test-uuid-123",
        json=PATIENT_RESOURCE,
    )

    result = await client.get_patient("test-uuid-123")
    assert result["resourceType"] == "Patient"
    assert result["id"] == "test-uuid-123"


@pytest.mark.asyncio
async def test_search_patients(client, httpx_mock):
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/registration",
        method="POST",
        json=REGISTRATION_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json=TOKEN_RESPONSE,
    )
    await client.authenticate()

    httpx_mock.add_response(
        url=httpx.URL(
            "http://openemr:80/apis/default/fhir/Patient",
            params={"name": "Doe"},
        ),
        json=BUNDLE_RESPONSE,
    )

    result = await client.search_patients(name="Doe")
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_auto_retry_on_401(client, httpx_mock):
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/registration",
        method="POST",
        json=REGISTRATION_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json=TOKEN_RESPONSE,
    )
    await client.authenticate()

    # First request returns 401
    httpx_mock.add_response(
        url="http://openemr:80/apis/default/fhir/Patient/test-uuid-123",
        status_code=401,
    )
    # Re-auth token
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json={**TOKEN_RESPONSE, "access_token": "refreshed-token"},
    )
    # Retry succeeds
    httpx_mock.add_response(
        url="http://openemr:80/apis/default/fhir/Patient/test-uuid-123",
        json=PATIENT_RESOURCE,
    )

    result = await client.get_patient("test-uuid-123")
    assert result["resourceType"] == "Patient"
    assert client._access_token == "refreshed-token"


@pytest.mark.asyncio
async def test_get_conditions(client, httpx_mock):
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/registration",
        method="POST",
        json=REGISTRATION_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json=TOKEN_RESPONSE,
    )
    await client.authenticate()

    httpx_mock.add_response(
        url=httpx.URL(
            "http://openemr:80/apis/default/fhir/Condition",
            params={"patient": "uuid-1"},
        ),
        json=BUNDLE_RESPONSE,
    )

    result = await client.get_conditions("uuid-1")
    assert result["resourceType"] == "Bundle"


@pytest.mark.asyncio
async def test_get_medications(client, httpx_mock):
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/registration",
        method="POST",
        json=REGISTRATION_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://openemr:80/oauth2/default/token",
        method="POST",
        json=TOKEN_RESPONSE,
    )
    await client.authenticate()

    httpx_mock.add_response(
        url=httpx.URL(
            "http://openemr:80/apis/default/fhir/MedicationRequest",
            params={"patient": "uuid-1"},
        ),
        json=BUNDLE_RESPONSE,
    )

    result = await client.get_medications("uuid-1")
    assert result["resourceType"] == "Bundle"


@pytest.mark.asyncio
async def test_not_authenticated_raises(client):
    with pytest.raises(RuntimeError, match="Not authenticated"):
        await client.get_patient("any-uuid")
