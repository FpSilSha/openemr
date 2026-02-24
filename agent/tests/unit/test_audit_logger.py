"""Unit tests for the PHI audit logging middleware."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.middleware.audit_logger import AuditLogMiddleware


def _make_request(path="/chat", method="POST", body=None):
    """Create a mock Starlette Request."""
    request = MagicMock()
    request.url.path = path
    request.method = method
    body_bytes = json.dumps(body).encode() if body else b"{}"

    async def mock_body():
        return body_bytes

    request.body = mock_body
    return request


def _make_response(status_code=200):
    """Create a mock Response."""
    response = MagicMock()
    response.status_code = status_code
    return response


@pytest.mark.asyncio
async def test_logs_chat_request_with_patient_uuid():
    """Audit log entry is written for /chat with patient_uuid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "audit_log.jsonl"
        middleware = AuditLogMiddleware(app=MagicMock())

        body = {"patient_uuid": "uuid-1", "conversation_id": "conv-1"}
        request = _make_request(body=body)
        response = _make_response()

        async def call_next(_):
            return response

        with (
            patch(
                "app.middleware.audit_logger.LOG_DIR", Path(tmpdir)
            ),
            patch(
                "app.middleware.audit_logger.AUDIT_LOG_FILE", log_file
            ),
        ):
            await middleware.dispatch(request, call_next)

        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["patient_uuid"] == "uuid-1"
        assert entry["conversation_id"] == "conv-1"
        assert entry["endpoint"] == "/chat"
        assert "timestamp" in entry


@pytest.mark.asyncio
async def test_skips_non_chat_paths():
    """Non-/chat paths are passed through without logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "audit_log.jsonl"
        middleware = AuditLogMiddleware(app=MagicMock())

        request = _make_request(path="/health", method="GET")
        response = _make_response()

        async def call_next(_):
            return response

        with (
            patch(
                "app.middleware.audit_logger.LOG_DIR", Path(tmpdir)
            ),
            patch(
                "app.middleware.audit_logger.AUDIT_LOG_FILE", log_file
            ),
        ):
            await middleware.dispatch(request, call_next)

        assert not log_file.exists()


@pytest.mark.asyncio
async def test_skips_chat_without_patient_uuid():
    """A /chat request without patient_uuid does not create an audit entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "audit_log.jsonl"
        middleware = AuditLogMiddleware(app=MagicMock())

        body = {"message": "hello"}
        request = _make_request(body=body)
        response = _make_response()

        async def call_next(_):
            return response

        with (
            patch(
                "app.middleware.audit_logger.LOG_DIR", Path(tmpdir)
            ),
            patch(
                "app.middleware.audit_logger.AUDIT_LOG_FILE", log_file
            ),
        ):
            await middleware.dispatch(request, call_next)

        assert not log_file.exists()


@pytest.mark.asyncio
async def test_handles_write_failure_gracefully():
    """If the log file cannot be written, middleware does not raise."""
    middleware = AuditLogMiddleware(app=MagicMock())

    body = {"patient_uuid": "uuid-fail"}
    request = _make_request(body=body)
    response = _make_response()

    async def call_next(_):
        return response

    # Force open() to raise so the write path hits the OSError handler
    with (
        patch(
            "app.middleware.audit_logger.LOG_DIR",
            Path("/nonexistent/dir"),
        ),
        patch(
            "app.middleware.audit_logger.AUDIT_LOG_FILE",
            Path("/nonexistent/dir/audit.jsonl"),
        ),
        patch(
            "builtins.open",
            side_effect=OSError("Permission denied"),
        ),
    ):
        # Should not raise
        result = await middleware.dispatch(request, call_next)
        assert result.status_code == 200
