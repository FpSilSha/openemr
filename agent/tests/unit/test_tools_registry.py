"""Unit tests for the LangChain tool registry."""

from app.tools import MVP_TOOLS


def test_mvp_tools_count():
    assert len(MVP_TOOLS) == 7


def test_all_tools_have_names():
    for t in MVP_TOOLS:
        assert hasattr(t, "name")
        assert t.name
