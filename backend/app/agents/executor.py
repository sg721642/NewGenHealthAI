"""
NewGenHealthAI — agents/executor.py
ExecutorAgent: synthesizes the final response using the LLM and gathered context.

When triage has collected symptoms across multiple rounds, the executor generates
a comprehensive, doctor-quality diagnosis with differential diagnosis, treatment
options, home remedies, and urgency guidance.
"""

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.llm_client import get_llm


def ExecutorAgent(state: AgentState) -> AgentState:
    """Synthesize the final patient response from retrieved documents or LLM knowledge."""

    # ── If triage is asking follow-up questions, pass through as-is ─────
    if state.get("triage_status") == "needs_info" and state.get("generation"):
        logger.info("Executor: Triage follow-up — pass-through (round %s)",
                     state.get("triage_round", "?"))
        # Append to conversation history so context is preserved
        question = state["question"]
        answer = state["generation"]
        state["conversation_history"].append({"role": "user", "content": question})
        state["conversation_history"].append(
            {"role": "assistant", "content": answer, "source": "Clinical Triage"}
        )
        return state

    # ── Normal diagnosis flow below ────────────────────────────────────
    llm = get_llm()
    question = state["question"]
    source_info = state.get("source", "Unknown")
    triage_round = state.get("triage_round", 0)
    collected_symptoms = state.get("collected_symptoms", [])

    # Build recent conversation context
    history_context = ""
    for item in state.get("conversation_history", [])[-6:]:
        if item.get("role") == "user":
            history_context += f"Patient: {item.get('content', '')}\n"
        elif item.get("role") == "assistant":
            history_context += f"Doctor: {item.get('content', '')}\n"

    if not llm:
        answer = (
            "Medical AI service temporarily unavailable. "
            "Please consult a healthcare professional."
        )
        source_info = "System Message"

    elif triage_round > 0 and collected_symptoms:
        # ── POST-TRIAGE COMPREHENSIVE DIAGNOSIS ────────────────────────
        # This is the "final answer" after the doctor has asked follow-up
        # questions. It should be MUCH more detailed and comprehensive.
        collected_text = "\n".join(f"  - {s}" for s in collected_symptoms)

        # Include RAG documents if available
        doc_context = ""
        if state.get("documents") and len(state["documents"]) > 0:
            doc_context = "\n\n".join(
                [doc.page_content[:1200] for doc in state["documents"][:4]]
            )
            doc_section = f"\n\nMEDICAL LITERATURE (use this to enrich your response):\n{doc_context}"
        else:
            doc_section = ""

        prompt = (
            "You are NewGenHealthAI, an experienced and compassionate clinical physician. "
            "You have just completed a clinical intake interview with the patient and gathered "
            "all the necessary information. Now provide your COMPREHENSIVE medical assessment.\n\n"
            f"CLINICAL INTAKE SUMMARY:\n"
            f"The patient reported the following during your consultation:\n{collected_text}\n\n"
            f"CONVERSATION HISTORY:\n{history_context}\n"
            f"{doc_section}\n\n"
            "Now provide a DETAILED, well-structured medical response. "
            "Format your response EXACTLY like this:\n\n"
            "## 🩺 Clinical Assessment\n"
            "Start with a brief summary of what the patient has described, showing you understand their situation.\n\n"
            "## 🔍 Possible Diagnoses\n"
            "List 2-3 most likely conditions (differential diagnosis) with brief explanations of why each fits. "
            "Rank them from most to least likely.\n\n"
            "## 💊 Recommended Treatment\n"
            "For the most likely diagnosis, provide:\n"
            "- Over-the-counter medications (with dosage guidance)\n"
            "- Prescription options (mention the patient should consult a doctor)\n"
            "- Non-pharmacological treatments\n\n"
            "## 🏠 Home Remedies & Self-Care\n"
            "Practical, actionable home remedies and lifestyle adjustments.\n\n"
            "## ⚠️ When to See a Doctor Immediately\n"
            "Red flag symptoms that require urgent medical attention.\n\n"
            "## 🛡️ Prevention Tips\n"
            "How to prevent recurrence or manage the condition long-term.\n\n"
            "IMPORTANT: Be thorough, caring, and professional. Use bullet points for clarity. "
            "This is the patient's final consultation response — make it count. "
            "Do NOT ask any more questions. Provide definitive guidance."
        )

        try:
            response = llm.invoke(prompt)
            answer = (
                response.content.strip()
                if hasattr(response, "content")
                else str(response).strip()
            )
            source_info = "Clinical Assessment" if not doc_context else "Clinical Assessment + Medical Literature"
            logger.info("Executor: Generated comprehensive post-triage diagnosis")
        except Exception as e:
            logger.error("Executor: Post-triage LLM generation failed: %s", str(e))
            answer = (
                "Based on the symptoms you've described, I recommend consulting with a "
                "healthcare professional for a proper examination and diagnosis. "
                "Please visit your nearest clinic or hospital if symptoms persist or worsen."
            )
            source_info = "System Message"

    elif state.get("documents") and len(state["documents"]) > 0:
        # ── Standard RAG-backed response ───────────────────────────────
        content = "\n\n".join(
            [doc.page_content[:1000] for doc in state["documents"][:3]]
        )
        prompt = (
            "You are an experienced medical doctor providing helpful consultation.\n\n"
            f"Previous Conversation:\n{history_context}\n"
            f"Patient's Current Question:\n{question}\n\n"
            f"Medical Information:\n{content}\n\n"
            "Provide a clear, detailed, caring response. Structure your answer with:\n"
            "- A direct answer to their question\n"
            "- Key medical facts\n"
            "- Practical advice or next steps\n"
            "- When to seek professional help\n\n"
            "Be professional, thorough, and reassuring. Use markdown formatting."
        )
        try:
            response = llm.invoke(prompt)
            answer = (
                response.content.strip()
                if hasattr(response, "content")
                else str(response).strip()
            )
            logger.info("Executor: Generated response from documents")
        except Exception as e:
            logger.error("Executor: LLM generation failed: %s", str(e))
            answer = (
                "I understand your concern about your symptoms. For accurate medical advice, "
                "please consult with a healthcare professional who can properly evaluate your condition."
            )
            source_info = "System Message"

    elif state.get("llm_success") and state.get("generation"):
        answer = state["generation"]
        logger.info("Executor: Using pre-generated LLM response")

    else:
        answer = (
            "I understand your concern about your symptoms. For accurate medical advice, "
            "please consult with a healthcare professional who can properly evaluate your condition."
        )
        source_info = "System Message"

    state["generation"] = answer
    state["source"] = source_info
    state["conversation_history"].append({"role": "user", "content": question})
    state["conversation_history"].append(
        {"role": "assistant", "content": answer, "source": source_info}
    )

    # Reset triage context after a diagnosis is delivered
    if triage_round > 0:
        state["triage_round"] = 0
        state["collected_symptoms"] = []
        state["questions_asked"] = []
        logger.info("Executor: Triage context reset after diagnosis delivery")

    return state
