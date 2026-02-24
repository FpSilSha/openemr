"""AgentForge LangChain tool registry."""

from app.tools.allergies import get_allergies_detailed
from app.tools.appointments import get_appointments
from app.tools.clinical_notes import create_clinical_note
from app.tools.icd10 import icd10_lookup
from app.tools.labs import get_lab_results
from app.tools.medications import drug_interaction_check, get_medications
from app.tools.patient import get_patient_summary, search_patients
from app.tools.pubmed import pubmed_search
from app.tools.vitals import get_vitals

MVP_TOOLS = [
    get_patient_summary,
    search_patients,
    get_medications,
    drug_interaction_check,
    get_lab_results,
    icd10_lookup,
    pubmed_search,
]

ALL_TOOLS = MVP_TOOLS + [
    get_appointments,
    get_vitals,
    get_allergies_detailed,
    create_clinical_note,
]

__all__ = ["MVP_TOOLS", "ALL_TOOLS"]
