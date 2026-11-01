import re
from typing import List

from app.core.logging_config import logger
from app.core.state import AgentState
from app.tools.llm_client import get_llm, invoke_llm_with_fallback

PROMPT_INJECTION_PATTERN = re.compile(
    r"(?i)(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|<\|im_start\|>|<\|im_end\|>|<system>|</system>|\[INST\]|\[/INST\])",
    re.IGNORECASE,
)


def sanitize_emergency_numbers(text: str) -> str:
    """Ensure India emergency numbers (112 / 108) are prioritized and rogue 911 mentions without locale are clarified."""
    if not text:
        return ""
    # If text says 'call 911' or 'dial 911' without mentioning 112 or 108:
    if re.search(r"\b(?:call|dial)\s+911\b", text, re.IGNORECASE) and not re.search(r"\b112\b", text):
        text = re.sub(
            r"\b(?:call|dial)\s+911\b",
            "call 112 / 108 in India (or 911 in the US/Canada)",
            text,
            flags=re.IGNORECASE,
        )
    return text


def _sanitize_text(text: str) -> str:
    """Sanitize retrieved text before inserting into LLM prompt templates."""
    if not text:
        return ""
    return PROMPT_INJECTION_PATTERN.sub("[sanitized]", text)


def _format_provenance_citations(documents: List) -> str:
    """
    Format citations only when actual provenance metadata exists.

    Security constraints:
    - Only HTTPS URLs are accepted; javascript:, data:, http:, and malformed
      URLs are silently dropped to prevent XSS and phishing vectors.
    - Titles are sourced from metadata only (not LLM output); markdown special
      characters are escaped to prevent injection via document titles.
    - A citation is marked as 'source-present' only (not independently verified).
    """
    citations = []
    seen: set = set()

    def _is_safe_url(url: str) -> bool:
        """Accept only HTTPS URLs with a valid host."""
        if not url:
            return False
        stripped = url.strip().lower()
        # Reject dangerous or non-HTTPS schemes
        if not stripped.startswith("https://"):
            return False
        # Reject trivially malformed URLs (no host after scheme)
        rest = url.strip()[len("https://"):]
        return bool(rest and "." in rest.split("/")[0])

    def _escape_md(text: str) -> str:
        """Escape markdown link-breaking characters in untrusted text."""
        # Escape [ ] ( ) characters that could break markdown link syntax
        return re.sub(r"([\[\]()])", r"\\\1", text)

    for doc in documents:
        meta = getattr(doc, "metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or ""
        url = meta.get("url", "").strip()

        safe_url = url if _is_safe_url(url) else ""
        safe_title = _escape_md(title[:120]) if title else ""

        if safe_title and safe_title not in seen:
            seen.add(safe_title)
            if safe_url:
                citations.append(f"- [{safe_title}]({safe_url})")
            else:
                citations.append(f"- {safe_title}")
        elif safe_url and safe_url not in seen:
            seen.add(safe_url)
            citations.append(f"- [{safe_url}]({safe_url})")

    if citations:
        return "\n\n### 📚 Referenced Sources\n" + "\n".join(citations)
    return ""


def _invoke_llm_safe(llm, prompt: str, temperature: float = 0.3, max_tokens: int = 2048):
    """Safely invoke an available or mocked LLM with automatic model-fallback resilience."""
    if llm is not None:
        try:
            return llm.invoke(prompt)
        except Exception as e:
            err_msg = str(e)
            if any(w in err_msg.lower() for w in ["404", "not found", "decommissioned", "deprecated", "does not exist"]):
                return invoke_llm_with_fallback(prompt, temperature=temperature, max_tokens=max_tokens)
            raise
    return invoke_llm_with_fallback(prompt, temperature=temperature, max_tokens=max_tokens)


def ExecutorAgent(state: AgentState) -> AgentState:
    """
    Synthesize the final patient response from retrieved documents or LLM knowledge.
    Enforces non-impersonation, educational tone, source provenance, and safe service-unavailable handling.
    """
    # ── 1. Immediate urgent-risk alert pass-through ────────────────────
    if state.get("is_urgent"):
        answer = state.get("urgent_advisory") or state.get("generation", "")
        source_info = "Urgent Medical Alert"
        state["generation"] = answer
        state["source"] = source_info
        state["is_failed_generation"] = False
        state["conversation_history"].append({"role": "user", "content": state.get("question", "")})
        state["conversation_history"].append(
            {"role": "assistant", "content": answer, "source": source_info}
        )
        logger.info("Executor: Delivered urgent medical advisory")
        return state

    # ── 2. Triage follow-up questions pass-through ──────────────────────
    if state.get("triage_status") == "needs_info" and state.get("generation"):
        logger.info("Executor: Triage follow-up pass-through (round %s)",
                    state.get("triage_round", "?"))
        question = state["question"]
        answer = state["generation"]
        state["conversation_history"].append({"role": "user", "content": question})
        state["conversation_history"].append(
            {"role": "assistant", "content": answer, "source": "Clinical Triage"}
        )
        return state

    # ── 3. Check for total provider exhaustion / failure ───────────────
    has_docs = bool(state.get("documents") and len(state["documents"]) > 0)
    has_llm = bool(state.get("llm_success") and state.get("generation"))
    all_providers_exhausted = bool(state.get("exhaustion_reason"))
    has_triaged_symptoms = bool(state.get("collected_symptoms") and len(state.get("collected_symptoms", [])) > 0)
    llm = get_llm()

    # Terminate immediately if:
    # (a) all providers failed and no pre-generated content exists (unless post-triage symptoms need synthesis), OR
    # (b) the fallback chain explicitly flagged exhaustion via exhaustion_reason
    #     (prevents unbounded secondary LLM calls after budget is spent)
    if (all_providers_exhausted or (not has_docs and not has_llm and not llm)) and not has_triaged_symptoms:
        exhaust_reason = state.get("exhaustion_reason", "no_providers_available")
        logger.warning(
            "Executor: provider exhaustion — terminating (reason=%s, result_state=PROVIDER_UNAVAILABLE)",
            exhaust_reason,
        )
        state["is_failed_generation"] = True
        state["source"] = "Service Unavailable"
        state["generation"] = (
            "Our health information service is temporarily unavailable. "
            "If you are experiencing concerning symptoms, please consult your healthcare provider or local clinic directly."
        )
        # Do not append failed generation to conversation history as a successful medical turn
        return state

    question = state.get("question", "")
    source_info = state.get("source", "Health Information")
    triage_round = state.get("triage_round", 0)
    collected_symptoms = state.get("collected_symptoms", [])

    # Build conversation context
    history_context = ""
    for item in state.get("conversation_history", [])[-6:]:
        if item.get("role") == "user":
            history_context += f"User: {item.get('content', '')}\n"
        elif item.get("role") == "assistant":
            history_context += f"Assistant: {item.get('content', '')}\n"

    # ── 4. Post-Triage Comprehensive Educational Summary ───────────────
    if triage_round > 0 and collected_symptoms:
        collected_text = "\n".join(f"  - {s}" for s in collected_symptoms)

        # Multi-symptom risk evaluation: fever + cough + breathlessness/dyspnea
        all_sym_lower = " ".join(collected_symptoms).lower()
        has_fever = any(k in all_sym_lower for k in ["fever", "bukhar", "temp", "100", "101", "102", "chills", "degree"])
        has_cough = any(k in all_sym_lower for k in ["cough", "khansi"])
        has_dyspnea = any(k in all_sym_lower for k in ["breath", "breathing", "saans", "dyspnea", "shortness", "occasionally", "phool"])
        triad_respiratory = has_fever and has_cough and has_dyspnea

        triad_instruction = ""
        if triad_respiratory:
            triad_instruction = (
                "\nCRITICAL CLINICAL SAFETY RULE FOR MULTI-SYMPTOM RESPIRATORY RISK:\n"
                "The patient reported the clinical triad of fever/chills, cough, and shortness of breath (dyspnea). "
                "1. Under 'Educational Possibilities', explicitly highlight lower respiratory tract conditions to discuss with a clinician "
                "(e.g., bronchitis, pneumonia, or acute viral/bacterial respiratory infections) rather than dismissing as a common cold.\n"
                "2. Under 'Supportive Self-Care', suggest monitoring oxygen saturation (SpO2) with a pulse oximeter if available.\n"
                "3. Under 'Guidance for Healthcare Provider Consultation', strongly emphasize prompt in-person medical evaluation.\n"
            )

        doc_section = ""
        citations = ""
        if has_docs:
            doc_context = "\n\n".join(
                [_sanitize_text(doc.page_content[:1000]) for doc in state["documents"][:4]]
            )
            doc_section = f"\n\nMEDICAL REFERENCE LITERATURE (evidence base):\n{doc_context}"
            citations = _format_provenance_citations(state["documents"][:4])

        prompt = (
            "You are NewGenHealthAI, an automated medical education and informational assistant. "
            "You are NOT a doctor or clinical physician and have NOT conducted an in-person physical examination.\n\n"
            f"REPORTED SYMPTOMS SUMMARY:\n{collected_text}\n\n"
            f"Conversation History:\n{history_context}\n"
            f"{doc_section}\n"
            f"{triad_instruction}\n"
            "Provide a concise, practical educational summary (approximately 150–350 words total) to help the user prepare "
            "for an in-person discussion with a licensed healthcare professional. Strictly adhere to these clinical safety constraints:\n"
            "1. NEVER claim to be a physician, doctor, or that a clinical diagnosis has been made.\n"
            "2. DO NOT state definitive diagnostic conclusions. Present differential considerations with explicit diagnostic uncertainty.\n"
            "3. DO NOT recommend specific prescription drugs, medication dosages, or treatment schedules.\n"
            "4. Keep explanations brief, high-yield, and focused. Do NOT write lengthy multi-page essays.\n"
            "5. Structure your response with these exact markdown headers:\n\n"
            "## 📋 Health Summary & Overview\n"
            "Brief objective summary (1-2 sentences) of symptoms reported by the user.\n\n"
            "## 🔍 Educational Possibilities & Discussion Points\n"
            "2-3 potential health conditions to discuss with a doctor, noting diagnostic limitations.\n\n"
            "## 💡 Supportive Self-Care & General Measures\n"
            "Concise, practical non-pharmacological comfort measures (3-4 bullet points).\n\n"
            "## ⚠️ Red Flags & Warning Signs\n"
            "Key symptoms requiring immediate emergency medical care (call 112 / 108 in India).\n\n"
            "## 🩺 Guidance for Healthcare Provider Consultation\n"
            "Specific questions the user should take to their doctor.\n\n"
            "> **Medical Disclaimer:** This summary is for educational and informational purposes only and does not substitute "
            "for professional medical advice, clinical diagnosis, or individualized treatment."
        )

        try:
            response = _invoke_llm_safe(llm, prompt, temperature=0.3, max_tokens=1000)
            answer = ""
            if response is not None:
                answer = (
                    response.content.strip()
                    if hasattr(response, "content")
                    else str(response).strip()
                )
            if citations and answer:
                answer += citations
            source_info = "Educational Health Assessment" if not has_docs else "Educational Assessment + Medical Literature"
            if not answer:
                raise ValueError("Empty response from LLM")
            logger.info("Executor: Generated comprehensive educational assessment")
        except Exception as e:
            logger.error("Executor: post-triage LLM generation failed (%s): %s", type(e).__name__, str(e)[:120])
            symptoms_list = "\n".join(f"- {s}" for s in collected_symptoms)
            
            if triad_respiratory:
                diff_text = (
                    "The combination of fever, cough, and shortness of breath (dyspnea) warrants careful clinical assessment. "
                    "Possible conditions to discuss with a physician include lower respiratory tract infection, acute bronchitis, "
                    "or pneumonia, which require physical examination and auscultation."
                )
                self_care_extra = "- If a pulse oximeter is available, check your oxygen saturation (SpO2) at rest (normal is generally ≥95%).\n"
                consult_extra = "Because shortness of breath accompanied by fever and cough can reflect lower respiratory involvement, seek prompt in-person medical evaluation rather than assuming it is a routine cold."
            else:
                diff_text = "Prolonged or recurring symptoms may be associated with viral infections, bacterial illness, or other inflammatory conditions that require professional clinical evaluation and diagnostic testing."
                self_care_extra = ""
                consult_extra = "Inform your doctor about the exact onset date, temperature readings, associated symptoms, and any home remedies or over-the-counter medications tried."

            answer = (
                "## 📋 Health Summary & Overview\n"
                f"You reported the following symptoms during intake clarification:\n{symptoms_list}\n\n"
                "## 🔍 Educational Possibilities & Discussion Points\n"
                f"{diff_text}\n\n"
                "## 💡 Supportive Self-Care & General Measures\n"
                "- Maintain adequate fluid intake (water, oral rehydration solutions, or clear broths).\n"
                "- Get adequate rest and avoid strenuous physical exertion.\n"
                f"{self_care_extra}"
                "- Monitor your temperature and symptoms closely.\n\n"
                "## ⚠️ Red Flags & Warning Signs\n"
                "Seek immediate emergency medical care (call 112 / 108 / 102 in India) if you experience severe shortness of breath, persistent chest pain, confusion, lips turning blue, or an unmanageable high fever (>103°F / 39.4°C).\n\n"
                "## 🩺 Guidance for Healthcare Provider Consultation\n"
                f"{consult_extra}\n\n"
                "> **Medical Disclaimer:** This summary is for educational and informational purposes only and does not substitute for professional medical advice, clinical diagnosis, or individualized treatment."
            )
            source_info = "Educational Health Assessment"

    # ── 5. Standard RAG-backed response ────────────────────────────────
    elif has_docs and (llm or GROQ_API_KEY):
        content = "\n\n".join(
            [_sanitize_text(doc.page_content[:1000]) for doc in state["documents"][:3]]
        )
        citations = _format_provenance_citations(state["documents"][:3])
        prompt = (
            "You are NewGenHealthAI, an automated health education assistant. You are NOT a doctor.\n\n"
            f"Conversation History:\n{history_context}\n"
            f"User Question:\n{question}\n\n"
            f"Verified Medical Information:\n{content}\n\n"
            "Provide a helpful educational response adhering to these rules:\n"
            "- Do not impersonate a physician or state a definitive diagnosis.\n"
            "- Do not recommend specific prescription drug dosages.\n"
            "- Include key evidence-based educational facts.\n"
            "- Outline practical non-prescription self-care and when to seek in-person medical care.\n"
            "- Include a clear medical disclaimer that this is educational information."
        )
        try:
            response = _invoke_llm_safe(llm, prompt, temperature=0.3, max_tokens=2048)
            answer = ""
            if response is not None:
                answer = (
                    response.content.strip()
                    if hasattr(response, "content")
                    else str(response).strip()
                )
            if citations and answer:
                answer += citations
            source_info = state.get("source") or "Medical Literature Database"
            if not answer:
                raise ValueError("Empty response from LLM")
            logger.info("Executor: Generated response from documents")
        except Exception as e:
            logger.error("Executor: RAG LLM generation failed (%s): %s", type(e).__name__, str(e)[:120])
            first_doc_snippet = state["documents"][0].page_content[:300].strip() if state.get("documents") else ""
            answer = (
                f"### Educational Overview\n\n{first_doc_snippet}\n\n"
                f"{citations}\n\n"
                "For accurate clinical evaluation, please consult with a healthcare professional who can properly examine your symptoms."
            )
            source_info = state.get("source") or "Medical Literature Database"

    # ── 6. Pre-generated LLM response ──────────────────────────────────
    elif has_llm:
        answer = state["generation"]
        source_info = state.get("source") or "AI Medical Knowledge"
        logger.info("Executor: Using pre-generated LLM response")

    # ── 7. Fallback when no successful provider exists ─────────────────
    else:
        logger.warning("Executor: Provider outcome was unsuccessful")
        state["is_failed_generation"] = True
        state["source"] = "Service Unavailable"
        state["generation"] = (
            "Our health information service is temporarily unavailable. "
            "If you are experiencing concerning symptoms, please consult your healthcare provider or local clinic directly."
        )
        return state

    answer = sanitize_emergency_numbers(answer)
    state["generation"] = answer
    state["source"] = source_info
    state["is_failed_generation"] = False
    state["conversation_history"].append({"role": "user", "content": question})
    state["conversation_history"].append(
        {"role": "assistant", "content": answer, "source": source_info}
    )

    # Reset triage context after final assessment is delivered
    if triage_round > 0:
        state["triage_round"] = 0
        state["collected_symptoms"] = []
        state["questions_asked"] = []
        logger.info("Executor: Triage context reset after assessment delivery")

    return state
