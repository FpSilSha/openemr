"""Cost tracking middleware — logs chat requests to JSONL."""

import json
import logging
import time
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

LOG_DIR = Path("/app/logs")
LOG_FILE = LOG_DIR / "cost_log.jsonl"


class CostTrackerMiddleware(BaseHTTPMiddleware):
    """Logs timing info for /chat requests to a JSONL file."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path != "/chat":
            response: Response = await call_next(request)
            return response

        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        entry = {
            "timestamp": time.time(),
            "path": "/chat",
            "method": request.method,
            "elapsed_seconds": round(elapsed, 3),
            "status_code": response.status_code,
        }

        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            logger.warning("Could not write cost log entry")

        return response
