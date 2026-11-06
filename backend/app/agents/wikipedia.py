"""
NewGenHealthAI — agents/wikipedia.py
WikipediaAgent: searches Wikipedia using a privacy-preserving query.

Privacy Rule:
  Raw patient questions and symptom narratives MUST NOT be forwarded to
  external public search services.  Only generic, allowlisted medical
  vocabulary is used to construct the outbound search query.
  If no recognised medical term can be extracted the agent declines to search
  rather than falling back to unredacted question text.
"""

import re
from typing import Optional

from langchain_core.documents import Document

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.wikipedia_search import get_wikipedia_wrapper

# ── Allowlisted generic medical vocabulary ────────────────────────────────────
# Only terms from this set are forwarded to the external Wikipedia API.
# Expanding this list is the ONLY approved way to broaden external query scope.
_MEDICAL_TERM_ALLOWLIST = frozenset({
    # Body systems / anatomy
    "heart", "cardiac", "cardiovascular", "lung", "pulmonary", "respiratory",
    "brain", "neurological", "neurology", "liver", "hepatic", "kidney", "renal",
    "stomach", "gastrointestinal", "intestinal", "bowel", "colon", "rectal",
    "skin", "dermatology", "musculoskeletal", "bone", "joint", "muscle",
    "blood", "hematology", "immune", "endocrine", "thyroid", "hormonal",
    # Common symptom categories (generic)
    "fever", "pain", "headache", "fatigue", "nausea", "vomiting", "diarrhea",
    "constipation", "cough", "dyspnea", "breathlessness", "palpitation",
    "dizziness", "vertigo", "rash", "swelling", "edema", "inflammation",
    "infection", "allergy", "anemia", "hypertension", "hypotension", "diabetes",
    "obesity", "insomnia", "anxiety", "depression",
    # Common condition categories
    "asthma", "pneumonia", "bronchitis", "sinusitis", "migraine", "epilepsy",
    "arthritis", "osteoporosis", "hypothyroidism", "hyperthyroidism", "gerd",
    "ibs", "crohns", "colitis", "psoriasis", "eczema", "urticaria",
    "hypertension", "stroke", "angina", "arrhythmia", "atherosclerosis",
    # Medical / clinical generic terms
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

    Returns a sanitized query string, or None if no medical terms are found.
    Never falls back to raw question text.
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
        return None  # No recognised medical terms — decline to search externally

    return " ".join(matched_terms) + " medical information"


def WikipediaAgent(state: AgentState) -> AgentState:
    """Search Wikipedia for medical information as a bounded privacy-preserving fallback source."""
    attempted = list(state.get("attempted_providers", []))
    if "wikipedia" not in attempted:
        attempted.append("wikipedia")
    state["attempted_providers"] = attempted
    state["wiki_attempted"] = True

    wiki = get_wikipedia_wrapper()
    if not wiki:
        state["documents"] = []
        state["wiki_success"] = False
        return state

    search_query = _build_privacy_preserving_query(state.get("question", ""))

    if not search_query:
        # No generic medical terms extractable — do not forward query externally.
        logger.info("Wikipedia: no allowlisted medical terms found; skipping external search")
        state["documents"] = []
        state["wiki_success"] = False
        return state

    try:
        content = wiki.run(search_query)
        # NOTE: No raw-question retry fallback — that would leak personal medical context.

        if content and len(content.strip()) > 100:
            state["documents"] = [
                Document(
                    page_content=content[:2000],
                    metadata={"source": "Wikipedia", "title": search_query},
                )
            ]
            state["wiki_success"] = True
            state["source"] = "Wikipedia Medical Information"
            logger.info("Wikipedia: retrieved content (query_terms=%d)", len(search_query.split()))
        else:
            state["documents"] = []
            state["wiki_success"] = False
            logger.info("Wikipedia: no relevant content found for sanitized query")

    except Exception as e:
        # Redact exception — may contain search-provider error details with query echoes.
        logger.error("Wikipedia: search failed (%s)", type(e).__name__)
        state["documents"] = []
        state["wiki_success"] = False

    return state
