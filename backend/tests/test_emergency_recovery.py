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

