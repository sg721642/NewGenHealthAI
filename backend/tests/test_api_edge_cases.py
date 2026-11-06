"""Edge case tests for API routes — Deep Modular Architecture"""
from unittest.mock import patch
import pytest

from app.services import chat_service, db_service


@pytest.fixture
def auth_headers(test_client):
    """Create a verified test user and session token."""
    user = db_service.get_user_by_username("edge_case_user")
    if not user:
        user = db_service.create_user("edge_case_user", "password123")
    token = db_service.create_user_session(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def test_chat_with_header_session_id(test_client, auth_headers, mock_dependencies):
    """Test chat endpoint with X-Session-ID header and authentication"""
    headers, user = auth_headers
    conv = db_service.create_conversation(user.id)
    with patch.object(chat_service.clinical_engine, 'process_message') as mock_process:
        mock_process.return_value = {
            "response": "Test response",
            "source": "Test",
            "timestamp": "10:00 AM",
            "success": True
        }
        response = test_client.post(
            "/api/v1/chat",
            json={"message": "Hello"},
            headers={**headers, "X-Session-ID": conv.id}
        )
        assert response.status_code == 200


def test_get_history_with_header(test_client, auth_headers):
    """Test get history with X-Session-ID header and authentication"""
    headers, user = auth_headers
    conv = db_service.create_conversation(user.id)
    response = test_client.get("/api/v1/history", headers={**headers, "X-Session-ID": conv.id})
    assert response.status_code == 200


def test_delete_current_session(test_client, auth_headers):
    """Test deleting current session resets session ID"""
    headers, user = auth_headers
    response = test_client.post("/api/v1/new-chat", headers=headers)
    session_id = response.json()["session_id"]

    response = test_client.delete(f"/api/v1/session/{session_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_clear_with_header(test_client, auth_headers):
    """Test clear endpoint with X-Session-ID header and authentication"""
    headers, user = auth_headers
    conv = db_service.create_conversation(user.id)
    response = test_client.post("/api/v1/clear", headers={**headers, "X-Session-ID": conv.id})
    assert response.status_code == 200
    assert response.json()["message"] == "Clinical state and conversation history cleared"
