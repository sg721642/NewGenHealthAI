"""Test configuration and fixtures — Deep Modular Architecture"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add backend root to path so `app.*` imports work
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Stub optional heavy AI/ML libraries in sys.modules for offline/lightweight test environments
for mod_name in [
    'langchain_community',
    'langchain_community.tools',
    'langchain_community.tools.tavily_search',
    'langchain_community.utilities',
    'langchain_community.utilities.wikipedia',
    'langchain_community.document_loaders',
    'langchain_community.vectorstores',
    'langchain_groq',
    'langchain_huggingface',
    'langchain_huggingface.embeddings',
    'langchain_text_splitters',
]:
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except ImportError:
            sys.modules[mod_name] = MagicMock()

from app.main import app  # noqa: E402
from app.services import chat_service, db_service  # noqa: E402



@pytest.fixture(scope="function")
def test_client():
    """Test client fixture"""
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock all external dependencies using object-based patching to avoid CI import issues"""
    # 1. Create a workspace for all mocks
    mock_app_instance = MagicMock()
    mock_app_instance.ainvoke = AsyncMock(return_value={
        "generation": "Test response from AI",
        "source": "Test Source",
        "llm_success": True
    })
    mock_app_instance.invoke.return_value = {
        "generation": "Test response from AI",
        "source": "Test Source",
        "llm_success": True
    }

    # 2. Patch external AI/ML dependencies only (never mock database ownership)
    with patch.object(chat_service.clinical_engine, 'initialize_workflow'), \
         patch.object(chat_service.clinical_engine, 'workflow_app', mock_app_instance), \
         patch('app.main.process_pdf') as mock_pdf, \
         patch('app.main.get_or_create_vectorstore') as mock_vs:

        mock_vs.return_value = MagicMock()

        yield {
            "pdf": mock_pdf,
            "vector_store": mock_vs,
            "workflow_app": mock_app_instance,
        }


@pytest.fixture
def mock_session_middleware():
    """Mock session middleware behavior"""
    pass
