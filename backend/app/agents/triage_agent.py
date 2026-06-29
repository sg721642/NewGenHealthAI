"""
NewGenHealthAI — agents/triage_agent.py
TriageAgent: Clinical interview agent that asks follow-up questions like a real
doctor — ONE question at a time — for up to 3 rounds.

KEY RULES:
- NEVER repeat a question that was already asked.
- Questions must be uniquely tailored to the patient's specific complaint.
- Uses a HIGH-temperature LLM call for genuine clinical variety.
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.core.logging_config import logger
from app.core.state import AgentState
from app.core.config import GROQ_API_KEY

MAX_TRIAGE_ROUNDS = 3


def _get_triage_llm():
    """Return a high-temperature Groq LLM specifically for dynamic triage."""
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
            temperature=0.7,   # Higher temp = more varied, less predictable questions
            max_tokens=1024,
        )
    except Exception as e:
        logger.error("Triage LLM init failed: %s", str(e))
        return None


def _extract_json(text: str) -> Optional[Dict]:
    """Try to pull a JSON object out of LLM freeform text."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def TriageAgent(state: AgentState) -> AgentState:
    """
    Clinical triage: ask ONE dynamic follow-up question per round, then diagnose.
    Non-medical queries pass through transparently.
    """

    if not state.get("is_medical_query", False):
        state["triage_status"] = "ready_to_diagnose"
        logger.info("Triage: non-medical query — skipping")
        return state

    llm = _get_triage_llm()
    if not llm:
        state["triage_status"] = "ready_to_diagnose"
        return state

    question = state["question"]
    triage_round = state.get("triage_round", 0)
    collected = list(state.get("collected_symptoms", []))
    questions_asked = list(state.get("questions_asked", []))

    # Append current patient message to collected symptoms
    if question.strip():
        collected.append(question.strip())
        state["collected_symptoms"] = collected

    # Force diagnosis after MAX rounds
    if triage_round >= MAX_TRIAGE_ROUNDS:
        logger.info("Triage: max rounds reached — forcing diagnosis")
        state["triage_status"] = "ready_to_diagnose"
        state["question"] = _build_enriched_question(collected)
        return state

    # Build conversation recap (last 10 turns)
    history_lines = []
    for item in state.get("conversation_history", [])[-10:]:
        role = "Patient" if item.get("role") == "user" else "Doctor"
        history_lines.append(f"{role}: {item.get('content', '')}")
    history_text = "\n".join(history_lines) if history_lines else "(first message)"

    # Collected symptoms so far
    collected_text = "\n".join(f"- {s}" for s in collected) if collected else "(none yet)"

    # CRITICAL: Build explicit list of questions already asked
    if questions_asked:
        asked_block = (
            "QUESTIONS YOU HAVE ALREADY ASKED (DO NOT ASK THESE AGAIN OR ANYTHING SIMILAR):\n"
            + "\n".join(f"  {i+1}. {q}" for i, q in enumerate(questions_asked))
        )
    else:
        asked_block = "QUESTIONS ALREADY ASKED: None yet (this is the first follow-up)."

    # Round-specific instruction
    if triage_round < MAX_TRIAGE_ROUNDS - 1:
        round_instruction = (
            f"This is clinical intake round {triage_round + 1} of {MAX_TRIAGE_ROUNDS}. "
            "Review everything the patient said and ALL questions already asked. "
            "Identify the single most clinically valuable piece of information that is STILL MISSING. "
            "This could be: exact location of pain, character/quality (throbbing/sharp/dull), "
            "radiation/spread, associated symptoms, aggravating/relieving factors, "
            "relevant past history, medications taken, or anything uniquely relevant to THEIR complaint. "
            "Ask EXACTLY ONE highly specific, patient-tailored question that has NOT been asked before. "
            "Do NOT follow a rigid sequence — let the patient's unique complaint guide you."
        )
    else:
        round_instruction = (
            f"This is the FINAL intake round (round {MAX_TRIAGE_ROUNDS}). "
            "If there is still ONE critical piece of information missing for a complete clinical picture, "
            "ask it (set status='needs_info'). "
            "If you now have sufficient detail, set status='ready_to_diagnose' to proceed."
        )

    triage_prompt = f"""You are NewGenHealthAI, a senior clinical physician conducting a patient intake interview.

PATIENT'S CURRENT MESSAGE: "{question}"

CONVERSATION SO FAR:
{history_text}

ALL INFORMATION COLLECTED FROM PATIENT:
{collected_text}

{asked_block}

ROUND: {triage_round + 1} of {MAX_TRIAGE_ROUNDS}

ROUND-SPECIFIC INSTRUCTION:
{round_instruction}

STRICT RULES:
1. Ask EXACTLY ONE question — never multiple questions in one message.
2. The question MUST be different from every question in "QUESTIONS ALREADY ASKED". Asking a similar or rephrased version of an already-asked question is FORBIDDEN.
3. Tailor your question specifically to the patient's complaint (e.g. headache → ask about location/type/aura; chest pain → ask about radiation/breathlessness; rash → ask about appearance/spread/itch).
4. Provide 3-5 SHORT answer options (2-6 words each), specific and clinically meaningful.
5. In `doctor_response`, write a warm, empathetic 1-2 sentence acknowledgment of what the patient just said. Do NOT include the follow-up question in this field.
6. Output ONLY valid JSON — no other text before or after.

OUTPUT FORMAT (choose one):

If more info needed:
{{
  "status": "needs_info",
  "doctor_response": "Warm empathetic acknowledgment of what patient just shared (1-2 sentences, no question here).",
  "question_text": "Your single, highly specific follow-up question.",
  "options": ["Option A", "Option B", "Option C", "Option D"]
}}

If enough information for diagnosis:
{{
  "status": "ready_to_diagnose",
  "doctor_response": "",
  "question_text": "",
  "options": []
}}"""

    try:
        response = llm.invoke(triage_prompt)
        answer = (
            response.content.strip()
            if hasattr(response, "content")
            else str(response).strip()
        )

        parsed = _extract_json(answer)

        if not parsed:
            logger.warning("Triage: couldn't parse JSON — defaulting to ready")
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)
            return state

        status = parsed.get("status", "ready_to_diagnose")
        question_text = parsed.get("question_text", "").strip()
        options = parsed.get("options", [])
        doctor_response = parsed.get("doctor_response", "").strip()

        if status == "needs_info" and question_text:
            state["triage_status"] = "needs_info"
            state["triage_round"] = triage_round + 1

            # Record this question so it won't be repeated
            questions_asked.append(question_text)
            state["questions_asked"] = questions_asked

            if doctor_response:
                state["generation"] = f"{doctor_response}\n\n**{question_text}**"
            else:
                state["generation"] = f"Thank you for sharing that.\n\n**{question_text}**"
            state["source"] = "Clinical Triage"

            state["follow_up_data"] = {
                "questions": [
                    {
                        "text": question_text,
                        "options": options[:5],
                    }
                ],
                "triage_round": triage_round + 1,
                "max_rounds": MAX_TRIAGE_ROUNDS,
            }

            logger.info(
                "Triage: round %d — asking: '%s'",
                triage_round + 1,
                question_text[:80],
            )

        else:
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)
            logger.info("Triage: sufficient info — proceeding to diagnosis")

    except Exception as e:
        logger.error("Triage: LLM call failed: %s", str(e))
        state["triage_status"] = "ready_to_diagnose"
        state["question"] = _build_enriched_question(collected)

    return state


def _build_enriched_question(collected: List[str]) -> str:
    """Combine all collected patient statements into a single enriched query."""
    if not collected:
        return ""
    if len(collected) == 1:
        return collected[0]

    parts = [
        "The patient reported the following during clinical intake:",
    ]
    for i, symptom in enumerate(collected, 1):
        parts.append(f"  {i}. {symptom}")
    parts.append(
        "\nBased on ALL the information above, provide a comprehensive medical assessment "
        "including: possible diagnoses (differential diagnosis), recommended treatments, "
        "home remedies, when to seek urgent care, and preventive measures."
    )
    return "\n".join(parts)
