"""Unit tests for OpenEMR client with mocked HTTP responses."""

from unittest.mock import AsyncMock

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


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://test"),
    )


def _make_client() -> OpenEMRClient:
    """Create a client with empty credentials and a mocked httpx transport."""
    settings = Settings(
        anthropic_api_key="test",
        langchain_api_key="test",
        openemr_base_url="http://openemr:80",
        openemr_api_url="http://openemr:80/apis/default",
        openemr_fhir_url="http://openemr:80/apis/default/fhir",
    )
    c = OpenEMRClient(settings)
    # Force clean state regardless of env vars
    c._client_id = None
    c._client_secret = None
    c._access_token = None
    # Replace httpx client with a mock to prevent real network calls
    c.http = AsyncMock(spec=httpx.AsyncClient)
    return c


@pytest.mark.asyncio
async def test_register_and_authenticate():
    client = _make_client()
    client.http.post = AsyncMock(
        side_effect=[
            _mock_response(REGISTRATION_RESPONSE),  # registration
            _mock_response(TOKEN_RESPONSE),  # token
        ]
    )

    await client.authenticate()

    assert client._client_id == "test-client-id"
    assert client._client_secret == "test-client-secret"
    assert client._access_token == "test-access-token"
    assert client.http.post.call_count == 2


@pytest.mark.asyncio
async def test_reuses_client_id_on_reauthenticate():
    client = _make_client()
    client.http.post = AsyncMock(
        side_effect=[
            _mock_response(REGISTRATION_RESPONSE),  # registration
            _mock_response(TOKEN_RESPONSE),  # first token
            _mock_response({**TOKEN_RESPONSE, "access_token": "new-token"}),  # second token
        ]
    )

    await client.authenticate()
    await client.authenticate()

    assert client._access_token == "new-token"
    # Registration (first call) + two token requests = 3 total
    assert client.http.post.call_count == 3
    # Only the first POST should be to registration
    first_url = str(client.http.post.call_args_list[0][0][0])
    assert "registration" in first_url
    # Subsequent POSTs should be to token endpoint only
    second_url = str(client.http.post.call_args_list[1][0][0])
    assert "token" in second_url
    third_url = str(client.http.post.call_args_list[2][0][0])
    assert "token" in third_url


@pytest.mark.asyncio
async def test_get_patient():
    client = _make_client()
    client.http.post = AsyncMock(
        side_effect=[
            _mock_response(REGISTRATION_RESPONSE),
            _mock_response(TOKEN_RESPONSE),
        ]
    )
    await client.authenticate()

    client.http.get = AsyncMock(return_value=_mock_response(PATIENT_RESOURCE))

    result = await client.get_patient("test-uuid-123")
    assert result["resourceType"] == "Patient"
    assert result["id"] == "test-uuid-123"


@pytest.mark.asyncio
async def test_search_patients():
    client = _make_client()
    client.http.post = AsyncMock(
        side_effect=[
            _mock_response(REGISTRATION_RESPONSE),
            _mock_response(TOKEN_RESPONSE),
        ]
    )
    await client.authenticate()

    client.http.get = AsyncMock(return_value=_mock_response(BUNDLE_RESPONSE))

    result = await client.search_patients(name="Doe")
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_auto_retry_on_401():
    client = _make_client()
    client.http.post = AsyncMock(
        side_effect=[
            _mock_response(REGISTRATION_RESPONSE),
            _mock_response(TOKEN_RESPONSE),
            _mock_response({**TOKEN_RESPONSE, "access_token": "refreshed-token"}),
        ]
    )
    await client.authenticate()

    # First GET returns 401, then re-auth, then retry succeeds
    client.http.get = AsyncMock(
        side_effect=[
            _mock_response({}, status_code=401),
            _mock_response(PATIENT_RESOURCE),
        ]
    )

    result = await client.get_patient("test-uuid-123")
    assert result["resourceType"] == "Patient"
    assert client._access_token == "refreshed-token"


@pytest.mark.asyncio
async def test_get_conditions():
    client = _make_client()
    client.http.post = AsyncMock(
        side_effect=[
            _mock_response(REGISTRATION_RESPONSE),
            _mock_response(TOKEN_RESPONSE),
        ]
    )
    await client.authenticate()

    client.http.get = AsyncMock(return_value=_mock_response(BUNDLE_RESPONSE))

    result = await client.get_conditions("uuid-1")
    assert result["resourceType"] == "Bundle"


@pytest.mark.asyncio
async def test_get_medications():
    client = _make_client()
    client.http.post = AsyncMock(
        side_effect=[
            _mock_response(REGISTRATION_RESPONSE),
            _mock_response(TOKEN_RESPONSE),
        ]
    )
    await client.authenticate()

    client.http.get = AsyncMock(return_value=_mock_response(BUNDLE_RESPONSE))

    result = await client.get_medications("uuid-1")
    assert result["resourceType"] == "Bundle"


@pytest.mark.asyncio
async def test_unauthenticated_client_auto_authenticates():
    """Client auto-authenticates on first FHIR call if no token exists."""
    client = _make_client()
    client.http.post = AsyncMock(
        side_effect=[
            _mock_response(REGISTRATION_RESPONSE),
            _mock_response(TOKEN_RESPONSE),
        ]
    )
    client.http.get = AsyncMock(return_value=_mock_response(PATIENT_RESOURCE))

    result = await client.get_patient("any-uuid")
    assert result["resourceType"] == "Patient"
    assert client._access_token == "test-access-token"
