"""Chat endpoint — sends user messages through the LangGraph agent."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage

from app.persistence.store import SessionRecord, SessionStore
from app.schemas.chat import ChatRequest, ChatResponse, ToolCall

router = APIRouter()


@dataclass
class SessionContext:
    """Server-side session state — LLM never sees or controls this."""

    conversation_id: str
    thread_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    patient_uuid: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# In-memory fallback (used when no SQLite store is configured, e.g. tests)
_sessions: dict[str, SessionContext] = {}


def get_sessions() -> dict[str, SessionContext]:
    """Accessor for in-memory session store (test compatibility)."""
    return _sessions


def _get_store(request: Request) -> SessionStore | None:
    """Get the SQLite session store from app state, if available."""
    return getattr(request.app.state, "session_store", None)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    """Process a user chat message through the clinical AI agent."""
    graph = request.app.state.agent_graph
    conversation_id = req.conversation_id or str(uuid.uuid4())
    store = _get_store(request)

    # --- Session binding (SQLite-backed when available) ---
    session: SessionContext | None = None

    if store:
        record = await store.get_session(conversation_id)
        if record:
            session = SessionContext(
                conversation_id=record.conversation_id,
                thread_id=record.thread_id,
                patient_uuid=record.patient_uuid,
                created_at=record.created_at,
            )
    else:
        # Fallback to in-memory
        session = _sessions.get(conversation_id)

    if session:
        # SECURITY: reject patient_uuid changes mid-conversation
        if (
            session.patient_uuid
            and req.patient_uuid
            and req.patient_uuid != session.patient_uuid
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot change patient context mid-conversation. "
                    "Start a new conversation."
                ),
            )
        # Late binding: first message with patient_uuid locks it
        if req.patient_uuid and not session.patient_uuid:
            session.patient_uuid = req.patient_uuid
    else:
        session = SessionContext(
            conversation_id=conversation_id,
            patient_uuid=req.patient_uuid,
        )

    # Persist session
    if store:
        await store.upsert_session(SessionRecord(
            conversation_id=session.conversation_id,
            thread_id=session.thread_id,
            patient_uuid=session.patient_uuid,
            created_at=session.created_at,
        ))
    else:
        _sessions[conversation_id] = session

    # Use session-bound patient_uuid (not the request's)
    patient_uuid = session.patient_uuid

    # Build patient_context for secure_tool_node
    patient_context = None
    if patient_uuid:
        patient_context = {"uuid": patient_uuid}

    input_state = {
        "messages": [HumanMessage(content=req.message)],
        "patient_uuid": patient_uuid,
        "patient_context": patient_context,
    }

    # Pass thread_id for LangGraph state persistence
    config = {"configurable": {"thread_id": session.thread_id}}
    result = await graph.ainvoke(input_state, config=config)

    # Extract tool calls from message history
    tool_calls = []
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(ToolCall(
                    name=tc["name"],
                    args=tc["args"],
                ))

    # Find the last AIMessage (skip SystemMessage verification feedback)
    response_text = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str):
            response_text = msg.content
            break

    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        tool_calls=tool_calls,
        session_locked=session.patient_uuid is not None,
    )
