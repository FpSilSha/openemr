"""Export OpenEMR demo data as deterministic test fixtures.

Usage (inside Docker):
    python scripts/export_fixtures.py

Authenticates with OpenEMR, exports all patients and their clinical data,
and writes to agent/tests/fixtures/ for use in eval datasets.

Outputs:
  - tests/fixtures/demo_data.json — all patient data (conditions, meds, labs, etc.)
  - tests/fixtures/uuid_mapping.json — placeholder → real UUID mapping for evals
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.clients.openemr import OpenEMRClient
from app.config import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FIXTURE_VERSION = 1
FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests",
    "fixtures",
)


async def export_patient_data(client: OpenEMRClient, patient_uuid: str) -> dict:
    """Export all clinical data for a single patient."""
    data: dict = {"uuid": patient_uuid}

    # Patient demographics
    try:
        patient = await client.get_patient(patient_uuid)
        data["patient"] = patient
    except Exception as e:
        logger.warning("Failed to get patient %s: %s", patient_uuid, e)
        data["patient"] = None

    # Conditions
    try:
        conditions = await client.get_conditions(patient_uuid)
        data["conditions"] = conditions
    except Exception as e:
        logger.warning("Failed to get conditions for %s: %s", patient_uuid, e)
        data["conditions"] = {"entry": []}

    # Medications
    try:
        medications = await client.get_medications(patient_uuid)
        data["medications"] = medications
    except Exception as e:
        logger.warning("Failed to get medications for %s: %s", patient_uuid, e)
        data["medications"] = {"entry": []}

    # Lab results / observations
    try:
        observations = await client.get_observations(patient_uuid)
        data["observations"] = observations
    except Exception as e:
        logger.warning("Failed to get observations for %s: %s", patient_uuid, e)
        data["observations"] = {"entry": []}

    # Vitals
    try:
        vitals = await client.get_vitals(patient_uuid)
        data["vitals"] = vitals
    except Exception as e:
        logger.warning("Failed to get vitals for %s: %s", patient_uuid, e)
        data["vitals"] = {"entry": []}

    # Allergies
    try:
        allergies = await client.get_allergies(patient_uuid)
        data["allergies"] = allergies
    except Exception as e:
        logger.warning("Failed to get allergies for %s: %s", patient_uuid, e)
        data["allergies"] = {"entry": []}

    # Appointments
    try:
        appointments = await client.get_appointments(patient_uuid)
        data["appointments"] = appointments
    except Exception as e:
        logger.warning("Failed to get appointments for %s: %s", patient_uuid, e)
        data["appointments"] = {"entry": []}

    return data


async def main():
    settings = Settings()
    client = OpenEMRClient(settings)

    try:
        await client.authenticate()
        logger.info("Authenticated with OpenEMR")

        # Discover all patients
        bundle = await client.search_patients()
        entries = bundle.get("entry", [])

        if not entries:
            logger.error("No patients found in OpenEMR. Run seed_patients.py first.")
            sys.exit(1)

        patients = []
        uuid_mapping = {}

        for idx, entry in enumerate(entries):
            resource = entry.get("resource", {})
            patient_uuid = resource.get("id", "")
            names = resource.get("name", [{}])
            name = ""
            if names:
                given = " ".join(names[0].get("given", []))
                family = names[0].get("family", "")
                name = f"{given} {family}".strip()

            logger.info("Exporting patient %d: %s (%s)", idx + 1, name, patient_uuid)
            patient_data = await export_patient_data(client, patient_uuid)
            patient_data["display_name"] = name
            patients.append(patient_data)

            # Create placeholder mapping (PATIENT_1, PATIENT_2, etc.)
            placeholder = f"PATIENT_{idx + 1}"
            uuid_mapping[placeholder] = patient_uuid

        # Write demo_data.json
        os.makedirs(FIXTURE_DIR, exist_ok=True)
        demo_data = {
            "fixture_version": FIXTURE_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "patient_count": len(patients),
            "patients": patients,
        }

        demo_path = os.path.join(FIXTURE_DIR, "demo_data.json")
        with open(demo_path, "w") as f:
            json.dump(demo_data, f, indent=2)
        logger.info("Wrote %s (%d patients)", demo_path, len(patients))

        # Write uuid_mapping.json
        mapping_path = os.path.join(FIXTURE_DIR, "uuid_mapping.json")
        with open(mapping_path, "w") as f:
            json.dump(uuid_mapping, f, indent=2)
        logger.info("Wrote %s", mapping_path)

        # Print summary
        print("\nExported patients:")
        for placeholder, uuid in uuid_mapping.items():
            print(f"  {placeholder} → {uuid}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
