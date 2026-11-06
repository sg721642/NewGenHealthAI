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

QUESTION_TYPES = {
    "temperature": ["Below 100°F (37.8°C)", "100–102°F (37.8–38.9°C)", "Above 102°F (38.9°C)", "Not measured yet"],
    "duration": ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"],
    "dyspnea": ["None", "Occasionally", "When walking or climbing", "Constant / resting"],
    "pain_severity": ["Mild / manageable", "Moderate", "Severe / throbbing", "Fluctuates throughout the day"],
    "associated_symptoms": ["Chills & body aches", "Nausea or headache", "Cough & sore throat", "None of these"],
    "general": ["Mild / occasional", "Moderate", "Severe", "Unsure / fluctuating"],
}


def _infer_question_type(question_text: str) -> str:
    """Infer the clinical axis of a question to ensure option coherence."""
    if not question_text:
        return "general"
    q = question_text.lower()
    # 1. Duration / Onset / Timeline — ALWAYS check before symptom nouns like fever!
    if any(k in q for k in [
        "how long", "how many days", "how many hours", "duration", "onset",
        "when did", "begin", "started", "start", "since when", "kab se",
        "kitne din", "kitne samay", "timeframe", "how many weeks"
    ]):
        return "duration"
    # 2. Dyspnea / Respiratory safety
    if any(k in q for k in [
        "breath", "breathing", "shortness", "saans", "dyspnea", "phool",
        "gasping", "chest tightness"
    ]):
        return "dyspnea"
    # 3. Associated / accompanying symptoms
    if any(k in q for k in [
        "associated", "other symptom", "accompanied", "along with",
        "accompanying", "aur koi", "other than", "any other"
    ]):
        return "associated_symptoms"
    # 4. Pain severity / character
    if any(k in q for k in [
        "how severe", "severity", "intensity", "rate your pain",
        "scale of", "throbbing", "sharp pain", "how bad", "kitna dard"
    ]):
        return "pain_severity"
    # 5. Temperature measurement (thermometer, degrees, etc. — NOT bare word "fever")
    if any(k in q for k in [
        "thermometer", "temperature", "measured", "degree", "°f", "°c",
        "tapman", "kitna bukhar", "how high"
    ]):
        return "temperature"
    # 6. Fallback if fever/bukhar without duration or other qualifiers
    if any(k in q for k in ["fever", "bukhar"]):
        return "temperature"
    return "general"


def _get_canonical_options(question_type: str) -> List[str]:
    """Retrieve standard curated choice options for a question type."""
    return list(QUESTION_TYPES.get(question_type, QUESTION_TYPES["general"]))


def _normalize_triage_text(text: str) -> str:
    """Normalize text by replacing unicode dashes, degree signs, non-breaking spaces, and punctuation."""
    if not text:
        return ""
    t = text.strip().lower()
    # Replace unicode dashes (en-dash \u2013, em-dash \u2014, minus \u2212, non-breaking hyphen \u2011)
    t = re.sub(r"[\u2013\u2014\u2011\u2212–—]", "-", t)
    # Replace non-breaking spaces
    t = t.replace("\u00a0", " ")
    # Replace degree symbol with space
    t = re.sub(r"[°\u00b0]", " ", t)
    # Separate numbers from adjacent units like 101f -> 101 f
    t = re.sub(r"(\d+)([a-zA-Z]+)", r"\1 \2", t)
    # Replace parentheses and extra punctuation
    t = re.sub(r"[()\[\]]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _sanitize_options_for_question(question_text: str, options: Optional[List[str]]) -> List[str]:
    """Ensure choice chips are semantically coherent with the question being asked."""
    q_type = _infer_question_type(question_text)
    canonical = _get_canonical_options(q_type)
    if not options or len(options) < 2:
        return canonical

    # If question is about temperature but options talk about days/hours or throbbing pain
    if q_type == "temperature":
        has_temp = any(re.search(r"\b(?:\d{2,3}|below|above|measured|not measured|normal|f|c|tapman)\b", opt.lower()) for opt in options)
        if not has_temp:
            return canonical

    # If question is about dyspnea/breathing but options talk about throbbing pain or duration
    if q_type == "dyspnea":
        has_resp = any(any(k in opt.lower() for k in ["breath", "breathing", "none", "occasional", "walking", "stairs", "rest", "constant", "saans"]) for opt in options)
        if not has_resp:
            return canonical

    # If question is about duration but options talk about pain or temperature
    if q_type == "duration":
        has_dur = any(any(k in opt.lower() for k in ["day", "hour", "week", "month", "today", "yesterday", "recent", "<", ">", "since", "start", "din"]) for opt in options)
        if not has_dur:
            return canonical

    # If question is about pain severity
    if q_type == "pain_severity":
        has_sev = any(any(k in opt.lower() for k in ["mild", "moderate", "severe", "throbbing", "sharp", "fluctuate", "manageable", "dard"]) for opt in options)
        if not has_sev:
            return canonical

    # If question is about associated symptoms
    if q_type == "associated_symptoms":
        has_sym = any(any(k in opt.lower() for k in ["cough", "throat", "chill", "ache", "headache", "nausea", "none", "pain", "fatigue", "vomit"]) for opt in options)
        if not has_sym:
            return canonical

    return options


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
    occasionally sometimes rarely frequently constantly persistent intermittent
    below above measured normal degrees degree celsius fahrenheit temp temperature
    walking exertion resting stairs stairs lying moving breath breathing breathless breathlessness shortness dyspnea
    kal aaj parso subah sham raat din dard bukhar khansi tez thoda jyada kam kabhi saans phool chhati seene pet sar
    """.split()
)


def is_valid_triage_reply(
    text: str,
    pending_question: Optional[str] = None,
    pending_options: Optional[List[str]] = None,
) -> bool:
    """Validate that a user reply to a triage follow-up question is meaningful content, not random keystrokes or gibberish."""
    if not text or not text.strip():
        return False
    raw = text.strip()
    norm = _normalize_triage_text(raw)
    if not norm:
        return False

    # 1. Direct option matching against pending options
    if pending_options:
        for opt in pending_options:
            if not opt:
                continue
            norm_opt = _normalize_triage_text(opt)
            if norm == norm_opt or norm in norm_opt or norm_opt in norm:
                return True
            # Check individual tokens match
            opt_tokens = set(re.findall(r"[a-z0-9]+", norm_opt))
            norm_tokens = set(re.findall(r"[a-z0-9]+", norm))
            if norm_tokens and norm_tokens.issubset(opt_tokens):
                return True

    # 2. Cross-modality rejection: if question is dyspnea or duration or temperature
    if pending_question:
        q_type = _infer_question_type(pending_question)
        if q_type == "dyspnea":
            # Duration phrases like "1-3 days" or temp like "100-102" are not valid answers to shortness of breath
            if re.search(r"\b\d+\s*(?:d|h|w|days?|hours?|weeks?)\b", norm):
                return False
            if re.search(r"\b\d{2,3}\s*(?:f|c|deg|degrees?)\b", norm):
                return False
        elif q_type == "duration":
            # Pure temperature like "100-102 F" does not answer "How long have you had fever?"
            if re.search(r"\b\d{2,3}\s*(?:f|c)\b", norm) and not re.search(r"\b(?:day|hour|week|month|today|yesterday|din|kab|since)\b", norm):
                return False
        elif q_type == "temperature":
            # Pure duration like "1-3 days" does not answer "What has your temperature measured?"
            if re.search(r"\b\d+\s*(?:d|h|w|days?|hours?|weeks?)\b", norm) and not re.search(r"\b(?:\d{2,3}|below|above|normal|f|c|tapman)\b", norm):
                return False

    # 3. Temperature pattern matching (e.g. 100-102, 100-102f, 38.5, 99°f, 101 f, 101f)
    if re.search(r"\b\d{2,3}(?:\.\d+)?\s*(?:-|to)\s*\d{2,3}(?:\.\d+)?\s*(?:f|c)?\b", norm):
        return True
    m_temp = re.search(r"(?:below|above|over|under|around|about)?\s*(\d{2,3}(?:\.\d+)?)\s*(?:f|c|degrees?|deg)?\b", norm)
    if m_temp:
        try:
            val = float(m_temp.group(1))
            if (35.0 <= val <= 43.0) or (94.0 <= val <= 108.0):
                return True
        except (ValueError, TypeError):
            pass

    # 4. Check for duration patterns like '2d', '3h', '1w', '1-3 days', 'less than 24 hours'
    if re.search(r"\b\d+\s*(?:d|h|w|m|days?|hours?|weeks?|months?)\b", norm):
        return True
    if re.search(r"\b\d+\s*-\s*\d+\s*(?:days?|hours?|weeks?|months?)\b", norm):
        return True

    words = re.findall(r"[a-z0-9]+", norm)
    if not words:
        return False

    # 4. Check if single token is a pure number within reasonable symptom range
    if len(words) == 1 and words[0].isdigit():
        val = int(words[0])
        return 0 <= val <= 365

    # 5. Check if any recognized common word or medical/time token is present
    match_count = sum(1 for w in words if w in COMMON_WORDS)
    if match_count > 0:
        return True

    # 6. Check for keyboard smashes or gibberish
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
    facts = dict(state.get("clinical_facts") or {})

    # Round 0: initialize chief complaint in clinical_facts
    if triage_round == 0 and question:
        facts["chief_complaint"] = question
        state["clinical_facts"] = facts

    # Validate follow-up response if in an active triage session
    if triage_round > 0:
        pending_followup = state.get("pending_follow_up_data") or state.get("follow_up_data")
        pending_q_obj = None
        pending_question = questions_asked[-1] if questions_asked else ""
        pending_options = []
        pending_field = "general"
        if pending_followup and pending_followup.get("questions"):
            pending_q_obj = pending_followup["questions"][0]
            pending_options = pending_q_obj.get("options", [])
            pending_field = (
                pending_q_obj.get("clinical_field")
                or pending_q_obj.get("question_type")
                or _infer_question_type(pending_question)
            )

        if not is_valid_triage_reply(question, pending_question=pending_question, pending_options=pending_options):
            logger.warning("Triage: rejected invalid or gibberish response: '%s'", question[:30])
            last_question = pending_question or "How long have you been experiencing this symptom?"
            q_type = _infer_question_type(last_question)
            existing_options = _sanitize_options_for_question(last_question, pending_options)

            state["triage_status"] = "needs_info"
            state["generation"] = (
                "I couldn't quite understand that response. To help provide accurate health guidance, "
                f"could you please clarify your answer to the question below or select one of the suggested options?\n\n**{last_question}**"
            )
            state["source"] = "Clinical Triage"
            state["follow_up_data"] = {
                "questions": [
                    {
                        "question_id": f"q_r{triage_round}_{q_type}",
                        "clinical_field": pending_field,
                        "question_type": q_type,
                        "text": last_question,
                        "options": existing_options[:5],
                        "structured_options": pending_q_obj.get("structured_options", []) if pending_q_obj else [],
                    }
                ],
                "triage_round": triage_round,
                "max_rounds": MAX_TRIAGE_ROUNDS,
            }
            state["pending_follow_up_data"] = state["follow_up_data"]
            return state

        # Store answer into structured fact store
        if pending_field in ("duration", "symptom_duration", "onset"):
            facts["symptom_duration"] = question
        elif pending_field in ("temperature", "measured_temperature"):
            facts["reported_temperature"] = question
        elif pending_field in ("dyspnea", "breathing_status"):
            facts["breathing_status"] = question
        elif pending_field in ("pain_severity", "severity"):
            facts["pain_severity"] = question
        elif pending_field in ("associated_symptoms", "symptoms"):
            facts["associated_symptoms"] = question
        else:
            facts[f"turn_{triage_round}_reply"] = question
        state["clinical_facts"] = facts

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
        fallback = _get_fallback_triage_question(
            triage_round, question, collected, questions_asked, clinical_facts=state.get("clinical_facts")
        )
        if fallback and triage_round < MAX_TRIAGE_ROUNDS:
            question_text = fallback["question_text"]
            q_type = fallback.get("question_type") or _infer_question_type(question_text)
            clinical_field = fallback.get("clinical_field", q_type)
            options = _sanitize_options_for_question(question_text, fallback["options"])
            ack = fallback.get("acknowledgment") or "Thank you for sharing that context."
            state["triage_status"] = "needs_info"
            state["triage_round"] = triage_round + 1
            questions_asked.append(question_text)
            state["questions_asked"] = questions_asked
            state["generation"] = f"{ack}\n\n**{question_text}**"
            state["source"] = "Clinical Triage"
            state["follow_up_data"] = {
                "questions": [
                    {
                        "question_id": f"q_r{triage_round + 1}_{q_type}",
                        "clinical_field": clinical_field,
                        "question_type": q_type,
                        "text": question_text,
                        "options": options[:5],
                        "structured_options": fallback.get("structured_options", [
                            {"option_id": f"opt_{i+1}", "label": opt, "canonical_value": opt}
                            for i, opt in enumerate(options[:5])
                        ]),
                    }
                ],
                "triage_round": triage_round + 1,
                "max_rounds": MAX_TRIAGE_ROUNDS,
            }
            state["pending_follow_up_data"] = state["follow_up_data"]
            return state
        else:
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
            "Review everything the user said, facts collected, and ALL questions already asked. "
            "Identify the single most clinically relevant piece of information that is STILL MISSING. "
            "Clinical fields: symptom_duration (how long/when started), measured_temperature (thermometer degrees), "
            "breathing_status (shortness of breath/dyspnea), associated_symptoms (cough, chills, headache), or pain_severity. "
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

CLINICAL FACTS COLLECTED:
{json.dumps(facts, indent=2)}

{asked_block}

ROUND: {triage_round + 1} of {MAX_TRIAGE_ROUNDS}

ROUND-SPECIFIC INSTRUCTION:
{round_instruction}

STRICT SAFETY & STYLE RULES:
1. Ask EXACTLY ONE question — never multiple questions.
2. The question MUST be different from every question in "QUESTIONS ALREADY ASKED".
3. Never claim or imply you are a physician, doctor, or that you are diagnosing a disease.
4. Do NOT recommend prescription drugs, medication dosages, or treatment schedules.
5. Provide 3-5 short, helpful option chips (2-6 words each) that directly answer the question asked.
6. In `acknowledgment`, write a polite, empathetic 1-2 sentence acknowledgment of what the user reported. Do NOT put the follow-up question in this field.
7. Output ONLY valid JSON — no markdown or surrounding commentary.

OUTPUT FORMAT (choose one):

If more clarification needed:
{{
  "status": "needs_info",
  "clinical_field": "symptom_duration | measured_temperature | breathing_status | associated_symptoms | pain_severity",
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
            
            q_type = _infer_question_type(q_text)
            default_options = _get_canonical_options(q_type)
            parsed = {
                "status": "needs_info",
                "clinical_field": q_type,
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
        clinical_field = parsed.get("clinical_field")

        # Check for repetition against questions already asked
        if status == "needs_info" and question_text:
            is_repeat = any(question_text.lower() in q.lower() or q.lower() in question_text.lower() for q in questions_asked)
            if is_repeat:
                logger.warning("Triage: question repeated — generating non-repeat clinical fallback")
                fallback = _get_fallback_triage_question(triage_round, question, collected, questions_asked, clinical_facts=state.get("clinical_facts"))
                if fallback:
                    question_text = fallback["question_text"]
                    options = fallback["options"]
                    clinical_field = fallback.get("clinical_field")
                    if fallback.get("acknowledgment"):
                        acknowledgment = fallback["acknowledgment"]

        if status == "needs_info" and question_text:
            state["triage_status"] = "needs_info"
            state["triage_round"] = triage_round + 1

            # Sanitize options to ensure semantic alignment with question_text
            q_type = _infer_question_type(question_text)
            if not clinical_field:
                clinical_field = q_type
            options = _sanitize_options_for_question(question_text, options)

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
                        "question_id": f"q_r{triage_round + 1}_{q_type}",
                        "clinical_field": clinical_field,
                        "question_type": q_type,
                        "text": question_text,
                        "options": options[:5],
                        "structured_options": [
                            {"option_id": f"opt_{i+1}", "label": opt, "canonical_value": opt}
                            for i, opt in enumerate(options[:5])
                        ],
                    }
                ],
                "triage_round": triage_round + 1,
                "max_rounds": MAX_TRIAGE_ROUNDS,
            }
            state["pending_follow_up_data"] = state["follow_up_data"]

            logger.info("Triage: round %d — follow-up question queued (field=%s, type=%s, chars=%d)", triage_round + 1, clinical_field, q_type, len(question_text))

        else:
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)
            logger.info("Triage: sufficient symptom details — proceeding to educational assessment")

    except Exception as e:
        logger.error("Triage: process exception (%s): %s", type(e).__name__, str(e)[:120])
        fallback = _get_fallback_triage_question(triage_round, question, collected, questions_asked, clinical_facts=state.get("clinical_facts"))
        if fallback and triage_round < MAX_TRIAGE_ROUNDS:
            question_text = fallback["question_text"]
            q_type = fallback.get("question_type") or _infer_question_type(question_text)
            clinical_field = fallback.get("clinical_field", q_type)
            options = _sanitize_options_for_question(question_text, fallback["options"])
            ack = fallback["acknowledgment"]
            state["triage_status"] = "needs_info"
            state["triage_round"] = triage_round + 1
            questions_asked.append(question_text)
            state["questions_asked"] = questions_asked
            state["generation"] = f"{ack}\n\n**{question_text}**"
            state["source"] = "Clinical Triage"
            state["follow_up_data"] = {
                "questions": [
                    {
                        "question_id": f"q_r{triage_round + 1}_{q_type}",
                        "clinical_field": clinical_field,
                        "question_type": q_type,
                        "text": question_text,
                        "options": options[:5],
                        "structured_options": fallback.get("structured_options", []),
                    }
                ],
                "triage_round": triage_round + 1,
                "max_rounds": MAX_TRIAGE_ROUNDS,
            }
            state["pending_follow_up_data"] = state["follow_up_data"]
        else:
            state["triage_status"] = "ready_to_diagnose"
            state["question"] = _build_enriched_question(collected)

    return state


def _get_fallback_triage_question(
    triage_round: int,
    question: str,
    collected: List[str],
    questions_asked: List[str],
    clinical_facts: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Deterministic, clinically structured fallback questions aligned with medical project specifications."""
    if triage_round >= MAX_TRIAGE_ROUNDS:
        return None

    facts = clinical_facts or {}
    all_reported = " ".join([question] + collected).lower()

    # Check which clinical axes have already been asked or collected in clinical_facts
    has_duration = bool(facts.get("symptom_duration")) or any(
        any(k in q.lower() for k in ["how many days", "how long", "duration", "when did", "onset", "begin", "started", "kab se"])
        for q in questions_asked
    )
    has_temp = bool(facts.get("reported_temperature")) or any(
        any(k in q.lower() for k in ["temperature", "thermometer", "measured", "how high", "tapman"])
        for q in questions_asked
    )
    has_resp = bool(facts.get("breathing_status")) or any(
        any(k in q.lower() for k in ["breath", "breathing", "shortness", "dyspnea", "saans"])
        for q in questions_asked
    )
    has_associated = bool(facts.get("associated_symptoms")) or any(
        any(k in q.lower() for k in ["associated", "other symptom", "accompanied"])
        for q in questions_asked
    )
    has_severity = bool(facts.get("pain_severity")) or any(
        any(k in q.lower() for k in ["severe", "severity", "how bad", "kitna dard"])
        for q in questions_asked
    )

    is_fever = any(k in all_reported for k in ["fever", "bukhar", "chills", "hot", "sweat", "temperature"])
    is_pain = any(k in all_reported for k in ["pain", "dard", "ache", "headache", "stomach", "chest"])
    is_respiratory = any(k in all_reported for k in ["cough", "khansi", "cold", "flu", "throat", "sneeze"])

    # Clinical Trajectory for Fever:
    # 1. Duration / Onset (essential timeline)
    # 2. Measured temperature (severity / fever grade)
    # 3. Respiratory / breathing safety
    # 4. Associated symptoms
    if is_fever:
        if not has_duration:
            return {
                "status": "needs_info",
                "clinical_field": "symptom_duration",
                "question_type": "duration",
                "acknowledgment": "I understand you have had a fever. Clarifying when it started and how long it has lasted helps assess its trajectory.",
                "question_text": "How long have you had the fever, and did it begin suddenly or gradually?",
                "options": ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"],
                "structured_options": [
                    {"option_id": "dur_24h", "label": "Less than 24 hours", "canonical_value": "<24h"},
                    {"option_id": "dur_1_3d", "label": "1–3 days", "canonical_value": "1-3d"},
                    {"option_id": "dur_4_7d", "label": "4–7 days", "canonical_value": "4-7d"},
                    {"option_id": "dur_week", "label": "More than a week", "canonical_value": ">7d"},
                ],
            }
        elif not has_temp:
            return {
                "status": "needs_info",
                "clinical_field": "measured_temperature",
                "question_type": "temperature",
                "acknowledgment": "Thank you for noting the timeframe. Checking your measured temperature helps evaluate fever grade.",
                "question_text": "What has your body temperature measured with a thermometer, or how high does it feel?",
                "options": ["Below 100°F (37.8°C)", "100–102°F (37.8–38.9°C)", "Above 102°F (38.9°C)", "Not measured yet"],
                "structured_options": [
                    {"option_id": "temp_normal", "label": "Below 100°F (37.8°C)", "canonical_value": "<100F"},
                    {"option_id": "temp_mod", "label": "100–102°F (37.8–38.9°C)", "canonical_value": "100-102F"},
                    {"option_id": "temp_high", "label": "Above 102°F (38.9°C)", "canonical_value": ">102F"},
                    {"option_id": "temp_unmeasured", "label": "Not measured yet", "canonical_value": "unmeasured"},
                ],
            }
        elif not has_resp and is_respiratory:
            return {
                "status": "needs_info",
                "clinical_field": "breathing_status",
                "question_type": "dyspnea",
                "acknowledgment": "Thank you for sharing your temperature reading. Checking your respiratory comfort is an essential clinical check.",
                "question_text": "Are you experiencing any shortness of breath, chest tightness, or difficulty breathing?",
                "options": ["None / breathing normally", "Occasionally", "When walking or climbing stairs", "Constant / at rest"],
                "structured_options": [
                    {"option_id": "breath_none", "label": "None / breathing normally", "canonical_value": "normal"},
                    {"option_id": "breath_occasional", "label": "Occasionally", "canonical_value": "occasional"},
                    {"option_id": "breath_exertion", "label": "When walking or climbing stairs", "canonical_value": "on_exertion"},
                    {"option_id": "breath_rest", "label": "Constant / at rest", "canonical_value": "at_rest"},
                ],
            }
        elif not has_associated:
            return {
                "status": "needs_info",
                "clinical_field": "associated_symptoms",
                "question_type": "associated_symptoms",
                "acknowledgment": "Thank you for providing that detail. One final check on related symptoms before summarizing.",
                "question_text": "Are you experiencing any accompanying symptoms such as cough, chills, body aches, or headache?",
                "options": ["Cough & sore throat", "Chills & body aches", "Headache & nausea", "None of these"],
                "structured_options": [
                    {"option_id": "sym_cough", "label": "Cough & sore throat", "canonical_value": "cough_sore_throat"},
                    {"option_id": "sym_chills", "label": "Chills & body aches", "canonical_value": "chills_aches"},
                    {"option_id": "sym_headache", "label": "Headache & nausea", "canonical_value": "headache_nausea"},
                    {"option_id": "sym_none", "label": "None of these", "canonical_value": "none"},
                ],
            }

    # Standard progression for non-fever complaints:
    if not has_duration:
        return {
            "status": "needs_info",
            "clinical_field": "symptom_duration",
            "question_type": "duration",
            "acknowledgment": "I understand you are experiencing this symptom. To help you prepare for a consultation with a healthcare professional, let's clarify a few details.",
            "question_text": "How long have you been experiencing this, and did it begin suddenly or gradually?",
            "options": ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"],
            "structured_options": [
                {"option_id": "dur_24h", "label": "Less than 24 hours", "canonical_value": "<24h"},
                {"option_id": "dur_1_3d", "label": "1–3 days", "canonical_value": "1-3d"},
                {"option_id": "dur_4_7d", "label": "4–7 days", "canonical_value": "4-7d"},
                {"option_id": "dur_week", "label": "More than a week", "canonical_value": ">7d"},
            ],
        }
    elif is_pain and not has_severity:
        return {
            "status": "needs_info",
            "clinical_field": "pain_severity",
            "question_type": "pain_severity",
            "acknowledgment": "Thank you for providing that timeframe. Duration is an essential detail for your doctor.",
            "question_text": "How severe would you describe the pain or discomfort throughout your typical day?",
            "options": ["Mild / manageable", "Moderate", "Severe / throbbing", "Fluctuates throughout the day"],
            "structured_options": [
                {"option_id": "sev_mild", "label": "Mild / manageable", "canonical_value": "mild"},
                {"option_id": "sev_mod", "label": "Moderate", "canonical_value": "moderate"},
                {"option_id": "sev_sev", "label": "Severe / throbbing", "canonical_value": "severe"},
                {"option_id": "sev_fluc", "label": "Fluctuates throughout the day", "canonical_value": "fluctuating"},
            ],
        }
    elif is_respiratory and not has_resp:
        return {
            "status": "needs_info",
            "clinical_field": "breathing_status",
            "question_type": "dyspnea",
            "acknowledgment": "Thank you for noting that. Checking your breathing comfort is an essential clinical safety check.",
            "question_text": "Are you experiencing any shortness of breath, chest tightness, or difficulty breathing?",
            "options": ["None / breathing normally", "Occasionally", "When walking or climbing stairs", "Constant / at rest"],
            "structured_options": [
                {"option_id": "breath_none", "label": "None / breathing normally", "canonical_value": "normal"},
                {"option_id": "breath_occasional", "label": "Occasionally", "canonical_value": "occasional"},
                {"option_id": "breath_exertion", "label": "When walking or climbing stairs", "canonical_value": "on_exertion"},
                {"option_id": "breath_rest", "label": "Constant / at rest", "canonical_value": "at_rest"},
            ],
        }
    elif not has_associated:
        return {
            "status": "needs_info",
            "clinical_field": "associated_symptoms",
            "question_type": "associated_symptoms",
            "acknowledgment": "Thank you for sharing that context. One final check on related symptoms before summarizing.",
            "question_text": "Are you experiencing any associated symptoms such as chills, body aches, nausea, or headache?",
            "options": ["Chills & body aches", "Nausea or headache", "Cough & sore throat", "None of these"],
            "structured_options": [
                {"option_id": "sym_chills", "label": "Chills & body aches", "canonical_value": "chills_aches"},
                {"option_id": "sym_nausea", "label": "Nausea or headache", "canonical_value": "headache_nausea"},
                {"option_id": "sym_cough", "label": "Cough & sore throat", "canonical_value": "cough_sore_throat"},
                {"option_id": "sym_none", "label": "None of these", "canonical_value": "none"},
            ],
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
