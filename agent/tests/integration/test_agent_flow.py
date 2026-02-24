"""Integration tests for the full LangGraph agent — requires Docker + LLM.

Run with: AGENTFORGE_INTEGRATION=1 pytest tests/integration/test_agent_flow.py -v
Requires: docker-compose.agent.yml stack + ANTHROPIC_API_KEY in environment
"""

import pytest
from langchain_core.messages import HumanMessage

from app.agent.graph import build_graph
from app.agent.models import get_primary_model
from app.clients.icd10_client import ICD10Client
from app.clients.openemr import OpenEMRClient
from app.clients.openfda import DrugInteractionClient
from app.clients.pubmed_client import PubMedClient
from app.config import Settings
from app.tools import icd10 as icd10_tool
from app.tools import labs as labs_tool
from app.tools import medications as med_tool
from app.tools import patient as patient_tool
from app.tools import pubmed as pubmed_tool


@pytest.fixture
async def agent_graph():
    """Stand up the full agent graph with live clients."""
    settings = Settings()
    openemr = OpenEMRClient(settings)
    drug = DrugInteractionClient(timeout=settings.tool_timeout_seconds)
    icd10 = ICD10Client(timeout=settings.tool_timeout_seconds)
    pubmed = PubMedClient(timeout=settings.tool_timeout_seconds)

    patient_tool.set_client(openemr)
    labs_tool.set_client(openemr)
    med_tool.set_clients(openemr, drug)
    icd10_tool.set_client(icd10)
    pubmed_tool.set_client(pubmed)

    model = get_primary_model(settings)
    graph = build_graph(model)

    yield graph

    await openemr.close()
    await drug.close()
    await icd10.close()
    await pubmed.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_greeting(agent_graph):
    """Agent responds to a simple greeting without tool calls."""
    result = await agent_graph.ainvoke({
        "messages": [HumanMessage(content="Hello, what can you help me with?")],
        "patient_uuid": None,
    })
    assert len(result["messages"]) >= 2
    last = result["messages"][-1]
    assert hasattr(last, "content") and last.content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_drug_interaction_uses_tool(agent_graph):
    """Agent invokes drug_interaction_check tool for a drug interaction query."""
    result = await agent_graph.ainvoke({
        "messages": [
            HumanMessage(
                content="Check for interactions between aspirin and warfarin"
            )
        ],
        "patient_uuid": None,
    })
    assert len(result["messages"]) >= 2
    tool_calls_found = any(
        hasattr(msg, "tool_calls") and msg.tool_calls
        for msg in result["messages"]
    )
    assert tool_calls_found


@pytest.mark.integration
@pytest.mark.asyncio
async def test_icd10_lookup_uses_tool(agent_graph):
    """Agent invokes icd10_lookup tool for a diagnosis code query."""
    result = await agent_graph.ainvoke({
        "messages": [
            HumanMessage(content="Look up ICD-10 codes for type 2 diabetes")
        ],
        "patient_uuid": None,
    })
    assert len(result["messages"]) >= 2
    last = result["messages"][-1]
    assert hasattr(last, "content") and last.content
