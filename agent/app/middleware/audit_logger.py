"""PHI access audit logging middleware — logs patient data access to JSONL."""

import json
import logging
import time
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

LOG_DIR = Path("/app/logs")
AUDIT_LOG_FILE = LOG_DIR / "audit_log.jsonl"


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Logs PHI access events for /chat requests that include a patient_uuid."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path != "/chat" or request.method != "POST":
            response: Response = await call_next(request)
            return response

        # Read and cache the request body for downstream handlers
        body_bytes = await request.body()
        patient_uuid = None
        conversation_id = None
        try:
            body = json.loads(body_bytes)
            patient_uuid = body.get("patient_uuid")
            conversation_id = body.get("conversation_id")
        except (json.JSONDecodeError, AttributeError):
            pass

        response = await call_next(request)

        # Only log when a patient_uuid is present (PHI access)
        if patient_uuid:
            entry = {
                "timestamp": time.time(),
                "patient_uuid": patient_uuid,
                "conversation_id": conversation_id or "",
                "endpoint": "/chat",
                "method": "POST",
                "status_code": response.status_code,
            }
            try:
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                with open(AUDIT_LOG_FILE, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except OSError:
                logger.warning("Could not write audit log entry")

        return response
