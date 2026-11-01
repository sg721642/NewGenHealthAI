"""
NewGenHealthAI — backend/tests/test_phase6_multiuser_e2e.py
Phase 6 End-to-End Multi-User Security, Isolation, and Lifecycle Regression Suite.

Verifies:
1. Multi-user registration, authentication, and session token generation.
2. Complete data isolation between User A and User B consultations.
3. Strict cross-account denial (read, write, list, clear, delete).
4. Authoritative session verification & fail-closed 404 behavior for invalid session IDs.
5. Immediate token revocation on logout (subsequent calls return 401).
6. Authentication enforcement across all clinical endpoints (chat, sessions, history, voice, image).
"""

import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import get_session_factory
from app.main import app
from app.services.chat_service import clinical_engine
from app.services.database_service import db_service

TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_data"))
TEST_DB_PATH = os.path.join(TEST_DIR, "phase6_e2e_test.db")


@pytest.fixture(scope="module")
def setup_phase6_env():
    """Create isolated SQLite database for Phase 6 E2E tests."""
    os.makedirs(TEST_DIR, exist_ok=True)
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False}
    )
    session_factory = get_session_factory(engine)

    old_engine = db_service.engine
    old_session = db_service.SessionLocal
    db_service.engine = engine
    db_service.SessionLocal = session_factory
    db_service.init_db()

    # Mock workflow_app for clinical engine to avoid heavy ML downloads
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={
            "generation": "Triage assessment completed for informational intake.",
            "source": "clinical-guidelines",
            "llm_success": True,
        }
    )
    old_workflow = clinical_engine.workflow_app
    clinical_engine.workflow_app = mock_workflow

    yield engine, session_factory

    # Teardown
    engine.dispose()
    db_service.engine = old_engine
    db_service.SessionLocal = old_session
    clinical_engine.workflow_app = old_workflow
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


@pytest.fixture
def client(setup_phase6_env):
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_multiuser_registration_and_login(client):
    """Verify registration and authentication for distinct User A and User B."""
    # Register User A
    res_reg_a = client.post(
        "/api/v1/auth/register",
        json={"username": "clinician_alice", "password": "AliceStrongPassword123!"},
    )
    assert res_reg_a.status_code == 200
    data_a = res_reg_a.json()
    assert data_a["success"] is True
    assert "token" in data_a
    token_a = data_a["token"]

    # Register User B
    res_reg_b = client.post(
        "/api/v1/auth/register",
        json={"username": "clinician_bob", "password": "BobStrongPassword456!"},
    )
    assert res_reg_b.status_code == 200
    data_b = res_reg_b.json()
    assert data_b["success"] is True
    assert "token" in data_b
    token_b = data_b["token"]

    assert token_a != token_b

    # Verify login for User A
    res_login_a = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician_alice", "password": "AliceStrongPassword123!"},
    )
    assert res_login_a.status_code == 200
    assert res_login_a.json()["username"] == "clinician_alice"


def test_independent_consultations_and_distinct_messages(client):
    """Verify User A and User B maintain completely isolated consultations and messages."""
    # Login both users
    token_a = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician_alice", "password": "AliceStrongPassword123!"},
    ).json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    token_b = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician_bob", "password": "BobStrongPassword456!"},
    ).json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a new consultation
    res_chat_a = client.post("/api/v1/new-chat", headers=headers_a)
    assert res_chat_a.status_code == 200
    sess_id_a = res_chat_a.json()["session_id"]

    # User B creates a new consultation
    res_chat_b = client.post("/api/v1/new-chat", headers=headers_b)
    assert res_chat_b.status_code == 200
    sess_id_b = res_chat_b.json()["session_id"]

    assert sess_id_a != sess_id_b

    # User A posts a medical message
    msg_a = "SYNTHETIC_PATIENT_A_CHRONIC_HYPERTENSION_STAGE_2"
    res_msg_a = client.post(
        "/api/v1/chat",
        headers={**headers_a, "X-Session-ID": sess_id_a},
        json={"message": msg_a, "session_id": sess_id_a},
    )
    assert res_msg_a.status_code == 200

    # User B posts a different medical message
    msg_b = "SYNTHETIC_PATIENT_B_MIGRAINE_WITH_VISUAL_AURA"
    res_msg_b = client.post(
        "/api/v1/chat",
        headers={**headers_b, "X-Session-ID": sess_id_b},
        json={"message": msg_b, "session_id": sess_id_b},
    )
    assert res_msg_b.status_code == 200

    # Verify User A's session history contains ONLY msg_a
    hist_a = client.get(f"/api/v1/session/{sess_id_a}", headers=headers_a)
    assert hist_a.status_code == 200
    messages_a_text = [m["content"] for m in hist_a.json().get("messages", [])]
    assert any(msg_a in m for m in messages_a_text)
    assert not any(msg_b in m for m in messages_a_text)

    # Verify User B's session history contains ONLY msg_b
    hist_b = client.get(f"/api/v1/session/{sess_id_b}", headers=headers_b)
    assert hist_b.status_code == 200
    messages_b_text = [m["content"] for m in hist_b.json().get("messages", [])]
    assert any(msg_b in m for m in messages_b_text)
    assert not any(msg_a in m for m in messages_b_text)


def test_cross_account_access_denial(client):
    """
    CRITICAL: Verify User A is strictly forbidden from accessing User B's data:
    1. Cannot view User B's session in session list
    2. Cannot read User B's history (fails with 404)
    3. Cannot inject messages into User B's session
    4. Cannot clear User B's session
    5. Cannot delete User B's session
    """
    token_a = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician_alice", "password": "AliceStrongPassword123!"},
    ).json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    token_b = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician_bob", "password": "BobStrongPassword456!"},
    ).json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B creates session
    sess_b = client.post("/api/v1/new-chat", headers=headers_b).json()["session_id"]
    client.post(
        "/api/v1/chat",
        headers={**headers_b, "X-Session-ID": sess_b},
        json={"message": "Private medical record for Bob", "session_id": sess_b},
    )

    # 1. User A lists sessions: sess_b must NOT appear
    sessions_a = client.get("/api/v1/sessions", headers=headers_a).json().get("sessions", [])
    session_ids_a = [s["session_id"] for s in sessions_a]
    assert sess_b not in session_ids_a

    # 2. User A attempts to read User B's session: must be denied with 404
    res_peek = client.get(f"/api/v1/session/{sess_b}", headers=headers_a)
    assert res_peek.status_code == 404

    # 3. User A attempts to inject message into User B's session: must not affect Bob
    res_inject = client.post(
        "/api/v1/chat",
        headers={**headers_a, "X-Session-ID": sess_b},
        json={"message": "Unauthorized intrusion attempt", "session_id": sess_b},
    )
    # Check that Bob's session did NOT receive the message
    bob_hist = client.get(f"/api/v1/session/{sess_b}", headers=headers_b).json()
    bob_contents = [m["content"] for m in bob_hist.get("messages", [])]
    assert not any("Unauthorized intrusion attempt" in c for c in bob_contents)

    # 4. User A attempts to clear User B's session: must be rejected with 404
    res_clear = client.post(
        "/api/v1/clear",
        headers={**headers_a, "X-Session-ID": sess_b},
    )
    assert res_clear.status_code == 404
    # Bob's history must remain intact
    bob_hist_after = client.get(f"/api/v1/session/{sess_b}", headers=headers_b).json()
    assert len(bob_hist_after.get("messages", [])) > 0

    # 5. User A attempts to delete User B's session: must be rejected with 404
    res_delete = client.delete(f"/api/v1/session/{sess_b}", headers=headers_a)
    assert res_delete.status_code == 404
    # Bob's session must still exist
    bob_sessions = client.get("/api/v1/sessions", headers=headers_b).json().get("sessions", [])
    assert any(s["session_id"] == sess_b for s in bob_sessions)


def test_unknown_session_fails_closed(client):
    """Verify non-existent/bogus session IDs return HTTP 404 and fail closed."""
    token_a = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician_alice", "password": "AliceStrongPassword123!"},
    ).json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    fake_session_id = f"nonexistent-session-{uuid.uuid4()}"

    # Querying history for unknown session must fail closed with 404
    res_fake_hist = client.get(f"/api/v1/session/{fake_session_id}", headers=headers_a)
    assert res_fake_hist.status_code == 404

    # Deleting unknown session must fail closed with 404
    res_fake_del = client.delete(f"/api/v1/session/{fake_session_id}", headers=headers_a)
    assert res_fake_del.status_code == 404

    # Clearing unknown session must fail closed with 404
    res_fake_clear = client.post(
        "/api/v1/clear",
        headers={**headers_a, "X-Session-ID": fake_session_id},
    )
    assert res_fake_clear.status_code == 404


def test_token_revocation_on_logout(client):
    """Verify server-side token revocation on logout immediately invalidates the token."""
    res_login = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician_alice", "password": "AliceStrongPassword123!"},
    )
    token = res_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Token works initially
    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200

    # Logout
    res_logout = client.post("/api/v1/auth/logout", headers=headers)
    assert res_logout.status_code == 200
    assert res_logout.json().get("success") is True

    # Token must now be strictly rejected with 401 Unauthorized
    res_post_logout = client.get("/api/v1/auth/me", headers=headers)
    assert res_post_logout.status_code == 401

    res_sessions_after = client.get("/api/v1/sessions", headers=headers)
    assert res_sessions_after.status_code == 401


def test_authentication_enforcement_clinical_endpoints(client):
    """Verify unauthenticated requests across all clinical routes return 401."""
    # Chat endpoints
    assert client.get("/api/v1/sessions").status_code == 401
    assert client.get("/api/v1/history").status_code == 401
    assert client.post("/api/v1/new-chat").status_code == 401
    assert client.post("/api/v1/chat", json={"message": "hello"}).status_code == 401
    assert client.post("/api/v1/clear").status_code == 401

    # Image analysis endpoint
    assert client.post("/api/v1/analyze-image").status_code == 401

    # Voice endpoints
    assert client.post("/api/v1/voice/stt").status_code == 401
    assert client.post("/api/v1/voice/tts", json={"text": "hello"}).status_code == 401

    # Bogus token
    bad_headers = {"Authorization": "Bearer invalid_bogus_token_xyz_999"}
    assert client.get("/api/v1/sessions", headers=bad_headers).status_code == 401
    assert client.post("/api/v1/chat", headers=bad_headers, json={"message": "test"}).status_code == 401


@pytest.mark.asyncio
async def test_concurrent_chat_requests_across_users(setup_phase6_env):
    """Verify concurrent requests from different users execute safely without race conditions."""
    import asyncio
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        token_a = (
            await ac.post(
                "/api/v1/auth/login",
                json={"username": "clinician_alice", "password": "AliceStrongPassword123!"},
            )
        ).json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        token_b = (
            await ac.post(
                "/api/v1/auth/login",
                json={"username": "clinician_bob", "password": "BobStrongPassword456!"},
            )
        ).json()["token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        sess_a = (await ac.post("/api/v1/new-chat", headers=headers_a)).json()["session_id"]
        sess_b = (await ac.post("/api/v1/new-chat", headers=headers_b)).json()["session_id"]

        req1 = ac.post(
            "/api/v1/chat",
            headers={**headers_a, "X-Session-ID": sess_a},
            json={"message": "Concurrent query from Alice", "session_id": sess_a},
        )
        req2 = ac.post(
            "/api/v1/chat",
            headers={**headers_b, "X-Session-ID": sess_b},
            json={"message": "Concurrent query from Bob", "session_id": sess_b},
        )
        req3 = ac.post(
            "/api/v1/chat",
            headers={**headers_a, "X-Session-ID": sess_a},
            json={"message": "Second query from Alice", "session_id": sess_a},
        )
        req4 = ac.post(
            "/api/v1/chat",
            headers={**headers_b, "X-Session-ID": sess_b},
            json={"message": "Second query from Bob", "session_id": sess_b},
        )

        res1, res2, res3, res4 = await asyncio.gather(req1, req2, req3, req4)

        for res in [res1, res2, res3, res4]:
            assert res.status_code == 200
            assert res.json().get("success") is True

        # Validate isolation after concurrency
        hist_a = (await ac.get(f"/api/v1/session/{sess_a}", headers=headers_a)).json()
        hist_b = (await ac.get(f"/api/v1/session/{sess_b}", headers=headers_b)).json()

        a_contents = [m["content"] for m in hist_a.get("messages", [])]
        b_contents = [m["content"] for m in hist_b.get("messages", [])]

        assert any("Concurrent query from Alice" in c for c in a_contents)
        assert not any("Concurrent query from Bob" in c for c in a_contents)

        assert any("Concurrent query from Bob" in c for c in b_contents)
        assert not any("Concurrent query from Alice" in c for c in b_contents)


def test_clear_conversation_lifecycle(client):
    """Verify clearing a conversation empties its message history authoritatively."""
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "clinician_alice", "password": "AliceStrongPassword123!"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create session and send messages
    sess = client.post("/api/v1/new-chat", headers=headers).json()["session_id"]
    res_msg = client.post(
        "/api/v1/chat",
        headers={**headers, "X-Session-ID": sess},
        json={"message": "Message before clearing", "session_id": sess},
    )
    assert res_msg.status_code == 200

    # Verify session has messages
    hist_before = client.get(f"/api/v1/session/{sess}", headers=headers).json()
    assert len(hist_before.get("messages", [])) > 0

    # Clear conversation with explicit X-Session-ID header
    res_clear = client.post(
        "/api/v1/clear",
        headers={**headers, "X-Session-ID": sess},
    )
    assert res_clear.status_code == 200
    assert res_clear.json().get("success") is True

    # History must now be empty
    hist_after = client.get(f"/api/v1/session/{sess}", headers=headers).json()
    assert hist_after.get("messages") == []

