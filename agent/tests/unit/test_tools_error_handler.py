"""Unit tests for the tool error handler decorator."""

import pytest

from app.tools.base import tool_error_handler


@pytest.mark.asyncio
async def test_error_handler_catches_exceptions():
    @tool_error_handler
    async def failing_tool():
        raise ValueError("something broke")

    result = await failing_tool()
    assert result["status"] == "error"
    assert "ValueError" in result["error"]


@pytest.mark.asyncio
async def test_error_handler_catches_timeout():
    @tool_error_handler
    async def slow_tool():
        raise TimeoutError("too slow")

    result = await slow_tool()
    assert result["status"] == "error"
    assert "timed out" in result["error"]
