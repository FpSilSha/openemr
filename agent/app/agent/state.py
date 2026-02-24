"""LangGraph agent state definition."""

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State passed through the LangGraph agent graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    patient_uuid: str | None
