"""Unit tests for the appointments LangChain tool (agent/app/tools/appointments.py)."""

from unittest.mock import AsyncMock

import pytest

import app.tools.appointments as appointments_module
from app.tools.appointments import get_appointments, set_client


@pytest.mark.asyncio
async def test_happy_path_two_appointments(mock_openemr_client):
    """Happy path: two appointments parsed with all fields."""
    set_client(mock_openemr_client)

    result = await get_appointments.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    data = result["data"]
    assert data["total"] == 2

    first = data["appointments"][0]
    assert first["date"] == "2026-03-01"
    assert first["time"] == "09:00:00Z"
    assert first["provider"] == "Dr. Smith"
    assert first["reason"] == "Follow-up visit"
    assert first["status"] == "booked"

    second = data["appointments"][1]
    assert second["date"] == "2026-01-10"
    assert second["time"] == "14:30:00Z"
    assert second["provider"] == "Dr. Jones"
    assert second["reason"] == "Annual physical"
    assert second["status"] == "fulfilled"


@pytest.mark.asyncio
async def test_empty_bundle_returns_empty_list(mock_openemr_client):
    """An empty entry list in the bundle produces an empty appointments list with total=0."""
    mock_openemr_client.get_appointments.return_value = {
        "resourceType": "Bundle",
        "entry": [],
    }
    set_client(mock_openemr_client)

    result = await get_appointments.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    assert result["data"]["appointments"] == []
    assert result["data"]["total"] == 0


@pytest.mark.asyncio
async def test_missing_provider_defaults_to_empty(mock_openemr_client):
    """When an appointment has no participant array, provider defaults to empty string."""
    mock_openemr_client.get_appointments.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Appointment",
                    "status": "booked",
                    "start": "2026-04-01T10:00:00Z",
                    "participant": [],
                    "reasonCode": [{"text": "Consultation"}],
                }
            }
        ],
    }
    set_client(mock_openemr_client)

    result = await get_appointments.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    appt = result["data"]["appointments"][0]
    assert appt["provider"] == ""
    assert appt["reason"] == "Consultation"
    assert appt["status"] == "booked"


@pytest.mark.asyncio
async def test_missing_reason_code_defaults_to_empty(mock_openemr_client):
    """When an appointment has no reasonCode field, reason defaults to empty string."""
    mock_openemr_client.get_appointments.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Appointment",
                    "status": "booked",
                    "start": "2026-04-15T08:00:00Z",
                    "participant": [
                        {
                            "actor": {
                                "reference": "Practitioner/prov-3",
                                "display": "Dr. Brown",
                            }
                        }
                    ],
                }
            }
        ],
    }
    set_client(mock_openemr_client)

    result = await get_appointments.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    appt = result["data"]["appointments"][0]
    assert appt["reason"] == ""
    assert appt["provider"] == "Dr. Brown"


@pytest.mark.asyncio
async def test_missing_start_datetime(mock_openemr_client):
    """When an appointment has no 'start' field, both date and time default to empty string."""
    mock_openemr_client.get_appointments.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Appointment",
                    "status": "proposed",
                    "participant": [
                        {
                            "actor": {
                                "reference": "Practitioner/prov-4",
                                "display": "Dr. Green",
                            }
                        }
                    ],
                    "reasonCode": [{"text": "New patient visit"}],
                }
            }
        ],
    }
    set_client(mock_openemr_client)

    result = await get_appointments.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "success"
    appt = result["data"]["appointments"][0]
    assert appt["date"] == ""
    assert appt["time"] == ""
    assert appt["status"] == "proposed"


@pytest.mark.asyncio
async def test_client_connection_error_returns_structured_error():
    """When get_appointments raises ConnectionError, tool_error_handler returns status='error'."""
    client = AsyncMock()
    client.get_appointments.side_effect = ConnectionError("timeout")
    set_client(client)

    result = await get_appointments.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "get_appointments" in result["error"]
    assert "ConnectionError" in result["error"]
    assert "timeout" in result["error"]


@pytest.mark.asyncio
async def test_client_timeout_returns_structured_error():
    """When get_appointments raises TimeoutError, the error message includes 'timed out'."""
    client = AsyncMock()
    client.get_appointments.side_effect = TimeoutError()
    set_client(client)

    result = await get_appointments.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "timed out" in result["error"].lower()
    assert "get_appointments" in result["error"]


@pytest.mark.asyncio
async def test_no_client_raises_runtime_error():
    """When _client is None, _get_client() raises RuntimeError surfaced as a structured error."""
    appointments_module._client = None

    result = await get_appointments.ainvoke({"patient_uuid": "uuid-1"})

    assert result["status"] == "error"
    assert "RuntimeError" in result["error"]
    assert "not initialized" in result["error"].lower()
