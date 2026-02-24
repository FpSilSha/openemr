"""Shared test fixtures for AgentForge unit tests."""

from unittest.mock import AsyncMock

import pytest


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
    """AsyncMock of DrugInteractionClient with RxCUI resolution and interaction data."""
    client = AsyncMock()

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

    return client
