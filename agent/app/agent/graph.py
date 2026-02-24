"""LangGraph agent graph — reason → tools → reason loop."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.prompts import CLINICAL_ASSISTANT_SYSTEM_PROMPT
from app.agent.state import AgentState
from app.tools import MVP_TOOLS


def _should_use_tools(state: AgentState) -> str:
    """Edge function: route to tools if the last message has tool_calls."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def build_graph(model: ChatAnthropic) -> StateGraph:
    """Build the agent graph with the given model and MVP tools."""
    model_with_tools = model.bind_tools(MVP_TOOLS)

    async def reason(state: AgentState) -> dict:
        """Invoke the LLM with system prompt + conversation history."""
        system = SystemMessage(content=CLINICAL_ASSISTANT_SYSTEM_PROMPT)
        messages = [system] + state["messages"]
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(MVP_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("reason", reason)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("reason")
    graph.add_conditional_edges("reason", _should_use_tools, {"tools": "tools", END: END})
    graph.add_edge("tools", "reason")

    return graph.compile()
