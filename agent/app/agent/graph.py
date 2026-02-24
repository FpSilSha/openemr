"""LangGraph agent graph — reason → tools → reason loop with patient security."""

import copy
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.agent.prompts import CLINICAL_ASSISTANT_SYSTEM_PROMPT
from app.agent.state import AgentState
from app.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# Tools that accept patient_uuid as an argument
_PATIENT_SCOPED_TOOLS = {
    "get_patient_summary",
    "get_medications",
    "get_lab_results",
    "get_appointments",
    "get_vitals",
    "get_allergies_detailed",
    "create_clinical_note",
}


def _should_use_tools(state: AgentState) -> str:
    """Edge function: route to tools if the last message has tool_calls."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def _build_secure_tool_node(tool_node: ToolNode):
    """Wrap ToolNode to enforce session-bound patient_uuid."""

    async def secure_tool_node(state: AgentState) -> dict:
        """Override patient_uuid in tool args with session-bound value."""
        patient_ctx = state.get("patient_context")
        if patient_ctx and patient_ctx.get("uuid"):
            session_uuid = patient_ctx["uuid"]
            last = state["messages"][-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                # Deep copy to avoid mutating the original message
                patched = copy.deepcopy(state)
                patched_last = patched["messages"][-1]
                for tc in patched_last.tool_calls:
                    if (
                        tc["name"] in _PATIENT_SCOPED_TOOLS
                        and "patient_uuid" in tc["args"]
                    ):
                        original = tc["args"]["patient_uuid"]
                        if original != session_uuid:
                            logger.warning(
                                "Overriding patient_uuid %s → %s in %s",
                                original,
                                session_uuid,
                                tc["name"],
                            )
                        tc["args"]["patient_uuid"] = session_uuid
                return await tool_node.ainvoke(patched)
        return await tool_node.ainvoke(state)

    return secure_tool_node


def build_graph(
    model: ChatAnthropic, tools: list | None = None
) -> CompiledStateGraph:
    """Build the agent graph with the given model and tools.

    Args:
        model: ChatAnthropic model instance.
        tools: List of LangChain tools to bind. Defaults to ALL_TOOLS.
    """
    tool_list = tools if tools is not None else ALL_TOOLS
    model_with_tools = model.bind_tools(tool_list)

    async def reason(state: AgentState) -> dict:
        """Invoke the LLM with system prompt + conversation history."""
        system = SystemMessage(content=CLINICAL_ASSISTANT_SYSTEM_PROMPT)
        messages = [system] + state["messages"]
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    raw_tool_node = ToolNode(tool_list)
    secure_tools = _build_secure_tool_node(raw_tool_node)

    graph = StateGraph(AgentState)
    graph.add_node("reason", reason)
    graph.add_node("tools", secure_tools)
    graph.set_entry_point("reason")
    graph.add_conditional_edges(
        "reason", _should_use_tools, {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "reason")

    return graph.compile()
