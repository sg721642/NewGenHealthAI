"""Tests for all agents — Deep Modular Architecture"""
import os
import sys
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.agents.executor import ExecutorAgent  # noqa: E402
from app.agents.explanation import ExplanationAgent  # noqa: E402
from app.agents.llm_agent import LLMAgent  # noqa: E402
from app.agents.memory import MemoryAgent  # noqa: E402
from app.agents.planner import PlannerAgent  # noqa: E402
from app.agents.retriever import RetrieverAgent  # noqa: E402
from app.agents.tavily import TavilyAgent  # noqa: E402
from app.agents.wikipedia import WikipediaAgent  # noqa: E402
from app.core.state import initialize_conversation_state  # noqa: E402


# --- Planner Agent Tests ---
def test_planner_agent_medical():
    state = initialize_conversation_state()
    state["question"] = "I have a high fever"
    new_state = PlannerAgent(state)
    assert new_state["current_tool"] == "retriever"


def test_planner_agent_general():
    state = initialize_conversation_state()
    state["question"] = "Hello there"
    new_state = PlannerAgent(state)
    assert new_state["current_tool"] == "llm_agent"


# --- Retriever Agent Tests ---
def test_retriever_agent_success():
    state = initialize_conversation_state()
    state["question"] = "fever"

    with patch('app.agents.retriever.get_retriever') as mock_get_retriever:
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [Document(page_content="Fever details " * 10)]
        mock_get_retriever.return_value = mock_retriever

        new_state = RetrieverAgent(state)
        assert new_state["rag_success"] is True
        assert len(new_state["documents"]) > 0


def test_retriever_agent_failure():
    state = initialize_conversation_state()
    state["question"] = "unknown"
    with patch('app.agents.retriever.get_retriever') as mock_get:
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = []
        mock_get.return_value = mock_retriever

        new_state = RetrieverAgent(state)
        assert new_state["rag_success"] is False


def test_retriever_agent_no_tool():
    state = initialize_conversation_state()
    with patch('app.agents.retriever.get_retriever', return_value=None):
        new_state = RetrieverAgent(state)
        assert new_state["rag_success"] is False


# --- LLM Agent Tests ---
def test_llm_agent():
    state = initialize_conversation_state()
    state["question"] = "Hi"
    with patch('app.agents.llm_agent.get_llm') as mock_get:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Hello there my friend, this is a long enough response."
        mock_get.return_value = mock_llm

        new_state = LLMAgent(state)
        assert new_state["llm_success"] is True
        assert new_state["generation"] == "Hello there my friend, this is a long enough response."


def test_llm_agent_no_tool():
    state = initialize_conversation_state()
    with patch('app.agents.llm_agent.get_llm', return_value=None):
        new_state = LLMAgent(state)
        assert new_state["llm_success"] is False
        assert "unavailable" in new_state["generation"]


# --- Wikipedia Agent Tests ---
def test_wikipedia_agent():
    state = initialize_conversation_state()
    # 'fever symptoms' contains allowlisted terms 'fever' and 'symptoms'
    state["question"] = "fever symptoms"
    with patch('app.agents.wikipedia.get_wikipedia_wrapper') as mock_get:
        mock_wiki = MagicMock()
        mock_wiki.run.return_value = "Flu information is very important to know. " * 10
        mock_get.return_value = mock_wiki
        new_state = WikipediaAgent(state)
        assert new_state["wiki_success"] is True


def test_wikipedia_agent_privacy_blocks_non_medical_query():
    """Verify raw personal queries without allowlisted medical terms are NOT forwarded externally."""
    state = initialize_conversation_state()
    state["question"] = "I went to the park yesterday and my friend Bob was there"  # no medical terms
    with patch('app.agents.wikipedia.get_wikipedia_wrapper') as mock_get:
        mock_wiki = MagicMock()
        mock_wiki.run.return_value = "Wikipedia content " * 100
        mock_get.return_value = mock_wiki
        new_state = WikipediaAgent(state)
        # Should NOT search — no allowlisted medical terms extractable
        assert new_state["wiki_success"] is False
        mock_wiki.run.assert_not_called()


def test_wikipedia_agent_no_tool():
    state = initialize_conversation_state()
    with patch('app.agents.wikipedia.get_wikipedia_wrapper', return_value=None):
        new_state = WikipediaAgent(state)
        assert new_state["wiki_success"] is False


def test_wikipedia_agent_short_content():
    state = initialize_conversation_state()
    state["question"] = "fever pain"
    with patch('app.agents.wikipedia.get_wikipedia_wrapper') as mock_get:
        mock_wiki = MagicMock()
        mock_wiki.run.return_value = "short"
        mock_get.return_value = mock_wiki
        new_state = WikipediaAgent(state)
        assert new_state["wiki_success"] is False


# --- Tavily Agent Tests ---
def test_tavily_agent():
    state = initialize_conversation_state()
    # 'symptoms treatment' contains allowlisted medical terms
    state["question"] = "symptoms treatment"
    with patch('app.agents.tavily.get_tavily_search') as mock_get:
        mock_tav = MagicMock()
        mock_tav.invoke.return_value = [
            {"content": "Medical treatment information is important. " * 5, "url": "https://health.gov/article"}]
        mock_get.return_value = mock_tav
        new_state = TavilyAgent(state)
        assert new_state["tavily_success"] is True


def test_tavily_agent_privacy_blocks_non_medical_query():
    """Verify raw personal narratives without medical terms are NOT forwarded to Tavily."""
    state = initialize_conversation_state()
    state["question"] = "I need to buy some groceries"  # no medical terms
    with patch('app.agents.tavily.get_tavily_search') as mock_get:
        mock_tav = MagicMock()
        mock_tav.invoke.return_value = [{"content": "Results " * 20, "url": "https://example.com"}]
        mock_get.return_value = mock_tav
        new_state = TavilyAgent(state)
        # Should NOT search — no allowlisted medical terms extractable
        assert new_state["tavily_success"] is False
        mock_tav.invoke.assert_not_called()


def test_tavily_agent_no_tool():
    state = initialize_conversation_state()
    with patch('app.agents.tavily.get_tavily_search', return_value=None):
        new_state = TavilyAgent(state)
        assert new_state["tavily_success"] is False


def test_tavily_agent_fail():
    state = initialize_conversation_state()
    with patch('app.agents.tavily.get_tavily_search') as mock_get:
        mock_tav = MagicMock()
        mock_tav.invoke.side_effect = Exception("error")
        mock_get.return_value = mock_tav
        new_state = TavilyAgent(state)
        assert new_state["tavily_success"] is False
        assert new_state["documents"] == []


# --- Memory Agent Tests ---
def test_memory_agent():
    state = initialize_conversation_state()
    state["conversation_history"] = [{"role": "user", "content": str(i)} for i in range(25)]

    new_state = MemoryAgent(state)

    assert len(new_state["conversation_history"]) == 20
    assert new_state["conversation_history"][-1]["content"] == "24"


# --- Executor Agent Tests ---
def test_executor_agent_with_docs():
    state = initialize_conversation_state()
    state["question"] = "What is X?"
    state["documents"] = [Document(page_content="X is Y.")]

    with patch('app.agents.executor.get_llm') as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "X is likely Y based on docs."
        mock_get_llm.return_value = mock_llm

        new_state = ExecutorAgent(state)

        assert new_state["generation"] == "X is likely Y based on docs."
        assert len(new_state["conversation_history"]) == 2  # user + assistant


def test_executor_agent_no_llm():
    state = initialize_conversation_state()
    state["question"] = "test"
    with patch('app.agents.executor.get_llm', return_value=None):
        new_state = ExecutorAgent(state)
        assert "temporarily unavailable" in new_state["generation"]


def test_executor_agent_llm_fail():
    state = initialize_conversation_state()
    state["question"] = "test"
    state["documents"] = [Document(page_content="some content")]
    with patch('app.agents.executor.get_llm') as mock_get:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("error")
        mock_get.return_value = mock_llm
        new_state = ExecutorAgent(state)
        assert "consult with a healthcare professional" in new_state["generation"].lower()


# --- Explanation Agent Tests ---
def test_explanation_agent():
    state = initialize_conversation_state()
    new_state = ExplanationAgent(state)
    assert new_state == state


# --- LLM Safe Invocation & OFFLINE_MODE Unit Tests ---
def test_invoke_llm_safe_offline_mode_returns_none():
    from app.agents.executor import _invoke_llm_safe

    mock_llm = MagicMock()
    with patch.dict(os.environ, {"OFFLINE_MODE": "true"}):
        with patch("app.agents.executor.invoke_llm_with_fallback") as mock_fallback:
            result = _invoke_llm_safe(mock_llm, "test prompt")
            assert result is None
            mock_llm.invoke.assert_not_called()
            mock_fallback.assert_not_called()


def test_invoke_llm_safe_normal_mode_invokes_llm():
    from app.agents.executor import _invoke_llm_safe

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Mocked answer from primary model")
    with patch.dict(os.environ, {"OFFLINE_MODE": "false"}):
        with patch("app.agents.executor.invoke_llm_with_fallback") as mock_fallback:
            result = _invoke_llm_safe(mock_llm, "test prompt")
            assert result.content == "Mocked answer from primary model"
            mock_llm.invoke.assert_called_once_with("test prompt")
            mock_fallback.assert_not_called()


def test_invoke_llm_safe_normal_mode_fallback_on_deprecation():
    from app.agents.executor import _invoke_llm_safe

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("404 Model llama-3.1-8b-instant decommissioned and does not exist")
    mock_fallback_resp = MagicMock(content="Mocked answer from fallback model")

    with patch.dict(os.environ, {"OFFLINE_MODE": "false"}):
        with patch("app.agents.executor.invoke_llm_with_fallback", return_value=mock_fallback_resp) as mock_fallback:
            result = _invoke_llm_safe(mock_llm, "test prompt")
            assert result.content == "Mocked answer from fallback model"
            mock_fallback.assert_called_once_with("test prompt", temperature=0.3, max_tokens=2048)


def test_invoke_llm_safe_normal_mode_when_llm_none():
    from app.agents.executor import _invoke_llm_safe

    mock_fallback_resp = MagicMock(content="Mocked answer when primary is None")

    with patch.dict(os.environ, {"OFFLINE_MODE": "false"}):
        with patch("app.agents.executor.invoke_llm_with_fallback", return_value=mock_fallback_resp) as mock_fallback:
            result = _invoke_llm_safe(None, "test prompt")
            assert result.content == "Mocked answer when primary is None"
            mock_fallback.assert_called_once_with("test prompt", temperature=0.3, max_tokens=2048)


def test_offline_mode_env_string_parsing():
    """Verify that string 'false' never evaluates to boolean True."""
    for false_str in ["false", "FALSE", "0", "no", "", "None"]:
        parsed = false_str.strip().lower() in ("true", "1", "yes")
        assert parsed is False, f"String '{false_str}' unexpectedly evaluated to True"

    for true_str in ["true", "TRUE", "1", "yes", "YES"]:
        parsed = true_str.strip().lower() in ("true", "1", "yes")
        assert parsed is True, f"String '{true_str}' unexpectedly evaluated to False"


def test_retriever_agent_unavailable_visibility():
    """Verify RetrieverAgent marks capability as unavailable when retriever is None."""
    state = initialize_conversation_state()
    state["question"] = "test query"
    with patch("app.agents.retriever.get_retriever", return_value=None):
        new_state = RetrieverAgent(state)
        assert new_state["rag_success"] is False
        assert new_state["rag_status"] == "unavailable"
        assert new_state["documents"] == []
