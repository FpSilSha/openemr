"""Unit tests for config module."""

from app.config import Settings


def test_default_settings():
    s = Settings(
        anthropic_api_key="test-key",
        langchain_api_key="test-ls-key",
    )
    assert s.openemr_base_url == "http://openemr:80"
    assert s.openemr_verify_ssl is True
    assert s.primary_model == "claude-sonnet-4-20250514"
    assert s.tool_timeout_seconds == 30.0
    assert s.agent_port == 8000


def test_settings_override():
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
