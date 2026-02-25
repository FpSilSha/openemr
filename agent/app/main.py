"""AgentForge FastAPI application with lifespan-managed clients and agent graph."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import build_graph
from app.agent.models import get_primary_model, get_verification_model
from app.clients.icd10_client import ICD10Client
from app.clients.openemr import OpenEMRClient
from app.clients.openfda import DrugInteractionClient
from app.clients.pubmed_client import PubMedClient
from app.config import settings
from app.middleware.audit_logger import AuditLogMiddleware
from app.middleware.cost_tracker import CostTrackerMiddleware
from app.persistence.store import SessionStore, get_checkpointer
from app.routes.approve import router as approve_router
from app.routes.chat import router as chat_router
from app.routes.feedback import router as feedback_router
from app.routes.health import router as health_router
from app.tools import allergies as allergies_tool
from app.tools import appointments as appointments_tool
from app.tools import icd10 as icd10_tool
from app.tools import labs as labs_tool
from app.tools import medications as med_tool
from app.tools import patient as patient_tool
from app.tools import pubmed as pubmed_tool
from app.tools import vitals as vitals_tool

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

    # Initialize persistence (SQLite for sessions + LangGraph state)
    db_path = os.environ.get("AGENT_DB_PATH", "/app/data/agent_state.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    session_store = SessionStore(db_path)
    await session_store.init_db()
    checkpointer = await get_checkpointer(db_path)
    app.state.session_store = session_store
    logger.info("SQLite persistence initialized at %s", db_path)

    # Authenticate with OpenEMR (OAuth2 registration + token)
    try:
        await openemr.authenticate()
        logger.info("OpenEMR OAuth2 authentication successful")
    except Exception as e:
        logger.warning("OpenEMR auth failed (tools will retry): %s", e)

    # Inject clients into tool modules
    patient_tool.set_client(openemr)
    labs_tool.set_client(openemr)
    med_tool.set_clients(openemr, drug)
    icd10_tool.set_client(icd10)
    pubmed_tool.set_client(pubmed)
    appointments_tool.set_client(openemr)
    vitals_tool.set_client(openemr)
    allergies_tool.set_client(openemr)

    # Build agent graph with verification model and checkpointer
    model = get_primary_model(settings)
    verify_model = get_verification_model(settings)
    graph = build_graph(
        model, verification_model=verify_model, checkpointer=checkpointer
    )
    app.state.agent_graph = graph

    logger.info("AgentForge started — tools and agent graph ready")
    yield

    # Cleanup
    await session_store.close()
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
app.add_middleware(AuditLogMiddleware)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(approve_router)
app.include_router(feedback_router)
