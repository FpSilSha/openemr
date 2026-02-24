"""Seed demo patients in OpenEMR for development and testing.

Usage (inside Docker):
    python scripts/seed_patients.py

Discovers existing patients via FHIR search. If none exist beyond the
default admin, creates demo patients via the REST API.
Outputs patient UUIDs for use in eval datasets.
"""

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.clients.openemr import OpenEMRClient
from app.config import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DEMO_PATIENTS = [
    {
        "fname": "John",
        "lname": "Doe",
        "DOB": "1980-01-15",
        "sex": "Male",
        "street": "123 Main St",
        "city": "Springfield",
        "state": "IL",
        "postal_code": "62701",
    },
    {
        "fname": "Jane",
        "lname": "Smith",
        "DOB": "1975-06-22",
        "sex": "Female",
        "street": "456 Oak Ave",
        "city": "Springfield",
        "state": "IL",
        "postal_code": "62701",
    },
]


async def main():
    settings = Settings()
    client = OpenEMRClient(settings)

    try:
        await client.authenticate()
        logger.info("Authenticated with OpenEMR")

        # Check existing patients
        bundle = await client.search_patients()
        entries = bundle.get("entry", [])
        existing = []
        for entry in entries:
            resource = entry.get("resource", {})
            names = resource.get("name", [{}])
            name = ""
            if names:
                given = " ".join(names[0].get("given", []))
                family = names[0].get("family", "")
                name = f"{given} {family}".strip()
            existing.append({
                "uuid": resource.get("id", ""),
                "name": name,
            })

        if existing:
            logger.info("Found %d existing patients:", len(existing))
            for p in existing:
                logger.info("  %s — %s", p["uuid"], p["name"])
            print(json.dumps({"patients": existing}, indent=2))
            return

        # Create demo patients via REST API
        logger.info("No patients found, creating demo patients...")
        created = []
        for patient_data in DEMO_PATIENTS:
            resp = await client.http.post(
                f"{settings.openemr_api_url}/api/patient",
                headers=client._auth_headers(),
                json=patient_data,
            )
            if resp.status_code == 401:
                await client.authenticate()
                resp = await client.http.post(
                    f"{settings.openemr_api_url}/api/patient",
                    headers=client._auth_headers(),
                    json=patient_data,
                )
            resp.raise_for_status()
            data = resp.json()
            uuid = data.get("data", {}).get("uuid", data.get("uuid", ""))
            name = f"{patient_data['fname']} {patient_data['lname']}"
            created.append({"uuid": uuid, "name": name})
            logger.info("Created patient: %s — %s", uuid, name)

        print(json.dumps({"patients": created}, indent=2))

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
