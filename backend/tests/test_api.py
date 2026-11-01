"""API Endpoint Tests — Updated for Phase 1A Authentication and Ownership"""
from unittest.mock import patch
import pytest

from app.services import chat_service, db_service


@pytest.fixture
def auth_headers(test_client):
    """Create a verified test user and session token."""
    user = db_service.get_user_by_username("test_api_user")
    if not user:
        user = db_service.create_user("test_api_user", "password123")
    token = db_service.create_user_session(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def test_health_check(test_client):
    """Health endpoint remains public."""
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "NewGenHealthAI Backend v3"
    assert "ai_ready" in data


def test_unauthenticated_requests_fail_with_401(test_client):
    """All private endpoints reject unauthenticated requests with 401."""
    assert test_client.get("/api/v1/sessions").status_code == 401
    assert test_client.get("/api/v1/history").status_code == 401
    assert test_client.post("/api/v1/new-chat").status_code == 401
    assert test_client.post("/api/v1/clear").status_code == 401
    assert test_client.post("/api/v1/chat", json={"message": "hi"}).status_code == 401


def test_new_chat(test_client, auth_headers):
    headers, user = auth_headers
    response = test_client.post("/api/v1/new-chat", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "session_id" in data
    assert data["message"] == "New clinical session created"


def test_get_sessions(test_client, auth_headers):
    headers, user = auth_headers
    with patch.object(db_service, 'get_all_sessions') as mock_get:
        mock_get.return_value = [{"session_id": "123", "preview": "hi", "last_active": "2024-01-01"}]
        response = test_client.get("/api/v1/sessions", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == "123"


def test_chat_flow_success(test_client, auth_headers, mock_dependencies):
    headers, user = auth_headers
    mock_dependencies["workflow_app"].ainvoke.return_value = {
        "generation": "Test connection successful",
        "source": "Mock Brain",
        "llm_success": True
    }

    response = test_client.post("/api/v1/new-chat", headers=headers)
    session_id = response.json()["session_id"]

    chat_response = test_client.post(
        "/api/v1/chat",
        json={"message": "Hello AI"},
        headers={**headers, "X-Session-ID": session_id}
    )

    assert chat_response.status_code == 200
    data = chat_response.json()
    assert data["success"] is True
    assert data["response"] == "Test connection successful"
    assert data["source"] == "Mock Brain"


def test_chat_flow_system_not_initialized(test_client, auth_headers):
    headers, user = auth_headers
    with patch.object(chat_service.clinical_engine, 'workflow_app', None):
        response = test_client.post(
            "/api/v1/chat",
            json={"message": "Hello"},
            headers=headers
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "System not initialized"


def test_get_history(test_client, auth_headers):
    headers, user = auth_headers
    with patch.object(db_service, 'get_chat_history') as mock_hist:
        mock_hist.return_value = [{"role": "user", "content": "hi"}]
        response = test_client.get(
            "/api/v1/history",
            headers={**headers, "X-Session-ID": "test-sess"}
        )
        assert response.status_code == 200
        assert len(response.json()["messages"]) == 1


def test_load_session(test_client, auth_headers):
    headers, user = auth_headers
    with patch.object(db_service, 'get_chat_history') as mock_hist:
        mock_hist.return_value = []
        response = test_client.get("/api/v1/session/test-session-id", headers=headers)
        assert response.status_code == 200
        assert response.json()["session_id"] == "test-session-id"


def test_delete_session(test_client, auth_headers):
    headers, user = auth_headers
    with patch.object(chat_service.clinical_engine, 'delete_conversation') as mock_del:
        mock_del.return_value = True
        response = test_client.delete("/api/v1/session/test-id", headers=headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Session deleted"
        mock_del.assert_called_once_with("test-id", user_id=user.id)


def test_clear_conversation(test_client, auth_headers):
    headers, user = auth_headers
    conv = db_service.create_conversation(user_id=user.id)
    with patch.object(chat_service.clinical_engine, 'clear_conversation') as mock_clear:
        mock_clear.return_value = True
        response = test_client.post(
            "/api/v1/clear",
            headers={**headers, "X-Session-ID": conv.id}
        )
        assert response.status_code == 200
        assert "cleared" in response.json()["message"].lower()


