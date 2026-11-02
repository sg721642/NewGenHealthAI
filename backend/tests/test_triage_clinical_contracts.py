"""
Tests for Triage Clinical Contracts, Question-Tied Options,
Structured Fact Store, and Medical Threshold Calibration (v3.0.0-rc8)
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.triage_agent import (
    TriageAgent,
    _infer_question_type,
    _sanitize_options_for_question,
    is_valid_triage_reply,
)
from app.core.state import initialize_conversation_state
from app.core.urgent_care import check_urgent_risk


# ==============================================================================
# 1. QUESTION PLANNING & OPTION COHERENCE (NO KEYWORD OVERWRITING)
# ==============================================================================

def test_duration_question_with_fever_word_never_infers_temperature():
    """
    FAILURE A ROOT CAUSE:
    A question asking "How long have you had the fever?" contains the word "fever",
    but its clinical axis is DURATION, not temperature.
    Inferring "temperature" and overwriting duration chips with °F is a critical defect.
    """
    question = "How long have you had the fever?"
    q_type = _infer_question_type(question)
    assert q_type == "duration", f"Expected 'duration', got '{q_type}'"

    options = ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"]
    sanitized = _sanitize_options_for_question(question, options)
    # Sanitized options MUST remain duration options, not Fahrenheit chips
    assert any("day" in opt.lower() or "hour" in opt.lower() for opt in sanitized)
    assert not any("°f" in opt.lower() or "100" in opt.lower() for opt in sanitized)


def test_when_did_fever_start_infers_duration():
    question = "When did your fever start and how did it begin?"
    q_type = _infer_question_type(question)
    assert q_type in ("duration", "onset")

    options = ["Started today", "1–3 days ago", "4–7 days ago", "Over a week ago"]
    sanitized = _sanitize_options_for_question(question, options)
    assert not any("100–102" in opt for opt in sanitized)


def test_temperature_question_has_temperature_chips():
    question = "What has your body temperature measured with a thermometer?"
    q_type = _infer_question_type(question)
    assert q_type == "temperature"

    options = ["Below 100°F (37.8°C)", "100–102°F (37.8–38.9°C)", "Above 102°F (38.9°C)", "Not measured yet"]
    sanitized = _sanitize_options_for_question(question, options)
    assert any("100" in opt for opt in sanitized)
    assert not any("1–3 days" in opt for opt in sanitized)


def test_associated_symptoms_question_with_fever_word_never_infers_temperature():
    question = "Do you have any other symptoms accompanying the fever, like cough, headache, or chills?"
    q_type = _infer_question_type(question)
    assert q_type == "associated_symptoms"

    options = ["Cough & sore throat", "Chills & body aches", "Headache & nausea", "None of these"]
    sanitized = _sanitize_options_for_question(question, options)
    assert not any("°f" in opt.lower() for opt in sanitized)
    assert any("cough" in opt.lower() or "chills" in opt.lower() for opt in sanitized)


def test_dyspnea_question_has_respiratory_chips():
    question = "Are you experiencing any shortness of breath or difficulty breathing?"
    q_type = _infer_question_type(question)
    assert q_type == "dyspnea"

    options = ["None / breathing normally", "Occasionally", "When walking or climbing stairs", "Constant / at rest"]
    sanitized = _sanitize_options_for_question(question, options)
    assert any("breath" in opt.lower() or "walking" in opt.lower() or "none" in opt.lower() for opt in sanitized)


# ==============================================================================
# 2. VALIDATION OF TRIAGE REPLIES AGAINST PENDING CONTRACT
# ==============================================================================

def test_valid_duration_replies_accepted():
    pending_q = "How long have you had the fever?"
    pending_opts = ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"]

    assert is_valid_triage_reply("1-3 days", pending_question=pending_q, pending_options=pending_opts)
    assert is_valid_triage_reply("kal se hai", pending_question=pending_q, pending_options=pending_opts)
    assert is_valid_triage_reply("2 din se", pending_question=pending_q, pending_options=pending_opts)
    assert is_valid_triage_reply("since yesterday", pending_question=pending_q, pending_options=pending_opts)


def test_gibberish_rejected_preserves_pending_question():
    pending_q = "How long have you had the fever?"
    pending_opts = ["Less than 24 hours", "1–3 days", "4–7 days", "More than a week"]

    assert not is_valid_triage_reply("asdfghjkl", pending_question=pending_q, pending_options=pending_opts)
    assert not is_valid_triage_reply("zzzzzz", pending_question=pending_q, pending_options=pending_opts)
    assert not is_valid_triage_reply("...", pending_question=pending_q, pending_options=pending_opts)


# ==============================================================================
# 3. STRUCTURED CLINICAL FACT STORE & QUESTION-TIED ADVANCEMENT
# ==============================================================================

def test_triage_flow_records_facts_to_correct_clinical_fields():
    """
    Multi-turn progression must populate structured clinical facts:
    Turn 1: 'I have fever' -> Active pending question: symptom_duration
    Turn 2: Answer '1–3 days' -> clinical_facts['symptom_duration'] = '1-3d'
    Next question: measured_temperature
    Turn 3: Answer '100–102°F' -> clinical_facts['reported_temperature'] = '100-102F'
    """
    state = initialize_conversation_state()
    state["question"] = "I have a fever"
    state["is_medical_query"] = True

    # Run Turn 1
    new_state = TriageAgent(state)
    assert new_state["triage_status"] == "needs_info"
    assert new_state["triage_round"] == 1
    fu = new_state.get("follow_up_data")
    assert fu is not None
    q_data = fu["questions"][0]
    
    # Must NOT ask temperature options for a duration question
    if "long" in q_data["text"].lower() or "duration" in q_data["text"].lower() or "when" in q_data["text"].lower():
        assert not any("100–102" in opt for opt in q_data["options"])


def test_complete_fever_multiturn_interview_with_fact_store():
    """
    Simulate full 3-turn fever clinical intake:
    Turn 1: 'mujhe bukhar hai' -> Asks duration with duration chips.
    Turn 2: User answers '1–3 days' -> Asks temperature with °F chips.
    Turn 3: User answers '100–102°F' -> Asks associated symptoms with symptom chips.
    Turn 4: User answers 'cough and mild chills' -> All facts collected -> ready_to_diagnose.
    """
    from app.core.state import reset_query_state

    # Turn 1: Initial complaint
    state = initialize_conversation_state()
    state["question"] = "mujhe bukhar hai"
    state["is_medical_query"] = True
    state = TriageAgent(state)

    assert state["triage_status"] == "needs_info"
    assert state["triage_round"] == 1
    assert state["clinical_facts"]["chief_complaint"] == "mujhe bukhar hai"
    q1 = state["follow_up_data"]["questions"][0]
    assert q1["clinical_field"] == "symptom_duration"
    assert any("day" in opt.lower() for opt in q1["options"])
    assert not any("100" in opt for opt in q1["options"])

    # Turn 2: User responds with duration
    state = reset_query_state(state)
    state["question"] = "1–3 days"
    state["is_medical_query"] = True
    state = TriageAgent(state)

    assert state["triage_status"] == "needs_info"
    assert state["triage_round"] == 2
    assert state["clinical_facts"]["symptom_duration"] == "1–3 days"
    q2 = state["follow_up_data"]["questions"][0]
    assert q2["clinical_field"] == "measured_temperature"
    assert any("100" in opt for opt in q2["options"])
    assert not any("1–3 days" in opt for opt in q2["options"])

    # Turn 3: User responds with temperature
    state = reset_query_state(state)
    state["question"] = "100–102°F (37.8–38.9°C)"
    state["is_medical_query"] = True
    state = TriageAgent(state)

    assert state["triage_status"] == "needs_info"
    assert state["triage_round"] == 3
    assert "100" in state["clinical_facts"]["reported_temperature"]
    q3 = state["follow_up_data"]["questions"][0]
    assert q3["clinical_field"] in ("associated_symptoms", "breathing_status")

    # Turn 4: User responds with associated symptoms -> reaches MAX_TRIAGE_ROUNDS
    state = reset_query_state(state)
    state["question"] = "Cough & sore throat"
    state["is_medical_query"] = True
    state = TriageAgent(state)

    assert state["triage_status"] == "ready_to_diagnose"
    assert "educational assessment" in state["question"]
    # Verify all clinical facts were preserved across all turns
    assert state["clinical_facts"]["chief_complaint"] == "mujhe bukhar hai"
    assert state["clinical_facts"]["symptom_duration"] == "1–3 days"
    assert "100" in state["clinical_facts"]["reported_temperature"]


def test_stale_chip_rejected_during_active_question():
    """
    If pending question is about temperature, clicking an unrelated duration chip
    from a previous turn is rejected as non-responsive and preserves the active question.
    """
    from app.core.state import reset_query_state

    state = initialize_conversation_state()
    state["question"] = "I have a fever"
    state["is_medical_query"] = True
    state = TriageAgent(state)  # Round 1 asks duration

    # Answer duration properly
    state = reset_query_state(state)
    state["question"] = "1–3 days"
    state["is_medical_query"] = True
    state = TriageAgent(state)  # Round 2 asks temperature

    assert state["triage_round"] == 2
    q2_text = state["follow_up_data"]["questions"][0]["text"]
    assert "temperature" in q2_text.lower() or "thermometer" in q2_text.lower() or "body" in q2_text.lower()

    # User accidentally re-clicks "1–3 days" (stale chip from Turn 1)
    state = reset_query_state(state)
    state["question"] = "1–3 days"
    state["is_medical_query"] = True
    state = TriageAgent(state)

    # Round MUST NOT advance to 3!
    assert state["triage_round"] == 2
    assert state["triage_status"] == "needs_info"
    assert "couldn't quite understand" in state["generation"].lower()


# ==============================================================================
# 4. MEDICAL GUIDANCE & FEVER THRESHOLD CALIBRATION
# ==============================================================================

def test_normal_temperature_not_classified_as_fever():
    """
    Temperature below 100°F (e.g. 98.6°F) is clinically normal or minimal elevation,
    not a true medical fever requiring high urgency.
    """
    risk = check_urgent_risk("My temperature is 98.6°F and I feel slightly warm")
    assert risk is None


def test_moderate_fever_not_emergency_dispatch():
    """
    101°F / 100-102°F fever with cough and fatigue (no acute red flags like
    unresponsive, severe chest pain, or cyanosis) is NOT an emergency dispatch.
    It must NOT trigger 112/108 ambulance dispatch!
    """
    risk = check_urgent_risk("I have 101°F fever and mild cough for 2 days")
    assert risk is None


def test_acute_cardiac_emergency_triggers_immediate_urgent_risk():
    """
    Crushing chest pain radiating to the left arm must trigger urgent care.
    """
    risk = check_urgent_risk("I have severe crushing chest pain radiating to my left arm")
    assert risk is not None
    assert risk["is_urgent"] is True
    assert risk["category"] == "cardiac"
    assert "112" in risk["advisory"]
