"""Shared tool utilities — error handler decorator."""

import functools
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def tool_error_handler(func: Callable) -> Callable:
    """Decorator that catches exceptions in tool functions and returns structured errors."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            result: dict[str, Any] = await func(*args, **kwargs)
            return result
        except TimeoutError:
            logger.warning("Tool %s timed out", func.__name__)
            return {
                "status": "error",
                "error": f"Tool '{func.__name__}' timed out. Try again.",
            }
        except Exception as e:
            logger.exception("Tool %s failed: %s", func.__name__, e)
            return {
                "status": "error",
                "error": f"Tool '{func.__name__}' failed: {type(e).__name__}: {e}",
            }

    return wrapper
