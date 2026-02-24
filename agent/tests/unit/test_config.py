"""Unit tests for config module."""

from app.config import Settings

# Env vars that CI sets which override Pydantic Settings defaults.
_CI_ENV_VARS = [
    "OPENEMR_BASE_URL",
    "OPENEMR_API_URL",
    "OPENEMR_FHIR_URL",
    "OPENEMR_USERNAME",
    "OPENEMR_PASSWORD",
    "ANTHROPIC_API_KEY",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
]


def test_default_settings(monkeypatch):
    for var in _CI_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    s = Settings(
        anthropic_api_key="test-key",
        langchain_api_key="test-ls-key",
    )
    assert s.openemr_base_url == "http://openemr:80"
    assert s.openemr_verify_ssl is True
    assert s.primary_model == "claude-sonnet-4-20250514"
    assert s.tool_timeout_seconds == 30.0
    assert s.agent_port == 8000


def test_settings_override(monkeypatch):
    for var in _CI_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    s = Settings(
        anthropic_api_key="test-key",
        langchain_api_key="test-ls-key",
        openemr_base_url="https://my-emr.example.com",
        openemr_verify_ssl=False,
        tool_timeout_seconds=60.0,
    )
    assert s.openemr_base_url == "https://my-emr.example.com"
    assert s.openemr_verify_ssl is False
    assert s.tool_timeout_seconds == 60.0
