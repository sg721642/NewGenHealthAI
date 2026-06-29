"""
NewGenHealthAI — core/langgraph_workflow.py
LangGraph StateGraph definition, routing functions, and workflow factory.
"""

from langgraph.graph import END, StateGraph

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
    """After planner, always go to triage for clinical interview."""
    return "triage_agent"


def _route_after_triage(state: AgentState) -> str:
    """After triage, either ask follow-up questions or proceed to diagnosis."""
    if state.get("triage_status") == "needs_info":
        # Follow-up questions are the response — go to executor to finalize
        return "executor"
    # Ready to diagnose — use the planner's original routing
    return "retriever" if state.get("current_tool") == "retriever" else "llm_agent"


def _route_after_llm(state: AgentState) -> str:
    return "executor" if state.get("llm_success") else "retriever"


def _route_after_rag(state: AgentState) -> str:
    return "executor" if state.get("rag_success") else "llm_agent"


def _route_after_llm_fallback(state: AgentState) -> str:
    return "executor" if state.get("llm_success") else "wikipedia"


def _route_after_wiki(state: AgentState) -> str:
    return "executor" if state.get("wiki_success") else "tavily"


def _route_after_tavily(state: AgentState) -> str:
    return "executor"


# ── Workflow Factory ───────────────────────────────────────────────────────────
def create_workflow():
    """Build and compile the LangGraph agentic workflow."""
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

    # Edges:  memory → planner → triage → (follow-up OR diagnosis pipeline)
    workflow.add_edge("memory", "planner")

    # Planner always routes to triage
    workflow.add_conditional_edges(
        "planner",
        _route_after_planner,
        {"triage_agent": "triage_agent"},
    )

    # Triage decides: ask follow-up → executor, OR proceed to diagnosis
    workflow.add_conditional_edges(
        "triage_agent",
        _route_after_triage,
        {"executor": "executor", "retriever": "retriever", "llm_agent": "llm_agent"},
    )

    workflow.add_conditional_edges(
        "llm_agent",
        _route_after_llm,
        {"executor": "executor", "retriever": "retriever"},
    )
    workflow.add_conditional_edges(
        "retriever",
        _route_after_rag,
        {"executor": "executor", "llm_agent": "llm_agent"},
    )
    workflow.add_conditional_edges(
        "wikipedia",
        _route_after_wiki,
        {"executor": "executor", "tavily": "tavily"},
    )
    workflow.add_conditional_edges(
        "tavily", _route_after_tavily, {"executor": "executor"}
    )
    workflow.add_edge("executor", END)

    return workflow.compile()
