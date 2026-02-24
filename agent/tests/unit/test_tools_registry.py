"""Unit tests for the LangChain tool registry."""

from app.tools import ALL_TOOLS, MVP_TOOLS


def test_mvp_tools_count():
    assert len(MVP_TOOLS) == 7


def test_all_tools_count():
    assert len(ALL_TOOLS) == 11


def test_all_tools_have_names():
    for t in ALL_TOOLS:
        assert hasattr(t, "name")
        assert t.name


def test_all_tools_superset_of_mvp():
    for t in MVP_TOOLS:
        assert t in ALL_TOOLS
