"""AgentForge LangChain tool registry."""

from app.tools.icd10 import icd10_lookup
from app.tools.labs import get_lab_results
from app.tools.medications import drug_interaction_check, get_medications
from app.tools.patient import get_patient_summary, search_patients
from app.tools.pubmed import pubmed_search

MVP_TOOLS = [
    get_patient_summary,
    search_patients,
    get_medications,
    drug_interaction_check,
    get_lab_results,
    icd10_lookup,
    pubmed_search,
]

__all__ = ["MVP_TOOLS"]
