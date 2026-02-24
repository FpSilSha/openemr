"""Integration tests for OpenEMR client — requires live Docker stack.

Run with: AGENTFORGE_INTEGRATION=1 pytest tests/integration/ -v
Requires: docker-compose.agent.yml stack running (ports 8380/9380)
"""

import pytest

from app.clients.openemr import OpenEMRClient
from app.config import Settings


@pytest.fixture
async def live_client():
    """Create an OpenEMR client pointed at the local Docker stack."""
    settings = Settings(
        anthropic_api_key="not-needed-for-client-tests",
        langchain_api_key="not-needed",
        openemr_base_url="http://localhost:8380",
        openemr_api_url="http://localhost:8380/apis/default",
        openemr_fhir_url="http://localhost:8380/apis/default/fhir",
        openemr_verify_ssl=False,
    )
    client = OpenEMRClient(settings)
    yield client
    await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_authenticate(live_client):
    """OAuth2 registration + token grant succeeds against live OpenEMR."""
    await live_client.authenticate()
    assert live_client._access_token is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_patient_with_demo_data(live_client):
    """Search for a patient and fetch their record."""
    await live_client.authenticate()
    results = await live_client.search_patients(name="Brady")
    entries = results.get("entry", [])
    if not entries:
        pytest.skip("No demo patient 'Brady' found — run seed script first")
    patient_uuid = entries[0]["resource"]["id"]
    patient = await live_client.get_patient(patient_uuid)
    assert patient["resourceType"] == "Patient"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_patients_demo(live_client):
    """Search returns results without error."""
    await live_client.authenticate()
    results = await live_client.search_patients(name="admin")
    assert "resourceType" in results


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fhir_metadata(live_client):
    """FHIR metadata endpoint returns CapabilityStatement."""
    await live_client.authenticate()
    result = await live_client._fhir_get("metadata")
    assert result["resourceType"] == "CapabilityStatement"
