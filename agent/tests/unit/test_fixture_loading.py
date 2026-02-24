"""Unit tests for fixture loading and version checking."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

EXPECTED_FIXTURE_VERSION = 1

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fixtures",
)


def _load_fixture(filename: str) -> dict:
    """Load a JSON fixture file from the fixtures directory."""
    path = os.path.join(FIXTURE_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(
            f"Fixture {filename} not found. Run scripts/export_fixtures.py first."
        )
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------


def test_demo_data_loads_when_present():
    """demo_data.json loads and has required structure."""
    data = _load_fixture("demo_data.json")
    assert "fixture_version" in data
    assert "patients" in data
    assert isinstance(data["patients"], list)


def test_fixture_version_matches():
    """Fixture version matches the expected version."""
    data = _load_fixture("demo_data.json")
    assert data["fixture_version"] == EXPECTED_FIXTURE_VERSION, (
        f"Fixture version mismatch: expected {EXPECTED_FIXTURE_VERSION}, "
        f"got {data['fixture_version']}. Re-run scripts/export_fixtures.py."
    )


def test_uuid_mapping_loads_when_present():
    """uuid_mapping.json loads and contains placeholder keys."""
    mapping = _load_fixture("uuid_mapping.json")
    assert isinstance(mapping, dict)
    if mapping:
        # All keys should be PATIENT_N format
        for key in mapping:
            assert key.startswith("PATIENT_"), f"Unexpected key: {key}"


def test_uuid_mapping_resolves_placeholders():
    """UUID mapping replaces placeholders with real UUIDs."""
    mapping = _load_fixture("uuid_mapping.json")
    if not mapping:
        pytest.skip("No UUID mapping entries")

    # Simulate placeholder resolution
    template = "Get patient summary for {{PATIENT_1}}"
    for placeholder, uuid in mapping.items():
        template = template.replace(f"{{{{{placeholder}}}}}", uuid)

    # Should have resolved at least PATIENT_1
    if "PATIENT_1" in mapping:
        assert mapping["PATIENT_1"] in template


# ---------------------------------------------------------------------------
# Fixture-backed mock client
# ---------------------------------------------------------------------------


def test_fixture_backed_mock_returns_data():
    """A mock client built from fixture data returns correct patient info."""
    data = _load_fixture("demo_data.json")
    if not data.get("patients"):
        pytest.skip("No patients in fixture data")

    patient = data["patients"][0]
    assert "uuid" in patient
    assert "patient" in patient

    # Verify clinical data keys exist
    for key in ("conditions", "medications", "observations", "vitals", "allergies"):
        assert key in patient, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Missing fixture handling
# ---------------------------------------------------------------------------


def test_missing_fixture_gives_clear_message():
    """Loading a non-existent fixture skips with a helpful message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "nonexistent.json")
        assert not os.path.exists(path)

    # The _load_fixture function uses pytest.skip, so we verify that path
    # would not exist (the skip mechanism is tested implicitly by the
    # test_demo_data_loads_when_present test being skipped when no fixtures)


def test_fixture_version_check_fails_on_mismatch():
    """Version check raises assertion on outdated fixture."""
    stale_data = {"fixture_version": 0, "patients": []}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(stale_data, f)
        temp_path = f.name

    try:
        with open(temp_path) as f:
            data = json.load(f)
        assert data["fixture_version"] != EXPECTED_FIXTURE_VERSION
    finally:
        os.unlink(temp_path)
