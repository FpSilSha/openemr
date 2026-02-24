"""Chat endpoint — sends user messages through the LangGraph agent."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage

from app.schemas.chat import ChatRequest, ChatResponse, ToolCall

router = APIRouter()


@dataclass
class SessionContext:
    """Server-side session state — LLM never sees or controls this."""

    conversation_id: str
    patient_uuid: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# In-memory session store (single-process; SQLite in Phase 3b)
_sessions: dict[str, SessionContext] = {}


def get_sessions() -> dict[str, SessionContext]:
    """Accessor for session store (allows test injection)."""
    return _sessions


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    """Process a user chat message through the clinical AI agent."""
    graph = request.app.state.agent_graph
    conversation_id = req.conversation_id or str(uuid.uuid4())
    sessions = get_sessions()

    # --- Session binding ---
    if conversation_id in sessions:
        session = sessions[conversation_id]
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
        sessions[conversation_id] = session

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

    result = await graph.ainvoke(input_state)

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
