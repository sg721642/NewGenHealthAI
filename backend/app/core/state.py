"""
NewGenHealthAI — core/state.py
AgentState TypedDict and state helper functions.
"""

from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.documents import Document


class AgentState(TypedDict):
    """Shared state passed between all LangGraph agent nodes."""

    question: str
    documents: List[Document]
    generation: str
    source: str
    search_query: Optional[str]
    conversation_history: List[Dict]
    llm_attempted: bool
    llm_success: bool
    rag_attempted: bool
    rag_success: bool
    wiki_attempted: bool
    wiki_success: bool
    tavily_attempted: bool
    tavily_success: bool
    current_tool: Optional[str]
    retry_count: int

    # ── Clinical Triage (Follow-Up Questions) ──────────────────────
    triage_status: Optional[str]        # "needs_info" | "ready_to_diagnose" | "urgent_risk" | None
    triage_round: int                   # how many Q&A rounds so far (max 3)
    collected_symptoms: List[str]       # accumulated patient details across turns
    questions_asked: List[str]          # exact questions already asked (to avoid repeats)
    follow_up_data: Optional[Dict[str, Any]]  # structured follow-up for frontend chips
    is_medical_query: bool              # whether planner flagged this as medical

    # ── Phase 2B: Urgent Risk & Bounded Workflow Safeguards ─────────
    is_urgent: bool                     # whether acute red flag emergency was detected
    urgent_advisory: Optional[str]      # deterministic emergency message
    urgent_category: Optional[str]      # e.g. "cardiac", "stroke", "respiratory", etc.
    attempted_providers: List[str]      # tracks visited tools to enforce single-visit budget per turn
    fallback_history: List[str]         # sequential log of provider fallback transitions
    is_failed_generation: bool          # whether all providers failed (service unavailable)
    exhaustion_reason: Optional[str]    # reason for provider exhaustion
    uncertainty_acknowledged: bool      # whether clinical uncertainty is explicitly acknowledged


def initialize_conversation_state() -> AgentState:
    """Return a fresh AgentState with all fields at their defaults."""
    return {
        "question": "",
        "documents": [],
        "generation": "",
        "source": "",
        "search_query": None,
        "conversation_history": [],
        "llm_attempted": False,
        "llm_success": False,
        "rag_attempted": False,
        "rag_success": False,
        "wiki_attempted": False,
        "wiki_success": False,
        "tavily_attempted": False,
        "tavily_success": False,
        "current_tool": None,
        "retry_count": 0,
        # Triage
        "triage_status": None,
        "triage_round": 0,
        "collected_symptoms": [],
        "questions_asked": [],
        "follow_up_data": None,
        "is_medical_query": False,
        # Phase 2B Safeguards
        "is_urgent": False,
        "urgent_advisory": None,
        "urgent_category": None,
        "attempted_providers": [],
        "fallback_history": [],
        "is_failed_generation": False,
        "exhaustion_reason": None,
        "uncertainty_acknowledged": False,
    }


def reset_query_state(state: AgentState) -> AgentState:
    """Reset per-query flags while preserving conversation history and triage context."""
    state.update(
        {
            "question": "",
            "documents": [],
            "generation": "",
            "source": "",
            "search_query": None,
            "llm_attempted": False,
            "llm_success": False,
            "rag_attempted": False,
            "rag_success": False,
            "wiki_attempted": False,
            "wiki_success": False,
            "tavily_attempted": False,
            "tavily_success": False,
            "current_tool": None,
            "retry_count": 0,
            # Keep triage_round and collected_symptoms across turns!
            # Only reset follow_up_data and triage_status per query
            "triage_status": None,
            "follow_up_data": None,
            # Reset per-query Phase 2B flags
            "is_urgent": False,
            "urgent_advisory": None,
            "urgent_category": None,
            "attempted_providers": [],
            "fallback_history": [],
            "is_failed_generation": False,
            "exhaustion_reason": None,
            "uncertainty_acknowledged": False,
        }
    )
    return state
