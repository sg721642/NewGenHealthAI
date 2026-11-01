"""
NewGenHealthAI — agents/planner.py
PlannerAgent: decides whether to use RAG retriever or direct LLM.

KEY FIX: If we're already in a triage session (triage_round > 0),
force is_medical_query=True so the user's follow-up answers stay
in the triage flow instead of being treated as a new query.
"""

from app.core.state import AgentState
from app.core.urgent_care import check_urgent_risk

# ── Medical Keywords ───────────────────────────────────────────────────────────
MEDICAL_KEYWORDS = [
    # Symptoms
    "fever", "pain", "headache", "nausea", "vomiting", "diarrhea", "cough",
    "acne", "pimple", "skin", "rash", "itch", "cold", "flu",
    "shortness of breath", "chest pain", "abdominal pain", "back pain",
    "joint pain", "muscle pain", "fatigue", "weakness", "dizziness",
    "confusion", "memory loss", "seizure", "numbness", "tingling", "swelling",
    "bleeding", "bruising", "weight loss", "weight gain",
    "appetite loss", "sleep problems", "insomnia",
    # Conditions
    "cancer", "diabetes", "hypertension", "heart disease", "stroke", "asthma",
    "copd", "pneumonia", "bronchitis", "covid", "coronavirus",
    "infection", "virus", "bacteria", "fungal", "arthritis", "osteoporosis",
    "thyroid", "kidney disease", "liver disease", "hepatitis", "depression",
    "anxiety", "bipolar", "schizophrenia", "alzheimer", "parkinson", "epilepsy",
    # Medical terms
    "treatment", "therapy", "medication", "medicine", "prescription", "dosage",
    "side effects", "diagnosis", "prognosis", "surgery", "operation",
    "procedure", "test", "lab results", "blood test", "x-ray", "mri",
    "ct scan", "ultrasound", "biopsy", "screening", "prevention", "vaccine",
    "immunization", "rehabilitation", "recovery", "chronic", "acute",
    "syndrome", "disorder", "symptom", "cure", "remedy", "doctor", "hospital",
    # Body parts
    "heart", "lung", "kidney", "liver", "brain", "stomach", "intestine",
    "blood", "bone", "muscle", "nerve", "eye", "ear", "throat",
    "neck", "spine", "joint", "head", "chest", "abdomen", "leg", "arm",
    # Severity / duration words (patient answers)
    "mild", "moderate", "severe", "throbbing", "sharp", "dull",
    "chronic", "recurring", "worse", "better", "days", "weeks", "hours",
]


def PlannerAgent(state: AgentState) -> AgentState:
    """Decide whether to route to urgent escalation, RAG retriever, or direct LLM."""
    raw_question = state.get("question", "")

    # 1. First-priority check: acute emergency red flags
    urgent_result = check_urgent_risk(raw_question)
    if urgent_result and urgent_result.get("is_urgent"):
        state["is_urgent"] = True
        state["urgent_category"] = urgent_result["category"]
        state["urgent_advisory"] = urgent_result["advisory"]
        state["generation"] = urgent_result["advisory"]
        state["source"] = "Urgent Medical Alert"
        state["triage_status"] = "urgent_risk"
        state["current_tool"] = "executor"
        state["is_medical_query"] = True
        state["retry_count"] = 0
        return state

    question = raw_question.lower()
    triage_round = state.get("triage_round", 0)

    # If we're already in a triage session, this is a follow-up answer
    # → Force medical query so triage continues asking questions
    if triage_round > 0:
        state["current_tool"] = "retriever"
        state["is_medical_query"] = True
        state["retry_count"] = 0
        return state

    contains_medical = any(kw in question for kw in MEDICAL_KEYWORDS)
    state["current_tool"] = "retriever" if contains_medical else "llm_agent"
    state["is_medical_query"] = contains_medical
    state["retry_count"] = 0
    return state
