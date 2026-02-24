"""Request/response schemas for the approval endpoint."""

from pydantic import BaseModel


class ApprovalRequest(BaseModel):
    conversation_id: str
    approved: bool
    clinician_note: str = ""


class ApprovalResponse(BaseModel):
    status: str  # "approved", "rejected", "expired"
    response: str
    conversation_id: str


class PendingItem(BaseModel):
    conversation_id: str
    thread_id: str
    created_at: str
    pending_action: str | None = None
