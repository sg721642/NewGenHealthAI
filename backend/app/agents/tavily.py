"""
NewGenHealthAI — agents/tavily.py
TavilyAgent: web search fallback using Tavily.

Privacy Rules:
  1. External search is DISABLED unless TAVILY_API_KEY is configured.
  2. Only allowlisted generic medical vocabulary is used to build the outbound
     search query — personal symptom narratives are never forwarded.
  3. If no recognised medical term can be extracted the agent declines to search.
"""

import re
from typing import Optional

from langchain_core.documents import Document

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.tavily_search import get_tavily_search

# ── Shared allowlisted medical term vocabulary (mirrors wikipedia.py) ─────────
# Only terms from this set are forwarded to the external Tavily search API.
_MEDICAL_TERM_ALLOWLIST = frozenset({
    "heart", "cardiac", "cardiovascular", "lung", "pulmonary", "respiratory",
    "brain", "neurological", "neurology", "liver", "hepatic", "kidney", "renal",
    "stomach", "gastrointestinal", "intestinal", "bowel", "colon", "rectal",
    "skin", "dermatology", "musculoskeletal", "bone", "joint", "muscle",
    "blood", "hematology", "immune", "endocrine", "thyroid", "hormonal",
    "fever", "pain", "headache", "fatigue", "nausea", "vomiting", "diarrhea",
    "constipation", "cough", "dyspnea", "breathlessness", "palpitation",
    "dizziness", "vertigo", "rash", "swelling", "edema", "inflammation",
    "infection", "allergy", "anemia", "hypertension", "hypotension", "diabetes",
    "obesity", "insomnia", "anxiety", "depression",
    "asthma", "pneumonia", "bronchitis", "sinusitis", "migraine", "epilepsy",
    "arthritis", "osteoporosis", "hypothyroidism", "hyperthyroidism", "gerd",
    "ibs", "crohns", "colitis", "psoriasis", "eczema", "urticaria",
    "stroke", "angina", "arrhythmia", "atherosclerosis",
    "symptom", "symptoms", "diagnosis", "treatment", "medication", "therapy",
    "prevention", "prognosis", "chronic", "acute", "benign", "malignant",
    "cancer", "tumor", "autoimmune", "congenital", "genetic", "hereditary",
    "virus", "bacteria", "fungal", "parasitic", "viral", "bacterial",
    "vaccine", "antibiotic", "antiviral", "supplement", "vitamin", "mineral",
    "nutrition", "exercise", "lifestyle", "diet",
})

_WORD_RE = re.compile(r"\b[A-Za-z]{3,}\b")


def _build_privacy_preserving_query(text: str) -> Optional[str]:
    """
    Extract only allowlisted generic medical terms from user text.

    Returns a sanitized query string suitable for external search, or None if
    no recognised medical terms are present.  Never falls back to raw question text.
    """
    if not text:
        return None

    matched_terms = []
    seen: set = set()
    for word in _WORD_RE.findall(text):
        lower = word.lower()
        if lower in _MEDICAL_TERM_ALLOWLIST and lower not in seen:
            matched_terms.append(lower)
            seen.add(lower)
        if len(matched_terms) >= 5:
            break

    if not matched_terms:
        return None

    return " ".join(matched_terms) + " health information"


def TavilyAgent(state: AgentState) -> AgentState:
    """Search the web via Tavily for current medical research as a bounded privacy-preserving fallback."""
    attempted = list(state.get("attempted_providers", []))
    if "tavily" not in attempted:
        attempted.append("tavily")
    state["attempted_providers"] = attempted
    state["tavily_attempted"] = True

    tavily = get_tavily_search()
    if not tavily:
        # Tavily disabled (no API key configured) — skip external search silently.
        logger.info("Tavily: search disabled (API key not configured or client unavailable)")
        state["documents"] = []
        state["tavily_success"] = False
        return state

    search_query = _build_privacy_preserving_query(state.get("question", ""))

    if not search_query:
        # No generic medical terms extractable — do not forward query externally.
        logger.info("Tavily: no allowlisted medical terms found; skipping external search")
        state["documents"] = []
        state["tavily_success"] = False
        return state

    try:
        results = tavily.invoke(search_query)
    except Exception as e:
        # Redact exception — may echo query or contain credential fragments.
        logger.error("Tavily: search failed (%s)", type(e).__name__)
        results = []

    valid_results = [
        r
        for r in (results or [])
        if isinstance(r, dict) and r.get("content") and len(r["content"].strip()) > 50
    ]

    if valid_results:
        state["documents"] = [
            Document(
                page_content=r["content"],
                metadata={"url": r.get("url", ""), "title": r.get("title", "")},
            )
            for r in valid_results
        ]
        state["tavily_success"] = True
        state["source"] = "Current Medical Research & News"
        logger.info("Tavily: retrieved %d results (query_terms=%d)", len(valid_results), len(search_query.split()))
    else:
        state["documents"] = []
        state["tavily_success"] = False
        logger.info("Tavily: no valid results for sanitized query")

    return state
