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
    """Try to pull a JSON object out of LLM freeform text with error resilience."""
    if not text or not text.strip():
        return None

    cleaned_text = text.strip()

    # 1. Direct parse attempt
    try:
        return json.loads(cleaned_text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Markdown fenced block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned_text)
    if m:
        block = m.group(1).strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            # Try removing trailing commas
            block_fixed = re.sub(r",\s*([}\]])", r"\1", block)
            try:
                return json.loads(block_fixed)
            except json.JSONDecodeError:
                pass

    # 3. Outer braces extraction
    m = re.search(r"\{[\s\S]*\}", cleaned_text)
    if m:
        candidate = m.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            candidate_fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                return json.loads(candidate_fixed)
            except json.JSONDecodeError:
                pass

    return None


def TriageAgent(state: AgentState) -> AgentState:
    """
    Automated symptom intake clarification: asks ONE clarification question per round
    (up to MAX_TRIAGE_ROUNDS) to gather context for healthcare discussions.
    Emergency situations bypass triage immediately. Non-medical queries pass through.
    """
    # 0. Urgent risk bypass: never trap acute emergencies in symptom triage
    if state.get("is_urgent"):
        state["triage_status"] = "urgent_risk"
        logger.info("Triage: acute emergency flagged — bypassing symptom interview")
        return state

    if not state.get("is_medical_query", False) and state.get("triage_round", 0) == 0:
        state["triage_status"] = "ready_to_diagnose"
        logger.info("Triage: non-medical query — skipping")
        return state

    llm = _get_triage_llm()
    if not llm:
        state["triage_status"] = "ready_to_diagnose"
        return state

    raw_question = state.get("question", "")
    question = raw_question.strip() if isinstance(raw_question, str) else ""

    triage_round = state.get("triage_round", 0)
    collected = list(state.get("collected_symptoms", []))
    questions_asked = list(state.get("questions_asked", []))

    # Append current message to collected symptoms if non-empty
    if question:
        collected.append(question)
        state["collected_symptoms"] = collected

    # Transition to assessment after MAX rounds without forced diagnosis
    if triage_round >= MAX_TRIAGE_ROUNDS:
        logger.info("Triage: max rounds reached (%d) — transitioning to educational assessment", MAX_TRIAGE_ROUNDS)
        state["triage_status"] = "ready_to_diagnose"
        state["question"] = _build_enriched_question(collected)
        return state

    # Build conversation recap (last 10 turns)
    history_lines = []
    for item in state.get("conversation_history", [])[-10:]:
        role = "User" if item.get("role") == "user" else "Assistant"
        history_lines.append(f"{role}: {item.get('content', '')}")
    history_text = "\n".join(history_lines) if history_lines else "(first message)"

    # Collected symptoms so far
    collected_text = "\n".join(f"- {s}" for s in collected) if collected else "(none yet)"

    # Build explicit list of questions already asked
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
            f"This is intake clarification round {triage_round + 1} of {MAX_TRIAGE_ROUNDS}. "
            "Review everything the user said and ALL questions already asked. "
            "Identify the single most clinically relevant piece of information that is STILL MISSING. "
            "This could be: location, onset/duration, character, severity, associated symptoms, "
            "or aggravating/relieving factors. "
            "Ask EXACTLY ONE clear, concise question that has NOT been asked before."
        )
    else:
        round_instruction = (
            f"This is the FINAL clarification round (round {MAX_TRIAGE_ROUNDS}). "
            "If there is still ONE important piece of symptom context missing, ask it (set status='needs_info'). "
            "If you now have enough context to summarize for discussion with a doctor, set status='ready_to_diagnose'."
        )

    triage_prompt = f"""You are NewGenHealthAI, an automated medical education intake assistant.
You are NOT a doctor or physician, and do NOT diagnose patients. Your goal is to gather symptom clarity
to help the user prepare for a consultation with a healthcare professional.

USER'S CURRENT MESSAGE: "{question}"

CONVERSATION SO FAR:
{history_text}

ALL INFORMATION COLLECTED:
{collected_text}

{asked_block}

ROUND: {triage_round + 1} of {MAX_TRIAGE_ROUNDS}

ROUND-SPECIFIC INSTRUCTION:
{round_instruction}

STRICT SAFETY & STYLE RULES:
1. Ask EXACTLY ONE question — never multiple questions.
2. The question MUST be different from every question in "QUESTIONS ALREADY ASKED".
3. Never claim or imply you are a physician, doctor, or that you are diagnosing a disease.
4. Do NOT recommend prescription drugs, medication dosages, or treatment schedules.
5. Provide 3-5 short, helpful option chips (2-6 words each).
6. In `acknowledgment`, write a polite, empathetic 1-2 sentence acknowledgment of what the user reported. Do NOT put the follow-up question in this field.
7. Output ONLY valid JSON — no markdown or surrounding commentary.

OUTPUT FORMAT (choose one):

If more clarification needed:
{{
  "status": "needs_info",
  "acknowledgment": "Empathetic acknowledgment of what the user shared (1-2 sentences).",
  "question_text": "Your single clarification question.",
  "options": ["Option A", "Option B", "Option C", "Option D"]
}}

If enough information gathered:
{{
  "status": "ready_to_diagnose",
  "acknowledgment": "",
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
            logger.warning("Triage: couldn't parse JSON — defaulting to ready_to_diagnose")
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)
            return state

        status = parsed.get("status", "ready_to_diagnose")
        question_text = parsed.get("question_text", "").strip()
        options = parsed.get("options", [])
        acknowledgment = (parsed.get("acknowledgment") or parsed.get("doctor_response") or "").strip()

        if status == "needs_info" and question_text:
            state["triage_status"] = "needs_info"
            state["triage_round"] = triage_round + 1

            # Record question to prevent repetition
            questions_asked.append(question_text)
            state["questions_asked"] = questions_asked

            if acknowledgment:
                state["generation"] = f"{acknowledgment}\n\n**{question_text}**"
            else:
                state["generation"] = f"Thank you for sharing that information.\n\n**{question_text}**"
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

            logger.info("Triage: round %d — asking: '%s'", triage_round + 1, question_text[:80])

        else:
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)
            logger.info("Triage: sufficient symptom details — proceeding to educational assessment")

    except Exception as e:
        logger.error("Triage: LLM call failed: %s", str(e))
        state["triage_status"] = "ready_to_diagnose"
        state["question"] = _build_enriched_question(collected)

    return state


def _build_enriched_question(collected: List[str]) -> str:
    """Combine all collected symptom statements into an enriched educational query."""
    if not collected:
        return ""
    if len(collected) == 1:
        return collected[0]

    parts = [
        "The user reported the following symptoms during intake clarification:",
    ]
    for i, symptom in enumerate(collected, 1):
        parts.append(f"  {i}. {symptom}")
    parts.append(
        "\nBased on ALL the information above, provide an educational assessment "
        "highlighting possible conditions to discuss with a healthcare professional, acknowledging uncertainties, "
        "supportive self-care, and when to seek urgent or in-person medical care."
    )
    return "\n".join(parts)
