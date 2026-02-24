"""Approval endpoints — resume or reject paused HITL workflows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage

from app.persistence.store import SessionStore
from app.schemas.approve import ApprovalRequest, ApprovalResponse, PendingItem

router = APIRouter()
logger = logging.getLogger(__name__)

# Clinical decisions are time-bound — stale drafts use outdated patient data
APPROVAL_TTL_HOURS = 24


def _get_store(request: Request) -> SessionStore:
    store = getattr(request.app.state, "session_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Session store not available")
    return store


@router.post("/approve", response_model=ApprovalResponse)
async def approve_action(req: ApprovalRequest, request: Request):
    """Resume or reject a paused HITL workflow after clinician review."""
    store = _get_store(request)
    graph = request.app.state.agent_graph

    session = await store.get_session(req.conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not session.pending_approval:
        raise HTTPException(
            status_code=400, detail="No pending approval for this conversation"
        )

    # Check TTL — expired drafts use stale clinical data
    created = datetime.fromisoformat(session.created_at)
    age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
    if age_hours > APPROVAL_TTL_HOURS:
        # Clear pending state
        session.pending_approval = False
        session.pending_action = None
        await store.upsert_session(session)

        return ApprovalResponse(
            status="expired",
            response=(
                f"This draft expired after {APPROVAL_TTL_HOURS} hours for patient "
                "safety. Patient data may have changed. Please request a new draft."
            ),
            conversation_id=req.conversation_id,
        )

    config = {"configurable": {"thread_id": session.thread_id}}

    if not req.approved:
        # Rejection: send a message so the agent knows and can respond
        result = await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            "[SYSTEM: Clinician rejected this action."
                            + (
                                f" Note: {req.clinician_note}"
                                if req.clinician_note
                                else ""
                            )
                            + "]"
                        )
                    )
                ]
            },
            config=config,
        )

        # Clear pending state
        session.pending_approval = False
        session.pending_action = None
        await store.upsert_session(session)

        response_text = _extract_response(result)
        return ApprovalResponse(
            status="rejected",
            response=response_text,
            conversation_id=req.conversation_id,
        )

    # Approved: resume the graph from the interrupt point
    result = await graph.ainvoke(None, config=config)

    # Clear pending state
    session.pending_approval = False
    session.pending_action = None
    await store.upsert_session(session)

    response_text = _extract_response(result)
    return ApprovalResponse(
        status="approved",
        response=response_text,
        conversation_id=req.conversation_id,
    )


@router.get("/pending", response_model=list[PendingItem])
async def list_pending(request: Request):
    """List all conversations awaiting clinician approval."""
    store = _get_store(request)
    records = await store.list_pending()
    return [
        PendingItem(
            conversation_id=r.conversation_id,
            thread_id=r.thread_id,
            created_at=r.created_at,
            pending_action=r.pending_action,
        )
        for r in records
    ]


def _extract_response(result: dict) -> str:
    """Extract the last AIMessage text from graph result."""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str):
            return msg.content
    return ""
