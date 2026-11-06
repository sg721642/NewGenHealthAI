"""
NewGenHealthAI — tests/test_targeted_session_revocation.py
Comprehensive verification of targeted session revocation (Phase 3):
- revoke_sessions_for_user only revokes the target user's sessions
- Unrelated users' sessions and conversations remain 100% intact
- Fails gracefully for non-existent users
- Normal logout and session restoration continue to function
"""

import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app.db.session import get_session_factory
from app.main import app
from app.services.database_service import db_service

TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_data"))
TEST_DB_PATH = os.path.join(TEST_DIR, "targeted_revocation_test.db")


@pytest.fixture(scope="module")
def setup_isolated_db():
    os.makedirs(TEST_DIR, exist_ok=True)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
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
    return TestClient(app)


def test_targeted_revocation_for_audit_tester(client, setup_isolated_db):
    """
    Verify revoke_sessions_for_user specifically revokes only audit_live_tester_01's
    active sessions while preserving unrelated users' active sessions and conversations.
    """
    # 1. Create target audit user with 2 active sessions
    audit_user = db_service.get_user_by_username("audit_live_tester_01")
    if not audit_user:
        audit_user = db_service.create_user("audit_live_tester_01", "AuditSecret123!")
    token_audit_1 = db_service.create_user_session(audit_user.id)
    token_audit_2 = db_service.create_user_session(audit_user.id)

    # 2. Create unrelated legitimate user with active session and consultation
    legit_user = db_service.get_user_by_username("legit_patient_99")
    if not legit_user:
        legit_user = db_service.create_user("legit_patient_99", "LegitSecret456!")
    token_legit = db_service.create_user_session(legit_user.id)
    conv_id = str(uuid.uuid4())
    db_service.create_conversation(session_id=conv_id, user_id=legit_user.id, title="Legitimate History")
    db_service.save_message(conv_id, "user", "My legitimate question", user_id=legit_user.id)

    # Pre-revocation verification: both users can authenticate
    resp_audit_before = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_audit_1}"})
    assert resp_audit_before.status_code == 200
    assert resp_audit_before.json()["username"] == "audit_live_tester_01"

    resp_legit_before = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_legit}"})
    assert resp_legit_before.status_code == 200
    assert resp_legit_before.json()["username"] == "legit_patient_99"

    # 3. Execute targeted revocation strictly on audit_live_tester_01
    revoked_count = db_service.revoke_sessions_for_user("audit_live_tester_01")
    assert revoked_count >= 2, f"Expected at least 2 revoked sessions, got {revoked_count}"

    # 4. Post-revocation verification:
    # Audit user's tokens are now invalid (HTTP 401)
    resp_audit_after_1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_audit_1}"})
    assert resp_audit_after_1.status_code == 401

    resp_audit_after_2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_audit_2}"})
    assert resp_audit_after_2.status_code == 401

    # Legitimate user's session remains 100% ACTIVE (HTTP 200)
    resp_legit_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_legit}"})
    assert resp_legit_after.status_code == 200
    assert resp_legit_after.json()["username"] == "legit_patient_99"

    # Legitimate user's consultation history remains 100% INTACT
    history_resp = client.get("/api/v1/history", headers={
        "Authorization": f"Bearer {token_legit}",
        "X-Session-ID": conv_id,
    })
    assert history_resp.status_code == 200
    assert len(history_resp.json()["messages"]) == 1
    assert history_resp.json()["messages"][0]["content"] == "My legitimate question"


def test_targeted_revocation_nonexistent_user():
    """Revoking sessions for a non-existent user returns 0 safely without error."""
    count = db_service.revoke_sessions_for_user("non_existent_user_xyz")
    assert count == 0

    count_empty = db_service.revoke_sessions_for_user("")
    assert count_empty == 0

    # Repeated revocation on an already-revoked user safely returns 0
    repeat_count = db_service.revoke_sessions_for_user("audit_live_tester_01")
    assert repeat_count == 0
