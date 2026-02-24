"""AgentForge FastAPI application with lifespan-managed clients and agent graph."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import build_graph
from app.agent.models import get_primary_model
from app.clients.icd10_client import ICD10Client
from app.clients.openemr import OpenEMRClient
from app.clients.openfda import DrugInteractionClient
from app.clients.pubmed_client import PubMedClient
from app.config import settings
from app.middleware.cost_tracker import CostTrackerMiddleware
from app.routes.chat import router as chat_router
from app.routes.feedback import router as feedback_router
from app.routes.health import router as health_router
from app.tools import icd10 as icd10_tool
from app.tools import labs as labs_tool
from app.tools import medications as med_tool
from app.tools import patient as patient_tool
from app.tools import pubmed as pubmed_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize clients, inject into tools, build agent graph."""
    # Create clients
    openemr = OpenEMRClient(settings)
    drug = DrugInteractionClient(timeout=settings.tool_timeout_seconds)
    icd10 = ICD10Client(timeout=settings.tool_timeout_seconds)
    pubmed = PubMedClient(
        api_key=settings.pubmed_api_key,
        timeout=settings.tool_timeout_seconds,
    )

    # Inject clients into tool modules
    patient_tool.set_client(openemr)
    labs_tool.set_client(openemr)
    med_tool.set_clients(openemr, drug)
    icd10_tool.set_client(icd10)
    pubmed_tool.set_client(pubmed)

    # Build agent graph
    model = get_primary_model(settings)
    graph = build_graph(model)
    app.state.agent_graph = graph

    logger.info("AgentForge started — tools and agent graph ready")
    yield

    # Cleanup
    await openemr.close()
    await drug.close()
    await icd10.close()
    await pubmed.close()
    logger.info("AgentForge shutdown — clients closed")


app = FastAPI(title="AgentForge OpenEMR Clinical AI Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CostTrackerMiddleware)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(feedback_router)
