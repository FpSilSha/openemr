"""Unit tests for HITL (Human-in-the-Loop) approval flow."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.graph import _approval_gate, _needs_approval
from app.persistence.store import SessionRecord, SessionStore
from app.routes.approve import (
    APPROVAL_TTL_HOURS,
    _extract_response,
    approve_action,
    list_pending,
)
from app.schemas.approve import ApprovalRequest

# ---------------------------------------------------------------------------
# _needs_approval edge function tests
# ---------------------------------------------------------------------------


def _make_tool_message(content_dict: dict, name: str = "create_clinical_note"):
    """Helper to create a ToolMessage with JSON content."""
    return ToolMessage(
        content=json.dumps(content_dict),
        tool_call_id="tc-1",
        name=name,
    )


def test_needs_approval_returns_needs_approval_when_flag_set():
    """_needs_approval detects requires_human_confirmation in tool result."""
    state = {
        "messages": [
            AIMessage(content="Creating note..."),
            _make_tool_message({
                "data": {
                    "requires_human_confirmation": True,
                    "draft": "Clinical note draft...",
                }
            }),
        ]
    }
    assert _needs_approval(state) == "needs_approval"


def test_needs_approval_returns_no_approval_for_normal_tools():
    """_needs_approval returns no_approval for regular tool results."""
    state = {
        "messages": [
            AIMessage(content="Fetching labs..."),
            ToolMessage(
                content=json.dumps({"data": {"results": []}}),
                tool_call_id="tc-1",
                name="get_lab_results",
            ),
        ]
    }
    assert _needs_approval(state) == "no_approval"


def test_needs_approval_handles_non_json_content():
    """_needs_approval gracefully handles non-JSON tool content."""
    state = {
        "messages": [
            AIMessage(content="done"),
            ToolMessage(
                content="Plain text result",
                tool_call_id="tc-1",
                name="get_patient_summary",
            ),
        ]
    }
    assert _needs_approval(state) == "no_approval"


def test_needs_approval_only_checks_trailing_tool_messages():
    """_needs_approval stops scanning at the first non-ToolMessage."""
    # An old tool message with the flag should be ignored if followed by AIMessage
    state = {
        "messages": [
            _make_tool_message({
                "data": {"requires_human_confirmation": True}
            }),
            AIMessage(content="Agent acknowledged"),
            ToolMessage(
                content=json.dumps({"data": {"results": []}}),
                tool_call_id="tc-2",
                name="get_labs",
            ),
        ]
    }
    assert _needs_approval(state) == "no_approval"


def test_needs_approval_checks_top_level_flag():
    """_needs_approval detects flag at top level (no nested 'data' key)."""
    state = {
        "messages": [
            _make_tool_message({"requires_human_confirmation": True}),
        ]
    }
    assert _needs_approval(state) == "needs_approval"


# ---------------------------------------------------------------------------
# _approval_gate node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_gate_extracts_pending_action():
    """_approval_gate extracts the pending action from tool results."""
    draft_data = {
        "requires_human_confirmation": True,
        "draft": "SOAP Note...",
        "note_type": "soap",
    }
    state = {
        "messages": [
            AIMessage(content="Creating note"),
            _make_tool_message({"data": draft_data}),
        ]
    }
    result = await _approval_gate(state)
    assert result["requires_human_confirmation"] is True
    assert result["pending_action"]["draft"] == "SOAP Note..."


@pytest.mark.asyncio
async def test_approval_gate_handles_no_pending():
    """_approval_gate returns None pending_action if nothing found."""
    state = {
        "messages": [
            AIMessage(content="Regular response"),
        ]
    }
    result = await _approval_gate(state)
    assert result["requires_human_confirmation"] is True
    assert result["pending_action"] is None


# ---------------------------------------------------------------------------
# _extract_response helper tests
# ---------------------------------------------------------------------------


def test_extract_response_finds_last_ai_message():
    """_extract_response returns the last AIMessage content."""
    result = {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="First response"),
            AIMessage(content="Final response"),
        ]
    }
    assert _extract_response(result) == "Final response"


def test_extract_response_returns_empty_on_no_messages():
    """_extract_response returns empty string when no messages."""
    assert _extract_response({}) == ""
    assert _extract_response({"messages": []}) == ""


def test_extract_response_skips_non_ai_messages():
    """_extract_response ignores HumanMessages at the end."""
    result = {
        "messages": [
            AIMessage(content="AI says"),
            HumanMessage(content="Human says"),
        ]
    }
    assert _extract_response(result) == "AI says"


# ---------------------------------------------------------------------------
# Approval endpoint tests
# ---------------------------------------------------------------------------


def _make_mock_request(store, graph=None):
    """Build a mock FastAPI Request with app.state attributes."""
    app_state = SimpleNamespace(
        session_store=store,
        agent_graph=graph or AsyncMock(),
    )
    app = SimpleNamespace(state=app_state)
    request = MagicMock()
    request.app = app
    return request


@pytest.fixture
async def hitl_store():
    """Create a temporary SessionStore with a pending approval session."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    s = SessionStore(db_path)
    await s.init_db()
    yield s
    await s.close()
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_approve_missing_conversation(hitl_store):
    """POST /approve with unknown conversation_id returns 404."""
    req = ApprovalRequest(
        conversation_id="nonexistent", approved=True
    )
    request = _make_mock_request(hitl_store)

    with pytest.raises(Exception) as exc_info:
        await approve_action(req, request)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_approve_no_pending(hitl_store):
    """POST /approve when no pending approval returns 400."""
    await hitl_store.upsert_session(SessionRecord(
        conversation_id="conv-no-pending",
        thread_id="thread-1",
        created_at=datetime.now(timezone.utc).isoformat(),
        pending_approval=False,
    ))

    req = ApprovalRequest(
        conversation_id="conv-no-pending", approved=True
    )
    request = _make_mock_request(hitl_store)

    with pytest.raises(Exception) as exc_info:
        await approve_action(req, request)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_approve_expired_draft(hitl_store):
    """POST /approve on an expired draft returns 'expired' status."""
    old_time = (
        datetime.now(timezone.utc) - timedelta(hours=APPROVAL_TTL_HOURS + 1)
    ).isoformat()

    await hitl_store.upsert_session(SessionRecord(
        conversation_id="conv-expired",
        thread_id="thread-expired",
        created_at=old_time,
        pending_approval=True,
        pending_action='{"draft": "old note"}',
    ))

    req = ApprovalRequest(
        conversation_id="conv-expired", approved=True
    )
    request = _make_mock_request(hitl_store)
    response = await approve_action(req, request)

    assert response.status == "expired"
    assert "expired" in response.response.lower()
    assert response.conversation_id == "conv-expired"

    # Verify pending state was cleared
    session = await hitl_store.get_session("conv-expired")
    assert session is not None
    assert session.pending_approval is False
    assert session.pending_action is None


@pytest.mark.asyncio
async def test_approve_fresh_draft_approved(hitl_store):
    """POST /approve with approved=True resumes the graph."""
    now = datetime.now(timezone.utc).isoformat()

    await hitl_store.upsert_session(SessionRecord(
        conversation_id="conv-approve",
        thread_id="thread-approve",
        created_at=now,
        pending_approval=True,
        pending_action='{"draft": "SOAP note"}',
    ))

    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Note saved successfully.")]
    }

    req = ApprovalRequest(
        conversation_id="conv-approve", approved=True
    )
    request = _make_mock_request(hitl_store, graph=mock_graph)
    response = await approve_action(req, request)

    assert response.status == "approved"
    assert response.response == "Note saved successfully."

    # Graph was resumed with None (standard resume pattern)
    mock_graph.ainvoke.assert_called_once_with(
        None, config={"configurable": {"thread_id": "thread-approve"}}
    )

    # Pending state cleared
    session = await hitl_store.get_session("conv-approve")
    assert session is not None
    assert session.pending_approval is False


@pytest.mark.asyncio
async def test_approve_rejected_with_note(hitl_store):
    """POST /approve with approved=False sends rejection through graph."""
    now = datetime.now(timezone.utc).isoformat()

    await hitl_store.upsert_session(SessionRecord(
        conversation_id="conv-reject",
        thread_id="thread-reject",
        created_at=now,
        pending_approval=True,
    ))

    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Understood, discarding draft.")]
    }

    req = ApprovalRequest(
        conversation_id="conv-reject",
        approved=False,
        clinician_note="Dosage seems wrong",
    )
    request = _make_mock_request(hitl_store, graph=mock_graph)
    response = await approve_action(req, request)

    assert response.status == "rejected"
    assert response.response == "Understood, discarding draft."

    # Verify the rejection message was sent to the graph
    call_args = mock_graph.ainvoke.call_args
    messages = call_args[0][0]["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert "rejected" in messages[0].content.lower()
    assert "Dosage seems wrong" in messages[0].content


@pytest.mark.asyncio
async def test_approve_rejected_without_note(hitl_store):
    """POST /approve rejection without clinician_note omits note text."""
    now = datetime.now(timezone.utc).isoformat()

    await hitl_store.upsert_session(SessionRecord(
        conversation_id="conv-reject-no-note",
        thread_id="thread-reject-nn",
        created_at=now,
        pending_approval=True,
    ))

    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "messages": [AIMessage(content="OK")]
    }

    req = ApprovalRequest(
        conversation_id="conv-reject-no-note",
        approved=False,
    )
    request = _make_mock_request(hitl_store, graph=mock_graph)
    response = await approve_action(req, request)

    assert response.status == "rejected"
    # Rejection message should NOT contain "Note:"
    call_args = mock_graph.ainvoke.call_args
    content = call_args[0][0]["messages"][0].content
    assert "Note:" not in content


# ---------------------------------------------------------------------------
# GET /pending endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pending_returns_pending_sessions(hitl_store):
    """GET /pending returns only sessions with pending_approval=True."""
    now = datetime.now(timezone.utc).isoformat()

    await hitl_store.upsert_session(SessionRecord(
        conversation_id="conv-pending",
        thread_id="thread-p",
        created_at=now,
        pending_approval=True,
        pending_action='{"type": "clinical_note"}',
    ))
    await hitl_store.upsert_session(SessionRecord(
        conversation_id="conv-done",
        thread_id="thread-d",
        created_at=now,
        pending_approval=False,
    ))

    request = _make_mock_request(hitl_store)
    result = await list_pending(request)

    assert len(result) == 1
    assert result[0].conversation_id == "conv-pending"
    assert result[0].pending_action == '{"type": "clinical_note"}'


@pytest.mark.asyncio
async def test_list_pending_empty(hitl_store):
    """GET /pending returns empty list when no pending approvals."""
    request = _make_mock_request(hitl_store)
    result = await list_pending(request)
    assert result == []
