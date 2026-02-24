"""Chat endpoint — sends user messages through the LangGraph agent."""

import uuid

from fastapi import APIRouter, Request
from langchain_core.messages import HumanMessage

from app.schemas.chat import ChatRequest, ChatResponse, ToolCall

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    """Process a user chat message through the clinical AI agent."""
    graph = request.app.state.agent_graph
    conversation_id = req.conversation_id or str(uuid.uuid4())

    input_state = {
        "messages": [HumanMessage(content=req.message)],
        "patient_uuid": req.patient_uuid,
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

    # Last AI message is the response
    response_text = result["messages"][-1].content

    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        tool_calls=tool_calls,
    )
