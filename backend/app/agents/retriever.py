import re
from typing import List

from langchain_core.documents import Document

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.vector_store import get_retriever

PROMPT_INJECTION_PATTERN = re.compile(
    r"(?i)(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|<\|im_start\|>|<\|im_end\|>|<system>|</system>|\[INST\]|\[/INST\])",
    re.IGNORECASE,
)


def _sanitize_document_content(content: str) -> str:
    """Sanitize retrieved content to protect downstream LLM generation from prompt injections."""
    if not content:
        return ""
    return PROMPT_INJECTION_PATTERN.sub("[sanitized]", content)


def RetrieverAgent(state: AgentState) -> AgentState:
    """Retrieve relevant documents from the ChromaDB vector store."""
    attempted = list(state.get("attempted_providers", []))
    if "retriever" not in attempted:
        attempted.append("retriever")
    state["attempted_providers"] = attempted
    state["rag_attempted"] = True

    retriever = get_retriever()
    if not retriever:
        logger.warning("RAG: No retriever available — vector store not initialized or dependencies missing")
        state["documents"] = []
        state["rag_success"] = False
        state["rag_status"] = "unavailable"
        return state

    try:
        # Build context-enriched query from recent conversation
        context_parts = [
            f"Context: {item.get('content', '')}"
            for item in state.get("conversation_history", [])[-3:]
            if item.get("role") == "user"
        ]
        context = " | ".join(context_parts)
        combined_query = f"{state['question']} {context}" if context else state["question"]

        docs = retriever.invoke(combined_query)
        valid_docs = []
        if docs:
            for d in docs:
                cleaned = _sanitize_document_content(d.page_content.strip())
                if len(cleaned) > 50:
                    valid_docs.append(Document(page_content=cleaned, metadata=getattr(d, "metadata", {}) or {}))

        if valid_docs:
            state["documents"] = valid_docs
            state["rag_success"] = True
            state["rag_status"] = "success"
            state["source"] = "Medical Literature Database"
            logger.info("RAG: Found %d relevant documents", len(valid_docs))
        else:
            state["documents"] = []
            state["rag_success"] = False
            state["rag_status"] = "no_documents_found"
            logger.info("RAG: No valid documents found")

    except Exception as e:
        logger.error("RAG: Retrieval failed: %s", str(e))
        state["documents"] = []
        state["rag_success"] = False

    return state
