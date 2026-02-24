"""Shared test fixtures for AgentForge unit tests."""

import os
import tempfile
from unittest.mock import AsyncMock

import pytest

from app.persistence.store import SessionStore


@pytest.fixture
def mock_openemr_client():
    """AsyncMock of OpenEMRClient with rich FHIR response data."""
    client = AsyncMock()

    client.get_patient.return_value = {
        "resourceType": "Patient",
        "id": "uuid-1",
        "name": [{"family": "Doe", "given": ["John"]}],
        "birthDate": "1980-01-15",
        "gender": "male",
    }

    client.get_conditions.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Condition",
                    "code": {
                        "coding": [{"code": "E11.9", "display": "Type 2 diabetes"}],
                        "text": "Type 2 diabetes mellitus",
                    },
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                }
            }
        ],
    }

    client.get_medications.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "medicationCodeableConcept": {"text": "Metformin 500mg"},
                    "status": "active",
                    "intent": "order",
                }
            },
            {
                "resource": {
                    "medicationCodeableConcept": {"text": "Lisinopril 10mg"},
                    "status": "active",
                    "intent": "order",
                }
            },
        ],
    }

    client.get_allergies.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "AllergyIntolerance",
                    "code": {"text": "Penicillin"},
                    "type": "allergy",
                    "criticality": "high",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                    "onsetDateTime": "2020-03-15",
                    "reaction": [
                        {
                            "manifestation": [{"text": "Hives"}],
                            "severity": "severe",
                        }
                    ],
                }
            }
        ],
    }

    client.get_vitals.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Blood Pressure"},
                    "valueQuantity": {"value": 120, "unit": "mmHg"},
                    "effectiveDateTime": "2026-01-15",
                    "status": "final",
                }
            }
        ],
    }

    client.get_observations.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "code": {"text": "Hemoglobin A1c"},
                    "valueQuantity": {"value": 6.5, "unit": "%"},
                    "effectiveDateTime": "2026-01-15",
                    "status": "final",
                }
            }
        ],
    }

    client.get_appointments.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Appointment",
                    "status": "booked",
                    "start": "2026-03-01T09:00:00Z",
                    "participant": [
                        {
                            "actor": {
                                "reference": "Practitioner/prov-1",
                                "display": "Dr. Smith",
                            }
                        }
                    ],
                    "reasonCode": [{"text": "Follow-up visit"}],
                }
            },
            {
                "resource": {
                    "resourceType": "Appointment",
                    "status": "fulfilled",
                    "start": "2026-01-10T14:30:00Z",
                    "participant": [
                        {
                            "actor": {
                                "reference": "Practitioner/prov-2",
                                "display": "Dr. Jones",
                            }
                        }
                    ],
                    "reasonCode": [{"text": "Annual physical"}],
                }
            },
        ],
    }

    client.search_patients.return_value = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "id": "uuid-1",
                    "name": [{"family": "Doe", "given": ["John"]}],
                    "birthDate": "1980-01-15",
                    "gender": "male",
                }
            }
        ],
    }

    return client


@pytest.fixture
def mock_drug_client():
    """AsyncMock of DrugInteractionClient with tiered resolution and interaction data."""
    client = AsyncMock()

    # Legacy exact-match API (used by external client tests)
    client.get_rxcui.side_effect = lambda name: {
        "aspirin": "1191",
        "warfarin": "11289",
        "metformin": "6809",
        "lisinopril": "29046",
    }.get(name.lower())

    client.check_multi_interactions.return_value = [
        {
            "severity": "high",
            "description": "Increased bleeding risk",
            "drugs": ["aspirin", "warfarin"],
        }
    ]

    # Tiered resolution API (used by drug_interaction_check tool)
    def _make_resolution(rxcui, name, tier=1, confidence=1.0):
        return {
            "rxcui": rxcui,
            "name": name,
            "resolution_tier": tier,
            "confidence": confidence,
            "candidates": [],
            "ambiguous": False,
            "original_name": name,
        }

    client.check_interactions_by_names.return_value = {
        "interactions": [
            {
                "severity": "high",
                "description": "Increased bleeding risk",
                "drugs": ["aspirin", "warfarin"],
            }
        ],
        "resolutions": {
            "aspirin": _make_resolution("1191", "aspirin"),
            "warfarin": _make_resolution("11289", "warfarin"),
        },
        "unresolved": [],
        "check_complete": True,
        "warning": None,
    }

    return client


@pytest.fixture
async def mock_session_store():
    """Temporary SQLite-backed SessionStore for tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SessionStore(db_path)
    await store.init_db()
    yield store
    await store.close()
    os.unlink(db_path)
