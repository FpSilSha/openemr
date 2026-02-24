"""Integration test configuration — auto-skip when Docker/LLM unavailable."""

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests requiring live Docker and/or LLM"
        " (deselect with '-m \"not integration\"')",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests unless AGENTFORGE_INTEGRATION=1."""
    if os.environ.get("AGENTFORGE_INTEGRATION") == "1":
        return
    skip_integration = pytest.mark.skip(
        reason="Set AGENTFORGE_INTEGRATION=1 to run integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
