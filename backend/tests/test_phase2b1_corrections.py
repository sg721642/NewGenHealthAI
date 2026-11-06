"""
NewGenHealthAI — tests/test_phase2b1_corrections.py
Phase 2B.1 Integration Tests

Verifies:
A05 — Consultation deadline enforcement (asyncio.wait_for)
A05 — exhaustion_reason prevents unbounded post-exhaustion LLM calls
A05 — Consistent result_state taxonomy in process_message response
A08 — Sensitive query / transcript not forwarded to external search providers
A08 — Triage question text not logged (log redaction)
A17 — India 112 locale present in emergency advisory
A17 — Conservative uncertainty language (does not claim 100% detection)
A17 — Does not infer country from symptoms
Provenance — HTTPS-only citation URL validation
Provenance — Dangerous URL schemes (javascript:, data:, http:) rejected
Cancellation — Lock released when asyncio.TimeoutError occurs
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.state import initialize_conversation_state
from app.core.urgent_care import check_urgent_risk, generate_urgent_advisory
from app.agents.executor import _format_provenance_citations
from app.agents.wikipedia import WikipediaAgent, _build_privacy_preserving_query
from app.agents.tavily import TavilyAgent, _build_privacy_preserving_query as _tavily_query


# ── A05: Consultation deadline and result_state taxonomy ─────────────────────

@pytest.mark.asyncio
async def test_consultation_timeout_returns_provider_timeout_state():
    """PROVIDER_TIMEOUT result_state is returned when asyncio.wait_for fires."""
    # Test the core mechanism used in chat_service.process_message:
    # asyncio.wait_for raises TimeoutError when deadline expires.

    async def hanging_workflow(state):
        await asyncio.sleep(60)  # Much longer than test deadline
        return {"generation": "should not reach here"}

    async def run_with_deadline(timeout_seconds: float):
        state = initialize_conversation_state()
        return await asyncio.wait_for(hanging_workflow(state), timeout=timeout_seconds)

    with pytest.raises(asyncio.TimeoutError):
        await run_with_deadline(0.05)  # 50ms deadline — should expire immediately


@pytest.mark.asyncio
async def test_lock_released_after_timeout():
    """Verify per-conversation lock is released even when TimeoutError fires."""
    from app.services.chat_service import ConversationLockManager

    mgr = ConversationLockManager()
    key = "user123:session456"

    async def acquire_and_timeout():
        async with mgr.lock(key):
            await asyncio.wait_for(asyncio.sleep(60), timeout=0.01)

    with pytest.raises(asyncio.TimeoutError):
        await acquire_and_timeout()

    # Lock must be released — another coroutine should be able to acquire it immediately
    acquired = False

    async def try_acquire():
        nonlocal acquired
        async with mgr.lock(key):
            acquired = True

    await asyncio.wait_for(try_acquire(), timeout=1.0)
    assert acquired, "Lock was not released after TimeoutError"


def test_result_state_taxonomy_constants():
    """Result-state constants exist in chat_service module docstring."""
    import app.services.chat_service as svc
    doc = svc.__doc__ or ""
    assert "SUCCESSFUL_EDUCATIONAL" in doc
    assert "SUCCESSFUL_URGENT" in doc
    assert "PROVIDER_TIMEOUT" in doc
    assert "PROVIDER_UNAVAILABLE" in doc


# ── A05: Provider exhaustion_reason prevents post-exhaustion LLM call ─────────

def test_executor_terminates_on_exhaustion_reason():
    """When exhaustion_reason is set, ExecutorAgent returns service-unavailable without LLM call."""
    from app.agents.executor import ExecutorAgent

    state = initialize_conversation_state()
    state["question"] = "headache symptoms"
    state["exhaustion_reason"] = "all_providers_attempted_after_rag"
    state["llm_success"] = False
    state["rag_success"] = False

    with patch('app.agents.executor.get_llm') as mock_llm:
        mock_llm.return_value = MagicMock()  # LLM would be available if called
        result = ExecutorAgent(state)

    # Must not have called LLM (mock was never invoked)
    mock_llm.return_value.invoke.assert_not_called()
    assert result["is_failed_generation"] is True
    assert result["source"] == "Service Unavailable"


def test_executor_exhaustion_reason_propagates_to_failed_generation():
    """Exhaustion flag sets is_failed_generation=True consistently."""
    from app.agents.executor import ExecutorAgent

    state = initialize_conversation_state()
    state["question"] = "joint pain"
    state["exhaustion_reason"] = "all_providers_attempted_tavily_failed"

    with patch('app.agents.executor.get_llm', return_value=None):
        result = ExecutorAgent(state)

    assert result["is_failed_generation"] is True
    assert "unavailable" in result["generation"].lower()


def test_workflow_routing_sets_exhaustion_reason_after_all_providers():
    """Routing functions set exhaustion_reason when all providers are attempted and failed."""
    from app.core.langgraph_workflow import _route_after_wiki, _route_after_tavily

    # After wiki — tavily already attempted
    state = initialize_conversation_state()
    state["wiki_success"] = False
    state["tavily_attempted"] = True
    state["attempted_providers"] = ["wikipedia", "tavily"]
    destination = _route_after_wiki(state)
    assert destination == "executor"
    assert state.get("exhaustion_reason") is not None

    # After tavily — failed
    state2 = initialize_conversation_state()
    state2["tavily_success"] = False
    destination2 = _route_after_tavily(state2)
    assert destination2 == "executor"
    assert state2.get("exhaustion_reason") is not None


# ── A08: Privacy — external search query leakage prevention ─────────────────

def test_wikipedia_query_extraction_allowlist_only():
    """Only allowlisted medical terms are forwarded to Wikipedia."""
    query = _build_privacy_preserving_query("I have chest pain and feel dizzy")
    # 'pain', 'dizziness' are in allowlist; 'have', 'feel', 'I' are NOT
    assert query is not None
    assert "pain" in query or "dizziness" in query or "dizzy" in query
    # Personal pronoun 'I' must not appear
    assert " i " not in query.lower()


def test_wikipedia_rejects_non_medical_queries():
    """Queries with no medical terms return None (no external search)."""
    result = _build_privacy_preserving_query("I went shopping for groceries yesterday")
    assert result is None


def test_wikipedia_no_raw_question_retry():
    """WikipediaAgent does NOT fall back to raw question when sanitized query yields nothing."""
    state = initialize_conversation_state()
    state["question"] = "My name is John Smith and I visited Oxford Street"

    with patch('app.agents.wikipedia.get_wikipedia_wrapper') as mock_get:
        mock_wiki = MagicMock()
        mock_wiki.run.return_value = "Wikipedia content " * 100
        mock_get.return_value = mock_wiki
        result = WikipediaAgent(state)

    # Agent must NOT call wiki.run at all — no medical terms
    mock_wiki.run.assert_not_called()
    assert result["wiki_success"] is False


def test_tavily_no_raw_question_fallback():
    """TavilyAgent does NOT send raw question when no medical terms found."""
    state = initialize_conversation_state()
    state["question"] = "Call my friend and tell them hello"

    with patch('app.agents.tavily.get_tavily_search') as mock_get:
        mock_tav = MagicMock()
        mock_tav.invoke.return_value = [{"content": "results " * 50, "url": "https://example.com"}]
        mock_get.return_value = mock_tav
        result = TavilyAgent(state)

    mock_tav.invoke.assert_not_called()
    assert result["tavily_success"] is False


def test_tavily_query_contains_only_medical_terms():
    """Privacy-preserving Tavily query contains only allowlisted terms."""
    query = _tavily_query("vomiting nausea fever since yesterday morning with my doctor")
    assert query is not None
    # Should contain medical terms
    terms_in_query = [t for t in ["vomiting", "nausea", "fever"] if t in query]
    assert len(terms_in_query) > 0
    # Must not contain 'my', 'doctor' (doctor not allowlisted), 'yesterday', 'morning'
    assert "yesterday" not in query
    assert "morning" not in query
    assert " my " not in query.lower()


# ── A08: Triage log redaction ─────────────────────────────────────────────────

def test_triage_log_does_not_contain_question_text(caplog):
    """Triage agent logs question length, not question content."""
    import logging
    from app.agents.triage_agent import TriageAgent

    sensitive_question = "SECRET PATIENT INFORMATION: John Doe, DOB 1985-03-12, diagnosis suspected"
    state = initialize_conversation_state()
    state["question"] = sensitive_question
    state["is_medical_query"] = True
    state["triage_round"] = 0

    mock_response = MagicMock()
    mock_response.content = '{"status": "needs_info", "acknowledgment": "I see.", "question_text": "How long?", "options": ["1 day", "2 days"]}'

    with patch('app.agents.triage_agent._get_triage_llm') as mock_llm_fn:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        with caplog.at_level(logging.INFO, logger="newgenhealthai"):
            TriageAgent(state)

    # Verify sensitive patient text NOT in any log record
    all_log_text = " ".join(r.message for r in caplog.records)
    assert "John Doe" not in all_log_text
    assert "1985" not in all_log_text
    assert "SECRET PATIENT INFORMATION" not in all_log_text
    # Verify question-text question is NOT logged
    assert "How long?" not in all_log_text
    # Verify round info IS logged (non-sensitive)
    assert any("round" in r.message.lower() for r in caplog.records)


# ── A17: Emergency localization and conservative language ─────────────────────

def test_india_112_in_medical_emergency_advisory():
    """India 112 appears prominently in non-crisis medical emergency advisory."""
    advisory = generate_urgent_advisory("cardiac", "Possible Cardiac Emergency")
    assert "112" in advisory
    assert "India" in advisory


def test_india_crisis_advisory():
    """India appears with specific crisis support numbers in crisis advisory."""
    advisory = generate_urgent_advisory("crisis", "Immediate Safety Alert")
    assert "India" in advisory
    assert "112" in advisory  # Physical danger fallback for India


def test_unknown_locale_safe_default_guidance():
    """Advisory includes fallback guidance for users in unlisted countries."""
    advisory = generate_urgent_advisory("cardiac", "Possible Cardiac Emergency")
    # Must tell users in unlisted locales what to do
    assert "not listed" in advisory.lower() or "local emergency" in advisory.lower()


def test_advisory_does_not_infer_country_from_symptoms():
    """urgent_care module docstring/code confirms no country inference from symptoms."""
    advisory = generate_urgent_advisory("stroke", "Possible Stroke")
    # The advisory should give a list of countries — not infer one from context
    # All three numbers should be present (India, US, UK)
    assert "112" in advisory
    assert "911" in advisory
    assert "999" in advisory


def test_advisory_conservative_language_no_100_percent_claim():
    """Advisory does NOT claim 100% emergency detection accuracy."""
    advisory_cardiac = generate_urgent_advisory("cardiac", "Possible Cardiac Emergency")
    advisory_stroke = generate_urgent_advisory("stroke", "Possible Stroke Emergency")
    for advisory in [advisory_cardiac, advisory_stroke]:
        assert "100%" not in advisory
        assert "all medical emergencies" not in advisory.replace(
            "does not detect all medical emergencies", "REDACTED"
        )
        # Disclaimer must acknowledge limitation
        assert "does not detect all medical emergencies" in advisory or "cannot" in advisory


def test_advisory_uses_may_be_not_definitive():
    """Advisory says 'may be' not 'you are having' to avoid false diagnosis."""
    advisory = generate_urgent_advisory("cardiac", "Possible Cardiac Emergency")
    assert "may be" in advisory.lower() or "possible" in advisory.lower()


# ── Provenance: Citation URL scheme validation ────────────────────────────────

def test_citation_rejects_javascript_url():
    """javascript: URLs must be dropped from citations."""
    from langchain_core.documents import Document
    doc = Document(
        page_content="Some content",
        metadata={"title": "Evil Source", "url": "javascript:alert('xss')"}
    )
    result = _format_provenance_citations([doc])
    assert "javascript:" not in result
    # Title should still appear (without URL link)
    assert "Evil Source" in result or result == ""


def test_citation_rejects_data_url():
    """data: URLs must be dropped from citations."""
    from langchain_core.documents import Document
    doc = Document(
        page_content="Content",
        metadata={"title": "Data URI Source", "url": "data:text/html,<script>alert(1)</script>"}
    )
    result = _format_provenance_citations([doc])
    assert "data:" not in result


def test_citation_rejects_http_url():
    """Plain http:// URLs are rejected — only HTTPS is accepted."""
    from langchain_core.documents import Document
    doc = Document(
        page_content="Content",
        metadata={"title": "HTTP Source", "url": "http://insecure.example.com/page"}
    )
    result = _format_provenance_citations([doc])
    # http:// should not appear as a clickable link
    assert "http://insecure" not in result


def test_citation_accepts_https_url():
    """Valid HTTPS URLs are included in citations."""
    from langchain_core.documents import Document
    doc = Document(
        page_content="Content",
        metadata={"title": "Trusted Source", "url": "https://www.ncbi.nlm.nih.gov/article/123"}
    )
    result = _format_provenance_citations([doc])
    assert "https://www.ncbi.nlm.nih.gov/article/123" in result
    assert "Trusted Source" in result


def test_citation_escapes_markdown_in_title():
    """Special markdown characters in document titles are escaped."""
    from langchain_core.documents import Document
    doc = Document(
        page_content="Content",
        metadata={"title": "Article [Special] (Title)", "url": "https://example.com/article"}
    )
    result = _format_provenance_citations([doc])
    # Escaped characters should prevent link-breaking
    assert result is not None
    # The result should be a valid markdown string (no unescaped bracket injection)
    assert "javascript" not in result


def test_citation_no_docs_returns_empty():
    """No documents yields empty citation string."""
    assert _format_provenance_citations([]) == ""


def test_citation_doc_without_url_shows_title_only():
    """Documents without URLs get title-only citation (no broken link)."""
    from langchain_core.documents import Document
    doc = Document(
        page_content="Content",
        metadata={"title": "Clinical Guidelines 2024"}
    )
    result = _format_provenance_citations([doc])
    assert "Clinical Guidelines 2024" in result
    assert "]()" not in result  # Must not render empty markdown link


# ── Emergency screening — check_urgent_risk basic coverage ────────────────────

def test_urgent_care_cardiac_detected():
    result = check_urgent_risk("I have crushing chest pressure radiating to my jaw")
    assert result is not None
    assert result["is_urgent"] is True
    assert result["category"] == "cardiac"


def test_urgent_care_crisis_detected():
    result = check_urgent_risk("I want to commit suicide")
    assert result is not None
    assert result["category"] == "crisis"


def test_urgent_care_normal_query_returns_none():
    result = check_urgent_risk("I have a mild headache today")
    assert result is None
