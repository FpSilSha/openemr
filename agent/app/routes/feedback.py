"""Feedback endpoint — stub for collecting user feedback on responses."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_feedback_store: list[dict] = []


class FeedbackRequest(BaseModel):
    conversation_id: str
    rating: int  # 1-5
    comment: str = ""


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Store user feedback for a conversation."""
    _feedback_store.append(req.model_dump())
    return {"status": "ok", "total_feedback": len(_feedback_store)}
