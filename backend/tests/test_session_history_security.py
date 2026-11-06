"""
NewGenHealthAI — tests/test_session_history_security.py
Comprehensive security tests for /api/v1/history endpoint:
- No X-Session-ID: empty history handled gracefully
- Repeated initial requests without X-Session-ID: zero database writes or unintended sessions
- Valid owned session ID: messages retrieved accurately
- Invalid session ID: returns HTTP 404
- Session owned by another user: strictly returns HTTP 404, zero cross-user exposure
- Existing session restoration: verified message order and content
"""

import os
import shutil
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import get_session_factory
from app.main import app
from app.models.message import Conversation, Message
from app.services.database_service import db_service

TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_data"))
TEST_DB_PATH = os.path.join(TEST_DIR, "session_security_test.db")


@pytest.fixture(scope="module")
def setup_isolated_db():
    """Create isolated test database and bind db_service."""
    os.makedirs(TEST_DIR, exist_ok=True)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False}
    )
    session_factory = get_session_factory(engine)

    old_engine = db_service.engine
    old_session = db_service.SessionLocal
    db_service.engine = engine
    db_service.SessionLocal = session_factory
    db_service.init_db()

    yield engine, session_factory

    engine.dispose()
    db_service.engine = old_engine
    db_service.SessionLocal = old_session
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


@pytest.fixture
def client(setup_isolated_db):
    """FastAPI TestClient with isolated DB."""
    return TestClient(app)


@pytest.fixture
def auth_users(setup_isolated_db):
    """Create two test users: User A and User B."""
    user_a = db_service.get_user_by_username("history_user_a")
    if not user_a:
        user_a = db_service.create_user("history_user_a", "password_a_123")
    token_a = db_service.create_user_session(user_a.id)

    user_b = db_service.get_user_by_username("history_user_b")
    if not user_b:
        user_b = db_service.create_user("history_user_b", "password_b_123")
    token_b = db_service.create_user_session(user_b.id)

    return {
        "user_a": user_a,
        "token_a": token_a,
        "auth_a": {"Authorization": f"Bearer {token_a}"},
        "user_b": user_b,
        "token_b": token_b,
        "auth_b": {"Authorization": f"Bearer {token_b}"},
    }


def test_history_no_session_id_returns_empty_gracefully(client, auth_users):
    """Initial request with no X-Session-ID returns HTTP 200 with empty messages."""
    response = client.get("/api/v1/history", headers=auth_users["auth_a"])
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["messages"] == []
    assert "session_id" in data
    assert len(data["session_id"]) > 0


def test_repeated_initial_requests_do_not_create_database_rows(client, auth_users):
    """
    Repeated initial requests without X-Session-ID must NOT create unintended
    sessions or rows in conversations or messages tables.
    """
    with db_service.get_session() as session:
        initial_convs = session.execute(
            select(func.count(Conversation.id)).where(Conversation.user_id == auth_users["user_a"].id)
        ).scalar()
        initial_msgs = session.execute(
            select(func.count(Message.id)).where(Message.user_id == auth_users["user_a"].id)
        ).scalar()

    # Perform 5 consecutive GET /history requests without X-Session-ID
    for _ in range(5):
        resp = client.get("/api/v1/history", headers=auth_users["auth_a"])
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    # Verify database row count remains unchanged
    with db_service.get_session() as session:
        final_convs = session.execute(
            select(func.count(Conversation.id)).where(Conversation.user_id == auth_users["user_a"].id)
        ).scalar()
        final_msgs = session.execute(
            select(func.count(Message.id)).where(Message.user_id == auth_users["user_a"].id)
        ).scalar()

    assert final_convs == initial_convs, f"Expected {initial_convs} conversations, got {final_convs}"
    assert final_msgs == initial_msgs, f"Expected {initial_msgs} messages, got {final_msgs}"


def test_history_with_valid_owned_session_returns_messages(client, auth_users):
    """A valid owned session ID returns HTTP 200 with accurate messages."""
    session_id = str(uuid.uuid4())
    user_id = auth_users["user_a"].id

    # Create conversation and save messages
    db_service.create_conversation(session_id=session_id, user_id=user_id, title="Test Consultation")
    db_service.save_message(session_id, "user", "I have a sore throat", user_id=user_id)
    db_service.save_message(session_id, "assistant", "Please rest and drink warm water", user_id=user_id)

    headers = dict(auth_users["auth_a"])
    headers["X-Session-ID"] = session_id

    response = client.get("/api/v1/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["session_id"] == session_id
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "I have a sore throat"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == "Please rest and drink warm water"


def test_history_with_invalid_session_id_returns_404(client, auth_users):
    """An invalid, non-existent session ID returns HTTP 404."""
    invalid_session_id = str(uuid.uuid4())
    headers = dict(auth_users["auth_a"])
    headers["X-Session-ID"] = invalid_session_id

    response = client.get("/api/v1/history", headers=headers)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Conversation not found"


def test_history_with_unowned_session_id_returns_404_no_data_leak(client, auth_users):
    """
    An explicitly supplied session ID owned by another user strictly returns HTTP 404.
    Unauthorized history is NEVER exposed.
    """
    session_b = str(uuid.uuid4())
    user_b_id = auth_users["user_b"].id

    # User B creates private conversation
    db_service.create_conversation(session_id=session_b, user_id=user_b_id, title="User B Confidential")
    db_service.save_message(session_b, "user", "Confidential medical record of User B", user_id=user_b_id)
    db_service.save_message(session_b, "assistant", "User B diagnosis details", user_id=user_b_id)

    # User A attempts to access User B's session history
    headers_a = dict(auth_users["auth_a"])
    headers_a["X-Session-ID"] = session_b

    response = client.get("/api/v1/history", headers=headers_a)
    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"

    # Verify that User B can legitimately access their own session
    headers_b = dict(auth_users["auth_b"])
    headers_b["X-Session-ID"] = session_b

    response_b = client.get("/api/v1/history", headers=headers_b)
    assert response_b.status_code == 200
    assert len(response_b.json()["messages"]) == 2
    assert response_b.json()["messages"][0]["content"] == "Confidential medical record of User B"


def test_existing_session_restoration(client, auth_users):
    """Verify that existing session restoration maintains message chronological order."""
    session_id = str(uuid.uuid4())
    user_id = auth_users["user_a"].id

    db_service.create_conversation(session_id=session_id, user_id=user_id, title="Restoration Test")
    for i in range(5):
        db_service.save_message(session_id, "user", f"Question {i}", user_id=user_id)
        db_service.save_message(session_id, "assistant", f"Answer {i}", user_id=user_id)

    headers = dict(auth_users["auth_a"])
    headers["X-Session-ID"] = session_id

    response = client.get(f"/api/v1/session/{session_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["messages"]) == 10
    for i in range(5):
        assert data["messages"][2 * i]["content"] == f"Question {i}"
        assert data["messages"][2 * i + 1]["content"] == f"Answer {i}"
