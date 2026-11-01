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
from app.core.config import GROQ_API_KEY, GROQ_TRIAGE_MODEL, GROQ_FALLBACK_MODELS
from app.tools.llm_client import invoke_llm_with_fallback, get_llm

MAX_TRIAGE_ROUNDS = 3

COMMON_WORDS = set(
    """
    a about above after again against all also am an and any are aren't as at be because been before being below
    between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each
    few for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself
    him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't
    my myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she she'd
    she'll she's should shouldn't so some such than that that's the their theirs them themselves then there there's
    these they they'd they'll they're they've this those through to too under until up very was wasn't we we'd we'll
    we're we've were weren't what what's when when's where where's which while who who's whom why why's with won't
    would wouldn't you you'd you'll you're you've
    yes no haan ha nahi nahin na dont don't know sure okay ok maybe fine
    day days week weeks month months year years hour hours hr hrs min mins minute minutes
    today yesterday morning evening night afternoon daily
    monday tuesday wednesday thursday friday saturday sunday
    pain ache aching sore hurt hurting sharp dull throbbing burning constant mild moderate severe
    fever cold flu cough headache chills nausea vomiting dizzy dizziness fatigue tired weakness
    high low fluctuating worse better nothing none neither
    kal aaj parso subah sham raat din dard bukhar khansi tez thoda jyada kam
    """.split()
)


def is_valid_triage_reply(text: str) -> bool:
    """Validate that a user reply to a triage follow-up question is meaningful content, not random keystrokes or gibberish."""
    if not text or not text.strip():
        return False
    t = text.strip().lower()

    words = re.findall(r"[a-z0-9]+", t)
    if not words:
        return False

    # Check if single token is a pure number within reasonable symptom range
    if len(words) == 1 and words[0].isdigit():
        val = int(words[0])
        return 0 <= val <= 365

    # Check if any recognized common word or medical/time token is present
    match_count = sum(1 for w in words if w in COMMON_WORDS)
    if match_count > 0:
        return True

    # Check for duration patterns like '2d', '3h', '1w'
    if re.search(r"\b\d+\s*(?:d|h|w|m|days?|hours?|weeks?|months?)\b", t):
        return True

    # Check for keyboard smashes or gibberish
    for w in words:
        if w.isalpha():
            if re.search(r"(?:asdf|sdfg|dfgh|fghj|ghjk|hjkl|qwer|werty|ertyu|rtyui|tyuio|yuio|zxcv|xcvb|cvbn|vbnm)", w):
                return False
            vowels = len(re.findall(r"[aeiouy]", w))
            consonants = len(w) - vowels
            if len(w) >= 5 and (vowels == 0 or consonants == 0):
                return False
            if re.search(r"(.)\1{2,}", w):
                return False

    return False


def _get_triage_llm():
    """Return a high-temperature Groq LLM specifically for dynamic triage."""
    return get_llm(model_name=GROQ_TRIAGE_MODEL, temperature=0.7, max_tokens=1024)


def _extract_json(text: str) -> Optional[Dict]:
    """Try to pull a JSON object out of LLM freeform text with error resilience."""
    if not text or not text.strip():
        return None

    cleaned_text = text.strip()

    # Strip thinking tokens if present (e.g. from reasoning models like Qwen or DeepSeek)
    cleaned_text = re.sub(r"<think>[\s\S]*?</think>", "", cleaned_text).strip()

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

    if state.get("triage_status") == "ready_to_diagnose":
        logger.info("Triage: general educational query — bypassing symptom intake")
        return state

    raw_question = state.get("question", "")
    question = raw_question.strip() if isinstance(raw_question, str) else ""

    triage_round = state.get("triage_round", 0)
    collected = list(state.get("collected_symptoms", []))
    questions_asked = list(state.get("questions_asked", []))

    # Validate follow-up response if in an active triage session
    if triage_round > 0:
        if not is_valid_triage_reply(question):
            logger.warning("Triage: rejected invalid or gibberish response: '%s'", question[:30])
            last_question = questions_asked[-1] if questions_asked else "How long have you been experiencing this symptom?"

            # Retrieve existing options from follow_up_data if available
            existing_options = []
            if state.get("follow_up_data") and state["follow_up_data"].get("questions"):
                existing_options = state["follow_up_data"]["questions"][0].get("options", [])
            if not existing_options:
                fb = _get_fallback_triage_question(
                    triage_round - 1,
                    question,
                    collected,
                    questions_asked[:-1] if len(questions_asked) > 1 else [],
                )
                existing_options = fb.get("options", ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"]) if fb else ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"]

            state["triage_status"] = "needs_info"
            state["generation"] = (
                "I couldn't quite understand that response. To help provide accurate health guidance, "
                f"could you please clarify your answer to the question below or select one of the suggested options?\n\n**{last_question}**"
            )
            state["source"] = "Clinical Triage"
            state["follow_up_data"] = {
                "questions": [
                    {
                        "text": last_question,
                        "options": existing_options[:5],
                    }
                ],
                "triage_round": triage_round,
                "max_rounds": MAX_TRIAGE_ROUNDS,
            }
            return state

    # Append valid message to collected symptoms if non-empty
    if question:
        collected.append(question)
        state["collected_symptoms"] = collected

    # Transition to assessment after MAX rounds without forced diagnosis
    if triage_round >= MAX_TRIAGE_ROUNDS:
        logger.info("Triage: max rounds reached (%d) — transitioning to educational assessment", MAX_TRIAGE_ROUNDS)
        state["triage_status"] = "ready_to_diagnose"
        state["question"] = _build_enriched_question(collected)
        return state

    llm = _get_triage_llm()
    if not llm:
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

    candidate_models = [GROQ_TRIAGE_MODEL] + [m for m in GROQ_FALLBACK_MODELS if m != GROQ_TRIAGE_MODEL]
    try:
        if llm is not None:
            try:
                response = llm.invoke(triage_prompt)
            except Exception as e:
                err_msg = str(e)
                if any(w in err_msg.lower() for w in ["404", "not found", "decommissioned", "deprecated", "does not exist"]):
                    response = invoke_llm_with_fallback(
                        triage_prompt,
                        candidate_models=candidate_models,
                        temperature=0.7,
                        max_tokens=1024,
                    )
                else:
                    raise
        else:
            response = invoke_llm_with_fallback(
                triage_prompt,
                candidate_models=candidate_models,
                temperature=0.7,
                max_tokens=1024,
            )
        answer = ""
        if response is not None:
            answer = (
                response.content.strip()
                if hasattr(response, "content")
                else str(response).strip()
            )

        parsed = _extract_json(answer) if answer else None

        if not parsed and answer and "?" in answer:
            # LLM replied conversationally with a follow-up question
            lines = [l.strip() for l in answer.strip().split("\n") if l.strip()]
            q_candidates = [l for l in lines if "?" in l]
            q_text = q_candidates[-1] if q_candidates else answer.strip()
            q_text = re.sub(r"^[*#\s\d.-]+", "", q_text).strip()
            ack_lines = [l for l in lines if l != q_text and "?" not in l]
            ack_text = " ".join(ack_lines)[:250] if ack_lines else "Thank you for sharing that context. Let's gather a bit more detail."
            
            fb = _get_fallback_triage_question(triage_round, question, collected, questions_asked)
            default_options = fb.get("options", ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"]) if fb else ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"]
            parsed = {
                "status": "needs_info",
                "acknowledgment": ack_text,
                "question_text": q_text,
                "options": default_options,
            }

        if not parsed:
            logger.warning("Triage: couldn't parse JSON — defaulting to ready_to_diagnose")
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)
            return state

        status = parsed.get("status", "ready_to_diagnose")
        question_text = parsed.get("question_text", "").strip()
        options = parsed.get("options", [])
        acknowledgment = (parsed.get("acknowledgment") or parsed.get("doctor_response") or "").strip()

        # Check for repetition against questions already asked
        if status == "needs_info" and question_text:
            is_repeat = any(question_text.lower() in q.lower() or q.lower() in question_text.lower() for q in questions_asked)
            if is_repeat:
                logger.warning("Triage: question repeated — generating non-repeat clinical fallback")
                fallback = _get_fallback_triage_question(triage_round, question, collected, questions_asked)
                if fallback:
                    question_text = fallback["question_text"]
                    options = fallback["options"]
                    if fallback.get("acknowledgment"):
                        acknowledgment = fallback["acknowledgment"]

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

            logger.info("Triage: round %d — follow-up question queued (chars=%d)", triage_round + 1, len(question_text))

        else:
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)
            logger.info("Triage: sufficient symptom details — proceeding to educational assessment")

    except Exception as e:
        logger.error("Triage: process exception (%s): %s", type(e).__name__, str(e)[:120])
        fallback = _get_fallback_triage_question(triage_round, question, collected, questions_asked)
        if fallback and triage_round < MAX_TRIAGE_ROUNDS:
            question_text = fallback["question_text"]
            options = fallback["options"]
            ack = fallback["acknowledgment"]
            state["triage_status"] = "needs_info"
            state["triage_round"] = triage_round + 1
            questions_asked.append(question_text)
            state["questions_asked"] = questions_asked
            state["generation"] = f"{ack}\n\n**{question_text}**"
            state["source"] = "Clinical Triage"
            state["follow_up_data"] = {
                "questions": [{"text": question_text, "options": options[:5]}],
                "triage_round": triage_round + 1,
                "max_rounds": MAX_TRIAGE_ROUNDS,
            }
        else:
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)

    return state


def _get_fallback_triage_question(
    triage_round: int,
    question: str,
    collected: List[str],
    questions_asked: List[str],
) -> Optional[Dict[str, Any]]:
    """Deterministic, clinically structured fallback questions aligned with medical project specifications."""
    if triage_round >= MAX_TRIAGE_ROUNDS:
        return None

    # Check which clinical axes have already been asked
    has_duration_asked = any("how many days" in q.lower() or "how long" in q.lower() or "duration" in q.lower() for q in questions_asked)
    has_severity_asked = any("severe" in q.lower() or "severity" in q.lower() or "temperature" in q.lower() for q in questions_asked)

    if triage_round == 0 or not has_duration_asked:
        return {
            "status": "needs_info",
            "acknowledgment": "I understand you are experiencing this symptom. To help you prepare for a consultation with a healthcare professional, let's clarify a few details.",
            "question_text": "How long have you been experiencing this, and did it begin suddenly or gradually?",
            "options": ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"],
        }
    elif triage_round == 1 or not has_severity_asked:
        return {
            "status": "needs_info",
            "acknowledgment": "Thank you for providing that timeframe. Duration is an essential detail for your doctor.",
            "question_text": "How severe would you describe this symptom, or is it accompanied by a high temperature or chills?",
            "options": ["Mild / manageable", "Moderate", "Severe / throbbing", "Fluctuates throughout the day"],
        }
    elif triage_round == 2:
        return {
            "status": "needs_info",
            "acknowledgment": "Thank you for sharing that context. One final check on related symptoms before summarizing.",
            "question_text": "Are you experiencing any associated symptoms such as chills, body aches, nausea, or shortness of breath?",
            "options": ["Chills & body aches", "Nausea or headache", "Cough & sore throat", "None of these"],
        }
    return None


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
