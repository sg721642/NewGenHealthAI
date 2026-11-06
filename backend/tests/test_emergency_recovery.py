"""
Emergency Recovery Regression Tests:
Verifies multi-turn medical triage, direct knowledge Q&A,
India-specific emergency numbers, and session state rehydration.
"""

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document
from app.core.state import initialize_conversation_state
from app.agents.planner import PlannerAgent
from app.agents.triage_agent import TriageAgent
from app.agents.executor import ExecutorAgent
from app.core.langgraph_workflow import _route_after_planner, _route_after_triage
from app.core.urgent_care import check_urgent_risk, generate_urgent_advisory


def test_general_knowledge_bypasses_triage():
    """Questions like 'What is diabetes?' must bypass triage directly to educational Q&A."""
    state = initialize_conversation_state()
    state["question"] = "What is diabetes?"
    state = PlannerAgent(state)
    assert state.get("is_medical_query") is True
    assert state.get("triage_status") == "ready_to_diagnose"
    # When triage_status is ready_to_diagnose, routing proceeds directly to retriever or llm
    assert _route_after_triage(state) in ("retriever", "llm_agent")


def test_symptom_initiates_multi_turn_triage():
    """Initial symptom presentation ('I have a fever') must initiate triage follow-up."""
    state = initialize_conversation_state()
    state["question"] = "I have a fever"
    state = PlannerAgent(state)
    assert state.get("is_medical_query") is True
    assert _route_after_planner(state) == "triage_agent"

    with patch("app.agents.triage_agent._get_triage_llm") as mock_llm:
        mock_resp = MagicMock()
        mock_resp.content = '{"status": "needs_info", "acknowledgment": "I see you have a fever.", "question_text": "How long have you had this fever?", "options": ["1-2 days", "3-5 days"]}'
        mock_llm.return_value.invoke.return_value = mock_resp
        state = TriageAgent(state)
        assert state.get("triage_status") == "needs_info"
        assert "How long" in state["generation"]
        assert _route_after_triage(state) == "executor"


def test_followup_answers_continue_active_triage():
    """Short follow-up answers like 'For 7 days' must maintain active triage."""
    state = initialize_conversation_state()
    state["question"] = "For 7 days"
    state["triage_round"] = 1
    state["collected_symptoms"] = ["I have a fever"]
    state = PlannerAgent(state)
    assert state.get("is_medical_query") is True
    assert _route_after_planner(state) == "triage_agent"

    with patch("app.agents.triage_agent._get_triage_llm") as mock_llm:
        mock_resp = MagicMock()
        mock_resp.content = '{"status": "needs_info", "acknowledgment": "7 days is a notable duration.", "question_text": "How high has your temperature been?", "options": ["Under 100 F", "100-102 F", "Over 102 F"]}'
        mock_llm.return_value.invoke.return_value = mock_resp
        state = TriageAgent(state)
        assert state.get("triage_status") == "needs_info"
        assert state.get("triage_round") == 2
        assert _route_after_triage(state) == "executor"


def test_urgent_emergency_numbers_india():
    """Emergency advisories in India must prominently feature 112, 108, and 102."""
    cardiac = check_urgent_risk("crushing chest pain radiating to my arm")
    assert cardiac is not None
    assert cardiac["is_urgent"] is True
    advisory = cardiac["advisory"]
    assert "112" in advisory
    assert "108" in advisory
    assert "102" in advisory
    assert "India National Emergency" in advisory


def test_triage_to_executor_round_limit():
    """After MAX_TRIAGE_ROUNDS, triage transitions to educational assessment."""
    state = initialize_conversation_state()
    state["question"] = "Chills and mild body ache"
    state["triage_round"] = 3
    state["collected_symptoms"] = ["High fever for 5 days", "Temperature 101 F"]
    state = TriageAgent(state)
    assert state["triage_status"] == "ready_to_diagnose"
    assert "educational assessment" in state["question"]
    assert _route_after_triage(state) in ("retriever", "llm_agent")


def test_ai_readiness_probe_missing_key():
    """When GROQ_API_KEY is missing, readiness returns ready=False and missing_api_key."""
    from app.tools.llm_client import check_ai_provider_readiness
    with patch("app.tools.llm_client.GROQ_API_KEY", ""):
        res = check_ai_provider_readiness(force_refresh=True)
        assert res["ready"] is False
        assert res["status"] == "missing_api_key"


def test_ai_readiness_probe_success():
    """When Groq models.list succeeds, readiness returns ready=True and operational."""
    from app.tools.llm_client import check_ai_provider_readiness
    with patch("app.tools.llm_client.GROQ_API_KEY", "gsk_test1234567890"):
        with patch("groq.Groq") as mock_groq_cls:
            mock_client = MagicMock()
            mock_client.models.list.return_value = MagicMock(data=[])
            mock_groq_cls.return_value = mock_client
            res = check_ai_provider_readiness(force_refresh=True)
            assert res["ready"] is True
            assert res["status"] == "operational"


def test_ai_readiness_probe_failure_sanitization():
    """When Groq raises an error, readiness returns ready=False and redacts any key."""
    from app.tools.llm_client import check_ai_provider_readiness
    secret_key = "gsk_secret_should_never_leak"
    with patch("app.tools.llm_client.GROQ_API_KEY", secret_key):
        with patch("groq.Groq") as mock_groq_cls:
            mock_client = MagicMock()
            mock_client.models.list.side_effect = RuntimeError(f"Connection refused with key {secret_key}")
            mock_groq_cls.return_value = mock_client
            res = check_ai_provider_readiness(force_refresh=True)
            assert res["ready"] is False
            assert res["status"] == "provider_unreachable"
            assert secret_key not in res["detail"]
            assert "[REDACTED]" in res["detail"]


def test_gibberish_triage_rejection():
    """Gibberish during active triage does not increment round or append symptom."""
    from app.agents.triage_agent import is_valid_triage_reply
    assert is_valid_triage_reply("shsauidfewjew") is False
    assert is_valid_triage_reply("asdfghjkl") is False
    assert is_valid_triage_reply("3 days") is True
    assert is_valid_triage_reply("mild headache and nausea") is True

    state = initialize_conversation_state()
    state["question"] = "shsauidfewjew"
    state["triage_round"] = 1
    state["collected_symptoms"] = ["fever"]
    state["triage_question"] = "How many days have you had the fever?"
    state["triage_options"] = ["1-2 days", "3-5 days", "More than a week"]

    updated_state = TriageAgent(state)
    # Triage round must NOT advance
    assert updated_state["triage_round"] == 1
    # Gibberish must NOT be added to collected symptoms
    assert "shsauidfewjew" not in updated_state["collected_symptoms"]
    assert updated_state["triage_status"] == "needs_info"
    assert "could not understand" in updated_state["generation"].lower() or "please clarify" in updated_state["generation"].lower()
    # Prior options must be preserved
    assert updated_state["triage_options"] == ["1-2 days", "3-5 days", "More than a week"]


def test_hinglish_third_person_cardiac_emergency():
    """Third-person Hinglish cardiac emergency queries must trigger urgent routing."""
    res1 = check_urgent_risk("mera dost ko heart attack aaya hai")
    assert res1 is not None
    assert res1["is_urgent"] is True
    assert "112" in res1["advisory"]
    assert "108" in res1["advisory"]

    res2 = check_urgent_risk("mere papa ko dil ka daura pada hai")
    assert res2 is not None
    assert res2["is_urgent"] is True
    assert "112" in res2["advisory"]


def test_emergency_followup_location_delhi():
    """Emergency follow-up mentioning Delhi must return localized Delhi dispatch guidance."""
    from app.core.urgent_care import check_emergency_followup, generate_delhi_emergency_guidance
    history = [
        {"role": "user", "content": "mera dost ko heart attack aaya hai"},
        {"role": "assistant", "content": "EMERGENCY: Call 112 immediately. What is your location?"}
    ]
    is_followup = check_emergency_followup("Delhi me", history)
    assert is_followup is not None
    assert is_followup.get("is_urgent") is True

    state = initialize_conversation_state()
    state["question"] = "Delhi me"
    state["conversation_history"] = history
    state = PlannerAgent(state)

    assert state.get("is_urgent") is True
    assert "112" in state["urgent_advisory"]
    assert "108" in state["urgent_advisory"]
    assert "AIIMS" in state["urgent_advisory"]
    assert "Safdarjung" in state["urgent_advisory"]


def test_sanitize_emergency_numbers():
    """Rogue US-only 911 mentions must be sanitized to include India emergency numbers."""
    from app.agents.executor import sanitize_emergency_numbers
    raw = "If symptoms worsen, please call 911 immediately or visit an ER."
    sanitized = sanitize_emergency_numbers(raw)
    assert "112 / 108 in India" in sanitized


def test_format_utc_iso_z():
    """_format_utc_iso must ensure output ends with UTC 'Z'."""
    from app.models.message import _format_utc_iso
    from datetime import datetime, timezone
    dt = datetime(2026, 11, 2, 4, 0, 0, tzinfo=timezone.utc)
    formatted = _format_utc_iso(dt)
    assert formatted.endswith("Z")
    assert "+00:00" not in formatted


def test_stable_conversation_title_generation():
    """Title generation should create concise, relevant titles."""
    from app.services.database_service import generate_conversation_title
    assert generate_conversation_title("I have had a high fever for three days") == "Fever Consultation"
    assert generate_conversation_title("What is diabetes?") == "Diabetes Inquiry"
    assert generate_conversation_title("Uploaded medical image for clinical analysis") == "Medical Image Consultation"
    assert generate_conversation_title("") == "New Consultation"


def test_unicode_temperature_option_accepted():
    """The choice chip '100–102°F (37.8–38.9°C)' must be recognized as valid."""
    from app.agents.triage_agent import is_valid_triage_reply
    options = ["Below 100°F (37.8°C)", "100–102°F (37.8–38.9°C)", "Above 102°F (38.9°C)", "Not measured yet"]
    reply = "100–102°F (37.8–38.9°C)"
    assert is_valid_triage_reply(reply, pending_question="What is your temperature?", pending_options=options) is True
    # Also valid without pending options via pattern matching
    assert is_valid_triage_reply(reply) is True
    assert is_valid_triage_reply("101°F") is True
    assert is_valid_triage_reply("38.5 C") is True


def test_occasional_shortness_of_breath_accepted():
    """'Occasionally' must be recognized as a valid triage answer without false emergency or gibberish rejection."""
    from app.agents.triage_agent import is_valid_triage_reply
    options = ["None", "Occasionally", "When walking or climbing", "Constant / resting"]
    assert is_valid_triage_reply("Occasionally", pending_options=options) is True
    assert is_valid_triage_reply("occasionally") is True
    assert is_valid_triage_reply("sometimes") is True
    assert is_valid_triage_reply("kabhi kabhi saans phoolti hai") is True


def test_gibberish_preserves_temperature_question_and_options():
    """Gibberish under a temperature question must reprompt the temperature question with temperature options, not duration."""
    state = initialize_conversation_state()
    state["triage_round"] = 1
    state["questions_asked"] = ["What has your body temperature measured, or how high does the fever feel?"]
    state["pending_follow_up_data"] = {
        "questions": [
            {
                "text": "What has your body temperature measured, or how high does the fever feel?",
                "options": ["Below 100°F (37.8°C)", "100–102°F (37.8–38.9°C)", "Above 102°F (38.9°C)", "Not measured yet"],
                "question_type": "temperature",
            }
        ]
    }
    state["question"] = "asdfghjkl zxcvbnm"
    res = TriageAgent(state)

    assert res["triage_status"] == "needs_info"
    assert "What has your body temperature measured" in res["generation"]
    # Verify options are temperature options, NOT duration
    opts = res["follow_up_data"]["questions"][0]["options"]
    assert any("100" in o or "°F" in o for o in opts)
    assert not any("1–3 days" in o or "hours" in o for o in opts)


def test_delhi_cats_ambulance_is_102():
    """Delhi CATS Ambulance must be clearly designated as 102 in emergency guidance."""
    from app.core.urgent_care import generate_delhi_emergency_guidance
    guidance = generate_delhi_emergency_guidance()
    assert "102" in guidance
    assert "CATS Ambulance" in guidance
    assert "112" in guidance


def test_multi_symptom_respiratory_triad_assessment():
    """When fever, cough, and shortness of breath coexist, educational summary must address lower respiratory tract risks."""
    state = initialize_conversation_state()
    state["triage_round"] = 3
    state["collected_symptoms"] = [
        "I have a fever of 101 F",
        "Persistent dry cough for 3 days",
        "Occasionally short of breath",
    ]
    state["source"] = "AI Medical Knowledge"
    # Execute through fallback path when LLM fails or is unavailable
    with patch("app.agents.executor.get_llm", return_value=None):
        res = ExecutorAgent(state)
        content = res["generation"]
        assert "lower respiratory" in content.lower() or "pneumonia" in content.lower() or "bronchitis" in content.lower()
        assert "pulse oximeter" in content.lower() or "spo2" in content.lower()
        assert "prompt" in content.lower() or "in-person" in content.lower()


def test_third_person_hindi_cardiac_emergency_continuity():
    """Third-person Hindi cardiac emergency followed by 'Delhi me' must route correctly to Delhi dispatch."""
    # Turn 1
    state1 = initialize_conversation_state()
    state1["question"] = "mera dost ko heart attack aa gaya hai"
    res1 = PlannerAgent(state1)
    assert res1.get("is_urgent") is True
    assert "cardiac" in res1.get("urgent_category", "")

    # Turn 2: User says "Delhi me"
    history = [
        {"role": "user", "content": "mera dost ko heart attack aa gaya hai"},
        {"role": "assistant", "content": res1["urgent_advisory"], "source": "Urgent Medical Alert"},
    ]
    state2 = initialize_conversation_state()
    state2["question"] = "Delhi me"
    state2["conversation_history"] = history
    res2 = PlannerAgent(state2)

    assert res2.get("is_urgent") is True
    assert "102" in res2["urgent_advisory"]
    assert "CATS Ambulance" in res2["urgent_advisory"]
    assert "112" in res2["urgent_advisory"]
    assert "AIIMS" in res2["urgent_advisory"]


def test_non_medical_image_rejection_with_skin_override():
    """Non-medical green image must not produce clinical disease diagnosis under modality override."""
    from PIL import Image
    from app.services.disease_classifier import disease_classifier
    # Green image without clinical lesions
    green_img = Image.new("RGB", (256, 256), color=(20, 200, 30))
    res = disease_classifier.classify(green_img, routed_category="skin", modality_confirmed=True)
    assert res["status"] in ("unsupported_image", "inconclusive", "clinical_analysis_disabled")
    assert res.get("disease") is None
    assert res.get("status") != "analysis_complete"



