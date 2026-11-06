"""
NewGenHealthAI — core/langgraph_workflow.py
LangGraph StateGraph definition, routing functions, and workflow factory.
"""

try:
    from langgraph.graph import END, StateGraph
except ImportError:
    END = "__end__"
    StateGraph = None


from app.agents.executor import ExecutorAgent
from app.agents.explanation import ExplanationAgent
from app.agents.llm_agent import LLMAgent
from app.agents.memory import MemoryAgent
from app.agents.planner import PlannerAgent
from app.agents.retriever import RetrieverAgent
from app.agents.tavily import TavilyAgent
from app.agents.triage_agent import TriageAgent
from app.agents.wikipedia import WikipediaAgent
from app.core.state import AgentState


# ── Routing Functions ──────────────────────────────────────────────────────────
def _route_after_planner(state: AgentState) -> str:
    """After planner, immediately route urgent red flags to executor, else triage."""
    if state.get("is_urgent"):
        return "executor"
    return "triage_agent"


def _route_after_triage(state: AgentState) -> str:
    """After triage, either ask follow-up questions, handle urgent alert, or proceed to educational assessment."""
    if state.get("is_urgent") or state.get("triage_status") in ("needs_info", "urgent_risk"):
        # Follow-up questions or emergency advisory are finalized at executor
        return "executor"
    # Ready for educational assessment — use primary tool selected by planner
    return "retriever" if state.get("current_tool") == "retriever" else "llm_agent"


def _route_after_llm(state: AgentState) -> str:
    """Bounded routing after direct LLM: success -> executor; failure -> retriever -> wiki -> tavily -> executor."""
    if state.get("llm_success"):
        return "executor"
    attempted = state.get("attempted_providers", [])
    if "retriever" not in attempted and not state.get("rag_attempted"):
        return "retriever"
    if "wikipedia" not in attempted and not state.get("wiki_attempted"):
        return "wikipedia"
    if "tavily" not in attempted and not state.get("tavily_attempted"):
        return "tavily"
    # All providers exhausted without success — flag for executor to terminate early
    state["exhaustion_reason"] = "all_providers_attempted_after_llm"
    return "executor"


def _route_after_rag(state: AgentState) -> str:
    """Bounded routing after RAG: success -> executor; failure -> llm_agent -> wiki -> tavily -> executor."""
    if state.get("rag_success"):
        return "executor"
    attempted = state.get("attempted_providers", [])
    if "llm_agent" not in attempted and not state.get("llm_attempted"):
        return "llm_agent"
    if "wikipedia" not in attempted and not state.get("wiki_attempted"):
        return "wikipedia"
    if "tavily" not in attempted and not state.get("tavily_attempted"):
        return "tavily"
    # All providers exhausted without success — flag for executor to terminate early
    state["exhaustion_reason"] = "all_providers_attempted_after_rag"
    return "executor"


def _route_after_llm_fallback(state: AgentState) -> str:
    """Fallback route after secondary LLM attempt."""
    if state.get("llm_success"):
        return "executor"
    attempted = state.get("attempted_providers", [])
    if "wikipedia" not in attempted and not state.get("wiki_attempted"):
        return "wikipedia"
    if "tavily" not in attempted and not state.get("tavily_attempted"):
        return "tavily"
    state["exhaustion_reason"] = "all_providers_attempted_after_llm_fallback"
    return "executor"


def _route_after_wiki(state: AgentState) -> str:
    """Bounded routing after Wikipedia: success -> executor; failure -> tavily -> executor."""
    if state.get("wiki_success"):
        return "executor"
    attempted = state.get("attempted_providers", [])
    if "tavily" not in attempted and not state.get("tavily_attempted"):
        return "tavily"
    # Wikipedia and tavily both exhausted
    state["exhaustion_reason"] = "all_providers_attempted_after_wiki"
    return "executor"


def _route_after_tavily(state: AgentState) -> str:
    """Terminal routing after Tavily web search."""
    # Tavily is the last fallback; if it also failed, mark exhaustion
    if not state.get("tavily_success"):
        state["exhaustion_reason"] = "all_providers_attempted_tavily_failed"
    return "executor"


# ── Workflow Factory ───────────────────────────────────────────────────────────
def create_workflow():
    """Build and compile the bounded LangGraph agentic workflow."""
    workflow = StateGraph(AgentState)

    # Register nodes
    workflow.add_node("memory", MemoryAgent)
    workflow.add_node("planner", PlannerAgent)
    workflow.add_node("triage_agent", TriageAgent)
    workflow.add_node("llm_agent", LLMAgent)
    workflow.add_node("retriever", RetrieverAgent)
    workflow.add_node("wikipedia", WikipediaAgent)
    workflow.add_node("tavily", TavilyAgent)
    workflow.add_node("executor", ExecutorAgent)
    workflow.add_node("explanation", ExplanationAgent)

    # Entry point
    workflow.set_entry_point("memory")

    # Edges:  memory → planner
    workflow.add_edge("memory", "planner")

    # Planner routes urgent red flags to executor, normal queries to triage
    workflow.add_conditional_edges(
        "planner",
        _route_after_planner,
        {"executor": "executor", "triage_agent": "triage_agent"},
    )

    # Triage decides: ask follow-up / urgent alert → executor, OR proceed to assessment
    workflow.add_conditional_edges(
        "triage_agent",
        _route_after_triage,
        {"executor": "executor", "retriever": "retriever", "llm_agent": "llm_agent"},
    )

    # Bounded fallback edges: each provider visited at most once per turn
    workflow.add_conditional_edges(
        "llm_agent",
        _route_after_llm,
        {
            "executor": "executor",
            "retriever": "retriever",
            "wikipedia": "wikipedia",
            "tavily": "tavily",
        },
    )
    workflow.add_conditional_edges(
        "retriever",
        _route_after_rag,
        {
            "executor": "executor",
            "llm_agent": "llm_agent",
            "wikipedia": "wikipedia",
            "tavily": "tavily",
        },
    )
    workflow.add_conditional_edges(
        "wikipedia",
        _route_after_wiki,
        {"executor": "executor", "tavily": "tavily"},
    )
    workflow.add_conditional_edges(
        "tavily",
        _route_after_tavily,
        {"executor": "executor"},
    )
    workflow.add_edge("executor", END)

    return workflow.compile()
