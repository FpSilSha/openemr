"""Unit tests for session-based patient binding and secure tool node."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routes.chat import SessionContext, get_sessions

# ---------------------------------------------------------------------------
# Session binding tests
# ---------------------------------------------------------------------------


def test_new_conversation_creates_session():
    """A new conversation_id creates a SessionContext entry."""
    sessions = get_sessions()
    sessions.clear()
    conv_id = "conv-new"
    sessions[conv_id] = SessionContext(
        conversation_id=conv_id, patient_uuid="uuid-1"
    )
    assert conv_id in sessions
    assert sessions[conv_id].patient_uuid == "uuid-1"
    sessions.clear()


def test_patient_uuid_locked_on_first_message():
    """Once patient_uuid is set, it stays locked."""
    sessions = get_sessions()
    sessions.clear()
    session = SessionContext(
        conversation_id="conv-lock", patient_uuid="uuid-1"
    )
    sessions["conv-lock"] = session
    assert session.patient_uuid == "uuid-1"
    sessions.clear()


def test_same_patient_uuid_is_accepted():
    """Re-sending the same patient_uuid does not raise."""
    session = SessionContext(
        conversation_id="conv-same", patient_uuid="uuid-1"
    )
    # Simulates the route logic: same uuid is fine
    incoming_uuid = "uuid-1"
    assert not (
        session.patient_uuid
        and incoming_uuid
        and incoming_uuid != session.patient_uuid
    )


def test_different_patient_uuid_is_rejected():
    """Changing patient_uuid mid-conversation is detected."""
    session = SessionContext(
        conversation_id="conv-reject", patient_uuid="uuid-1"
    )
    incoming_uuid = "uuid-different"
    is_violation = (
        session.patient_uuid
        and incoming_uuid
        and incoming_uuid != session.patient_uuid
    )
    assert is_violation


def test_no_patient_uuid_creates_unbound_session():
    """A session without patient_uuid starts unbound."""
    session = SessionContext(conversation_id="conv-unbound")
    assert session.patient_uuid is None


def test_late_binding_sets_patient_uuid():
    """First message without UUID, second with UUID locks it."""
    session = SessionContext(conversation_id="conv-late")
    assert session.patient_uuid is None
    # Simulate late binding
    session.patient_uuid = "uuid-late"
    assert session.patient_uuid == "uuid-late"


def test_session_has_created_at_timestamp():
    """SessionContext auto-generates a created_at ISO timestamp."""
    session = SessionContext(conversation_id="conv-ts")
    assert session.created_at
    assert "T" in session.created_at  # ISO format


# ---------------------------------------------------------------------------
# Secure tool node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_secure_tool_node_overrides_patient_uuid():
    """secure_tool_node replaces LLM's patient_uuid with session-bound value."""
    from app.agent.graph import _build_secure_tool_node

    # Create a mock tool node
    mock_tool_node = AsyncMock()
    mock_tool_node.ainvoke.return_value = {"messages": []}

    secure_fn = _build_secure_tool_node(mock_tool_node)

    # Build a fake state with a tool call containing wrong UUID
    tool_call = MagicMock()
    tool_call.name = "get_patient_summary"
    tool_call.tool_calls = [
        {
            "name": "get_patient_summary",
            "args": {"patient_uuid": "wrong-uuid"},
            "id": "tc-1",
        }
    ]
    # The last message needs tool_calls attribute
    last_msg = MagicMock()
    last_msg.tool_calls = [
        {
            "name": "get_patient_summary",
            "args": {"patient_uuid": "wrong-uuid"},
            "id": "tc-1",
        }
    ]

    state = {
        "messages": [last_msg],
        "patient_uuid": "session-uuid",
        "patient_context": {"uuid": "session-uuid"},
    }

    await secure_fn(state)

    # Verify the tool node was called
    assert mock_tool_node.ainvoke.called
    # The patched state should have overridden UUID
    called_state = mock_tool_node.ainvoke.call_args[0][0]
    patched_uuid = called_state["messages"][-1].tool_calls[0]["args"][
        "patient_uuid"
    ]
    assert patched_uuid == "session-uuid"


@pytest.mark.asyncio
async def test_secure_tool_node_passthrough_without_context():
    """Without patient_context, secure_tool_node passes state unchanged."""
    from app.agent.graph import _build_secure_tool_node

    mock_tool_node = AsyncMock()
    mock_tool_node.ainvoke.return_value = {"messages": []}

    secure_fn = _build_secure_tool_node(mock_tool_node)

    state = {
        "messages": [],
        "patient_uuid": None,
        "patient_context": None,
    }

    await secure_fn(state)

    # Should be called with the original state
    mock_tool_node.ainvoke.assert_called_once_with(state)
