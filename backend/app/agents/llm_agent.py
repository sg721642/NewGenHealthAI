"""
NewGenHealthAI — agents/llm_agent.py
LLMAgent: generates a direct response from the LLM without RAG.
Enhanced with better prompting for comprehensive medical responses.
"""

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.llm_client import get_llm


def LLMAgent(state: AgentState) -> AgentState:
    """Generate a response directly from the LLM (no retrieval)."""
    llm = get_llm()
    if not llm:
        state["llm_success"] = False
        state["llm_attempted"] = True
        state["generation"] = "Medical AI service is temporarily unavailable."
        return state

    # Build conversation context
    history_context = ""
    for item in state.get("conversation_history", [])[-5:]:
        if item.get("role") == "user":
            history_context += f"Patient: {item.get('content', '')}\n"
        elif item.get("role") == "assistant":
            history_context += f"Doctor: {item.get('content', '')}\n"

    # Check if this is a post-triage enriched question
    collected = state.get("collected_symptoms", [])
    triage_round = state.get("triage_round", 0)

    if triage_round > 0 and collected:
        # Post-triage: give comprehensive response
        collected_text = "\n".join(f"  - {s}" for s in collected)
        prompt = (
            "You are NewGenHealthAI, an experienced clinical physician. "
            "You completed a clinical interview and gathered these details:\n\n"
            f"PATIENT INFORMATION:\n{collected_text}\n\n"
            f"Conversation:\n{history_context}\n\n"
            "Provide a COMPREHENSIVE medical assessment with:\n"
            "## 🩺 Clinical Assessment\n"
            "Brief summary of the patient's condition.\n\n"
            "## 🔍 Possible Diagnoses\n"
            "Top 2-3 likely conditions with explanations.\n\n"
            "## 💊 Recommended Treatment\n"
            "Medications, dosage guidance, and non-drug treatments.\n\n"
            "## 🏠 Home Remedies & Self-Care\n"
            "Practical home remedies and lifestyle adjustments.\n\n"
            "## ⚠️ When to See a Doctor\n"
            "Red flag symptoms requiring urgent attention.\n\n"
            "Be thorough, professional, and caring. Use bullet points."
        )
    else:
        # Standard query
        prompt = (
            "You are a compassionate and knowledgeable medical AI assistant.\n\n"
            f"Conversation History:\n{history_context}\n"
            f"Current Patient Question:\n{state['question']}\n\n"
            "Provide a helpful, detailed medical response. Be clear, professional, and caring. "
            "Use markdown formatting with headers and bullet points for clarity. "
            "Include practical advice and when to seek professional help."
        )

    response = llm.invoke(prompt)
    answer = (
        response.content.strip()
        if hasattr(response, "content")
        else str(response).strip()
    )

    if answer and len(answer) > 10:
        state["generation"] = answer
        state["llm_success"] = True
        state["source"] = "AI Medical Knowledge"
        logger.info("LLM: Generated response successfully")
    else:
        state["llm_success"] = False
        logger.warning("LLM: Response too short or empty")

    state["llm_attempted"] = True
    return state
