import re

from langchain_core.documents import Document

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.tavily_search import get_tavily_search


def _build_safe_tavily_query(text: str) -> str:
    """Extract safe generic search terms without leaking personal details or narrative."""
    if not text:
        return "medical conditions and symptoms"
    cleaned = re.sub(
        r"\b(?:i\s+have|i\s+am|i\'?m|my|me|patient|he|she|his|her|we|our|the\s+patient\s+reported)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    words = [w for w in re.findall(r"\b[A-Za-z0-9_-]+\b", cleaned) if len(w) > 2]
    safe_terms = " ".join(words[:6]) if words else "medical health"
    return f"{safe_terms} health medical symptoms"


def TavilyAgent(state: AgentState) -> AgentState:
    """Search the web via Tavily for current medical research and news as a bounded fallback."""
    attempted = list(state.get("attempted_providers", []))
    if "tavily" not in attempted:
        attempted.append("tavily")
    state["attempted_providers"] = attempted
    state["tavily_attempted"] = True

    tavily = get_tavily_search()
    if not tavily:
        state["documents"] = []
        state["tavily_success"] = False
        return state

    try:
        search_query = _build_safe_tavily_query(state.get("question", ""))
        results = tavily.invoke(search_query)
    except Exception as e:
        logger.error("Tavily: Search failed: %s", str(e))
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
        logger.info("Tavily: Found %d results", len(valid_results))
    else:
        state["documents"] = []
        state["tavily_success"] = False
        logger.info("Tavily: No valid results")

    return state
