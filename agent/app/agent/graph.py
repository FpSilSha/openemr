"""LangGraph agent graph — reason → tools → reason → verify loop."""

from __future__ import annotations

import copy
import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.agent.prompts import CLINICAL_ASSISTANT_SYSTEM_PROMPT
from app.agent.state import AgentState
from app.tools import ALL_TOOLS
from app.verification import run_verification

logger = logging.getLogger(__name__)

# Maximum verification retries before accepting with caveats
_MAX_VERIFY_ATTEMPTS = 1

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
    return "verify"


def _should_retry_or_end(state: AgentState) -> str:
    """Edge function: retry reasoning if verification failed, else end."""
    attempts = state.get("verification_attempts", 0)
    last = state["messages"][-1]

    # If verification passed (no feedback appended), go to END
    if isinstance(last, AIMessage):
        return END

    # If we've exhausted retries, accept with caveats
    if attempts >= _MAX_VERIFY_ATTEMPTS:
        return END

    return "reason"


def _build_secure_tool_node(tool_node: ToolNode):
    """Wrap ToolNode to enforce session-bound patient_uuid."""

    async def secure_tool_node(state: AgentState) -> dict[str, Any]:
        """Override patient_uuid in tool args with session-bound value."""
        patient_ctx = state.get("patient_context")
        if patient_ctx and patient_ctx.get("uuid"):
            session_uuid = patient_ctx["uuid"]
            last = state["messages"][-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                # Deep copy to avoid mutating the original message
                patched = copy.deepcopy(state)
                patched_last = patched["messages"][-1]
                if isinstance(patched_last, AIMessage):
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
                result: dict[str, Any] = await tool_node.ainvoke(patched)
                return result
        result = await tool_node.ainvoke(state)
        return result  # type: ignore[return-value]

    return secure_tool_node


def build_graph(
    model: ChatAnthropic,
    tools: list | None = None,
    verification_model: ChatAnthropic | None = None,
    checkpointer: Any | None = None,
) -> CompiledStateGraph:
    """Build the agent graph with the given model, tools, and verification.

    Args:
        model: ChatAnthropic model instance for primary reasoning.
        tools: List of LangChain tools to bind. Defaults to ALL_TOOLS.
        verification_model: Optional model for hallucination checks.
        checkpointer: Optional LangGraph checkpointer for state persistence.
    """
    tool_list = tools if tools is not None else ALL_TOOLS
    model_with_tools = model.bind_tools(tool_list)

    async def reason(state: AgentState) -> dict:
        """Invoke the LLM with system prompt + conversation history."""
        prompt = CLINICAL_ASSISTANT_SYSTEM_PROMPT
        patient_ctx = state.get("patient_context")
        if patient_ctx and patient_ctx.get("uuid"):
            prompt += (
                f"\n\n## Current Patient Context\n"
                f"Patient UUID: {patient_ctx['uuid']}\n"
                f"Use this UUID for all patient data lookups in this conversation."
            )
        system = SystemMessage(content=prompt)
        messages = [system] + state["messages"]
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def verify(state: AgentState) -> dict:
        """Run verification checks on the agent's response."""
        result = await run_verification(
            state["messages"],
            verification_model=verification_model,
        )

        if result["passed"]:
            return {}

        # Build feedback for the agent about what failed
        failed_checks = [
            f"- {name}: {check['reason']}"
            for name, check in result["checks"].items()
            if not check["passed"]
        ]
        feedback = (
            "Verification found issues with your response. "
            "Please address and revise:\n"
            + "\n".join(failed_checks)
        )

        attempts = state.get("verification_attempts", 0) + 1
        return {
            "messages": [SystemMessage(content=feedback)],
            "verification_attempts": attempts,
        }

    raw_tool_node = ToolNode(tool_list)
    secure_tools = _build_secure_tool_node(raw_tool_node)

    graph = StateGraph(AgentState)
    graph.add_node("reason", reason)
    graph.add_node("tools", secure_tools)
    graph.add_node("verify", verify)
    graph.set_entry_point("reason")
    graph.add_conditional_edges(
        "reason",
        _should_use_tools,
        {"tools": "tools", "verify": "verify"},
    )
    graph.add_edge("tools", "reason")
    graph.add_conditional_edges(
        "verify",
        _should_retry_or_end,
        {"reason": "reason", END: END},
    )

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
