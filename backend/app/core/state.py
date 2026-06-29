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
    triage_status: Optional[str]        # "needs_info" | "ready_to_diagnose" | None
    triage_round: int                   # how many Q&A rounds so far (max 3)
    collected_symptoms: List[str]       # accumulated patient details across turns
    questions_asked: List[str]          # exact questions already asked (to avoid repeats)
    follow_up_data: Optional[Dict[str, Any]]  # structured follow-up for frontend chips
    is_medical_query: bool              # whether planner flagged this as medical


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
        }
    )
    return state
