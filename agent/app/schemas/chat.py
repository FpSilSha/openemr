"""Request/response schemas for the chat endpoint."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    patient_uuid: str | None = None
    conversation_id: str | None = None


class ToolCall(BaseModel):
    name: str
    args: dict
    result: dict | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    tool_calls: list[ToolCall] = []
    session_locked: bool = False
