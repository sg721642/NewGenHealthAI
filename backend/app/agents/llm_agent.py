"""
NewGenHealthAI — agents/llm_agent.py
LLMAgent: generates a direct response from the LLM without RAG.
Enhanced with better prompting for comprehensive medical responses.
"""

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.llm_client import get_llm, invoke_llm_with_fallback
from app.agents.executor import sanitize_emergency_numbers


def LLMAgent(state: AgentState) -> AgentState:
    """Generate an educational health response directly from the LLM (no retrieval)."""
    attempted = list(state.get("attempted_providers", []))
    if "llm_agent" not in attempted:
        attempted.append("llm_agent")
    state["attempted_providers"] = attempted
    state["llm_attempted"] = True

    llm = get_llm()
    if not llm:
        state["llm_success"] = False
        state["generation"] = "Health AI information service is temporarily unavailable."
        return state

    # Build conversation context
    history_context = ""
    for item in state.get("conversation_history", [])[-5:]:
        if item.get("role") == "user":
            history_context += f"User: {item.get('content', '')}\n"
        elif item.get("role") == "assistant":
            history_context += f"Assistant: {item.get('content', '')}\n"

    # Check if this is a post-triage enriched question
    collected = state.get("collected_symptoms", [])
    triage_round = state.get("triage_round", 0)

    if triage_round > 0 and collected:
        collected_text = "\n".join(f"  - {s}" for s in collected)

        # Multi-symptom risk evaluation: fever + cough + breathlessness/dyspnea
        all_sym_lower = " ".join(collected).lower()
        has_fever = any(k in all_sym_lower for k in ["fever", "bukhar", "temp", "100", "101", "102", "chills", "degree"])
        has_cough = any(k in all_sym_lower for k in ["cough", "khansi"])
        has_dyspnea = any(k in all_sym_lower for k in ["breath", "breathing", "saans", "dyspnea", "shortness", "occasionally", "phool"])
        triad_instruction = ""
        if has_fever and has_cough and has_dyspnea:
            triad_instruction = (
                "\nCRITICAL CLINICAL SAFETY RULE FOR MULTI-SYMPTOM RESPIRATORY RISK:\n"
                "The patient reported the clinical triad of fever/chills, cough, and shortness of breath (dyspnea). "
                "1. Under 'Educational Considerations', explicitly highlight lower respiratory tract conditions to discuss with a clinician "
                "(e.g., bronchitis, pneumonia, or acute viral/bacterial respiratory infections) rather than dismissing as a common cold.\n"
                "2. Under 'Supportive Self-Care', suggest monitoring oxygen saturation (SpO2) with a pulse oximeter if available.\n"
                "3. Under 'In-Person Consultation Guidance', strongly emphasize prompt in-person medical evaluation.\n"
            )

        prompt = (
            "You are NewGenHealthAI, an automated medical education and informational assistant. "
            "You are NOT a doctor or licensed clinical physician, and have NOT performed a physical examination.\n\n"
            "REPORTED SYMPTOM INFORMATION:\n"
            f"{collected_text}\n\n"
            f"Conversation History:\n{history_context}\n"
            f"{triad_instruction}\n"
            "Provide a concise, objective educational summary (~150–350 words total) to assist the user in discussing their symptoms "
            "with a licensed healthcare professional. Follow these strict clinical safety rules:\n"
            "1. DO NOT claim to be a physician, doctor, or that a clinical diagnosis has been established.\n"
            "2. DO NOT provide definitive diagnoses. Highlight diagnostic uncertainties and suggest possible conditions as educational discussion points only.\n"
            "3. DO NOT recommend specific prescription drugs, dosages, or administration schedules. You may mention general categories of over-the-counter comfort measures with advice to consult a pharmacist or doctor.\n"
            "4. Keep explanations brief, actionable, and clear. Avoid lengthy essays.\n"
            "5. Structure your response with markdown headers:\n"
            "## 📋 Health Summary & Overview\n"
            "Objective summary of symptoms reported by the user.\n\n"
            "## 🔍 Educational Considerations\n"
            "General health conditions to discuss with a clinician, noting key uncertainties.\n\n"
            "## 💡 Supportive Self-Care & General Measures\n"
            "Safe, non-pharmacological comfort measures (e.g. hydration, rest, position).\n\n"
            "## ⚠️ Red Flags & Warning Signs\n"
            "Specific warning signs requiring immediate or emergency medical care (call 112 / 108 / 102 in India).\n\n"
            "## 🩺 In-Person Consultation Guidance\n"
            "Practical questions and steps for consulting a healthcare professional."
        )
    else:
        # Standard query
        prompt = (
            "You are NewGenHealthAI, an AI health education assistant. "
            "You are NOT a doctor, and provide general health information for educational purposes only.\n\n"
            f"Conversation History:\n{history_context}\n"
            f"User Question:\n{state['question']}\n\n"
            "Provide a concise, helpful educational response (~150–350 words). Strictly adhere to these safety rules:\n"
            "- Do not impersonate a physician or claim clinical examination.\n"
            "- Do not provide patient-specific prescriptions or drug dosages.\n"
            "- Acknowledge uncertainties when symptom details are incomplete.\n"
            "- Outline when to seek in-person professional medical evaluation.\n"
            "- Use clear markdown formatting with headers and bullet points."
        )

    try:
        if llm is not None:
            try:
                response = llm.invoke(prompt)
            except Exception as e:
                err_msg = str(e)
                if any(w in err_msg.lower() for w in ["404", "not found", "decommissioned", "deprecated", "does not exist"]):
                    response = invoke_llm_with_fallback(prompt, temperature=0.3, max_tokens=1000)
                else:
                    raise
        else:
            response = invoke_llm_with_fallback(prompt, temperature=0.3, max_tokens=1000)
        answer = ""
        if response is not None:
            answer = (
                response.content.strip()
                if hasattr(response, "content")
                else str(response).strip()
            )

        if answer and len(answer) > 10:
            answer = sanitize_emergency_numbers(answer)
            state["generation"] = answer
            state["llm_success"] = True
            state["source"] = "AI Medical Knowledge"
            logger.info("LLM: Generated response successfully")
        else:
            state["llm_success"] = False
            logger.warning("LLM: Response too short or empty")

    except Exception as e:
        logger.error("LLM: generation failed (%s)", type(e).__name__)
        state["llm_success"] = False

    return state
