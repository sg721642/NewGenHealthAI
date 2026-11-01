import re

from langchain_core.documents import Document

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.wikipedia_search import get_wikipedia_wrapper


def _build_safe_search_query(text: str) -> str:
    """Extract safe generic search terms without leaking personal pronouns or context."""
    if not text:
        return "general health symptoms"
    # Remove common personal narrative tokens
    cleaned = re.sub(
        r"\b(?:i\s+have|i\s+am|i\'?m|my|me|patient|he|she|his|her|we|our|the\s+patient\s+reported)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    words = [w for w in re.findall(r"\b[A-Za-z0-9_-]+\b", cleaned) if len(w) > 2]
    safe_terms = " ".join(words[:6]) if words else "health condition"
    return f"{safe_terms} medical"


def WikipediaAgent(state: AgentState) -> AgentState:
    """Search Wikipedia for medical information as a bounded fallback source."""
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

    try:
        search_query = _build_safe_search_query(state.get("question", ""))
        content = wiki.run(search_query)

        # Retry with raw question if first search is too short (up to 10 words max to prevent leak)
        if not content or len(content.strip()) < 100:
            short_query = " ".join(state.get("question", "").split()[:10])
            content = wiki.run(short_query)

        if content and len(content.strip()) > 100:
            state["documents"] = [
                Document(
                    page_content=content[:2000],
                    metadata={"source": "Wikipedia", "title": search_query},
                )
            ]
            state["wiki_success"] = True
            state["source"] = "Wikipedia Medical Information"
            logger.info("Wikipedia: Found relevant content")
        else:
            state["documents"] = []
            state["wiki_success"] = False
            logger.info("Wikipedia: No relevant content found")

    except Exception as e:
        logger.error("Wikipedia: Search failed: %s", str(e))
        state["documents"] = []
        state["wiki_success"] = False

    return state
