"""
NewGenHealthAI — tests/test_security_ownership.py
Comprehensive regression tests for Phase 1A:
A01 (Authentication Enforcement) & A02 (Conversation Ownership and Clinical Memory Isolation).
Uses real database operations against isolated synthetic test databases.
"""

import os
import shutil
import sys
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.migrations import backup_database, restore_database, run_database_migration
from app.db.session import get_session_factory
from app.main import app
from app.models.message import Base, Conversation, Message, User, UserSession
from app.services.chat_service import clinical_engine
from app.services.database_service import DatabaseService, db_service

TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_data"))
TEST_DB_PATH = os.path.join(TEST_DIR, "security_test.db")


@pytest.fixture(scope="module")
def setup_security_env():
    """Create isolated test database and bind db_service."""
    os.makedirs(TEST_DIR, exist_ok=True)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False}
    )
    session_factory = get_session_factory(engine)

    # Rebind db_service singleton to test DB
    old_engine = db_service.engine
    old_session = db_service.SessionLocal
    db_service.engine = engine
    db_service.SessionLocal = session_factory
    db_service.init_db()

    # Mock workflow_app for clinical engine to avoid heavy ML in route tests
    mock_workflow = MagicMock()
    mock_workflow.ainvoke = AsyncMock(
        return_value={"generation": "Clinical response", "source": "Literature", "llm_success": True}
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
        except Exception:
            pass


@pytest.fixture
def client(setup_security_env):
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def users_and_tokens(setup_security_env):
    """Seed synthetic users user_a and user_b."""
    user_a = db_service.get_user_by_username("user_a")
    if not user_a:
        user_a = db_service.create_user("user_a", "password_a_123")
    token_a = db_service.create_user_session(user_a.id)

    user_b = db_service.get_user_by_username("user_b")
    if not user_b:
        user_b = db_service.create_user("user_b", "password_b_123")
    token_b = db_service.create_user_session(user_b.id)

    return {
        "user_a": user_a,
        "token_a": token_a,
        "auth_a": {"Authorization": f"Bearer {token_a}"},
        "user_b": user_b,
        "token_b": token_b,
        "auth_b": {"Authorization": f"Bearer {token_b}"},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION ENFORCEMENT TESTS (A01)
# ═══════════════════════════════════════════════════════════════════════════════

def test_missing_auth_header_fails_with_401(client):
    """Requests with no Authorization header must receive HTTP 401."""
    res_sessions = client.get("/api/v1/sessions")
    assert res_sessions.status_code == 401
    assert "detail" in res_sessions.json()

    res_history = client.get("/api/v1/history")
    assert res_history.status_code == 401

    res_new_chat = client.post("/api/v1/new-chat")
    assert res_new_chat.status_code == 401

    res_clear = client.post("/api/v1/clear")
    assert res_clear.status_code == 401

    res_chat = client.post("/api/v1/chat", json={"message": "Headache"})
    assert res_chat.status_code == 401


def test_malformed_auth_header_fails_with_401(client):
    """Malformed tokens (Basic, Bearer with no token, non-bearer) must receive HTTP 401."""
    for bad_header in ["Bearer", "Bearer    ", "Basic 12345", "Token xyz", "InvalidHeader"]:
        res = client.get("/api/v1/sessions", headers={"Authorization": bad_header})
        assert res.status_code == 401, f"Failed for header: {bad_header}"


def test_invalid_unrecognized_token_fails_with_401(client):
    """
    Unrecognized or invalid token strings fail closed with HTTP 401.
    Note: Full cryptographic token expiration enforcement is scheduled for Phase 2 (A06).
    """
    fake_token = str(uuid.uuid4())
    res = client.get("/api/v1/sessions", headers={"Authorization": f"Bearer {fake_token}"})
    assert res.status_code == 401
    assert "Invalid or expired" in res.json()["detail"]


def test_query_parameter_tokens_are_strictly_rejected(client, users_and_tokens):
    """
    Tokens passed in URL query parameters (?token=...) must NEVER be accepted.
    All endpoints strictly require standard Authorization: Bearer headers.
    """
    token_a = users_and_tokens["token_a"]
    for path, method in [
        (f"/api/v1/sessions?token={token_a}", "get"),
        (f"/api/v1/history?token={token_a}", "get"),
        (f"/api/v1/voice/tts?token={token_a}", "post"),
        (f"/api/v1/voice/stt?token={token_a}", "post"),
    ]:
        fn = getattr(client, method)
        if method == "post":
            res = fn(path, json={"text": "Test speech synthesis"})
        else:
            res = fn(path)
        assert res.status_code == 401, f"Endpoint {path} accepted query token"



def test_logout_revokes_token_immediately(client, users_and_tokens):
    """Logging out invalidates the token so subsequent use returns HTTP 401."""
    user = db_service.create_user(f"logout_user_{uuid.uuid4().hex[:6]}", "password123")
    token = db_service.create_user_session(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Before logout: valid
    res_before = client.get("/api/v1/sessions", headers=headers)
    assert res_before.status_code == 200

    # Logout
    res_logout = client.post("/api/v1/auth/logout", headers=headers)
    assert res_logout.status_code == 200

    # After logout: token must be rejected with 401
    res_after = client.get("/api/v1/sessions", headers=headers)
    assert res_after.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CONVERSATION OWNERSHIP & CLINICAL MEMORY ISOLATION TESTS (A01, A02)
# ═══════════════════════════════════════════════════════════════════════════════

def test_user_can_create_and_retrieve_own_conversation(client, users_and_tokens):
    """User A creates a conversation, sends a message, and retrieves it."""
    auth_a = users_and_tokens["auth_a"]

    # Create new conversation via server
    res_new = client.post("/api/v1/new-chat", headers=auth_a)
    assert res_new.status_code == 200
    session_id = res_new.json()["session_id"]
    assert session_id

    # Send message in that session
    res_chat = client.post(
        "/api/v1/chat",
        headers={**auth_a, "X-Session-ID": session_id},
        json={"message": "Chest pain for 2 days"},
    )
    assert res_chat.status_code == 200
    assert res_chat.json()["success"] is True

    # User A retrieves history
    res_hist = client.get(
        "/api/v1/history", headers={**auth_a, "X-Session-ID": session_id}
    )
    assert res_hist.status_code == 200
    msgs = res_hist.json()["messages"]
    assert len(msgs) >= 2
    assert msgs[0]["content"] == "Chest pain for 2 days"


def test_user_b_cannot_retrieve_user_a_conversation(client, users_and_tokens):
    """User B cannot view User A's consultation history (fails with 404, no data leaked)."""
    auth_a = users_and_tokens["auth_a"]
    auth_b = users_and_tokens["auth_b"]

    # User A creates a consultation
    res_new = client.post("/api/v1/new-chat", headers=auth_a)
    session_a = res_new.json()["session_id"]

    client.post(
        "/api/v1/chat",
        headers={**auth_a, "X-Session-ID": session_a},
        json={"message": "Confidential patient diagnosis: Flu"},
    )

    # User B attempts to access User A's session via /history
    res_b_hist = client.get(
        "/api/v1/history", headers={**auth_b, "X-Session-ID": session_a}
    )
    assert res_b_hist.status_code == 404
    assert "messages" not in res_b_hist.json()

    # User B attempts to load User A's session via /session/{id}
    res_b_load = client.get(f"/api/v1/session/{session_a}", headers=auth_b)
    assert res_b_load.status_code == 404


def test_user_b_cannot_list_user_a_conversation(client, users_and_tokens):
    """User B's session list must never contain User A's consultations."""
    auth_a = users_and_tokens["auth_a"]
    auth_b = users_and_tokens["auth_b"]

    # User A creates a consultation
    res_new = client.post("/api/v1/new-chat", headers=auth_a)
    session_a = res_new.json()["session_id"]
    client.post(
        "/api/v1/chat",
        headers={**auth_a, "X-Session-ID": session_a},
        json={"message": "User A secret symptoms"},
    )

    # User B lists sessions
    res_b_sessions = client.get("/api/v1/sessions", headers=auth_b)
    assert res_b_sessions.status_code == 200
    b_session_ids = [s["session_id"] for s in res_b_sessions.json()["sessions"]]
    assert session_a not in b_session_ids


def test_user_b_cannot_append_message_to_user_a_conversation(client, users_and_tokens):
    """User B providing User A's session ID to /chat must fail with 404."""
    auth_a = users_and_tokens["auth_a"]
    auth_b = users_and_tokens["auth_b"]

    res_new = client.post("/api/v1/new-chat", headers=auth_a)
    session_a = res_new.json()["session_id"]

    # User B attempts to inject a message into User A's consultation
    res_b_post = client.post(
        "/api/v1/chat",
        headers={**auth_b, "X-Session-ID": session_a},
        json={"message": "Injected malicious message"},
    )
    assert res_b_post.status_code == 404


def test_user_b_cannot_delete_user_a_conversation(client, users_and_tokens):
    """User B cannot delete User A's consultation."""
    auth_a = users_and_tokens["auth_a"]
    auth_b = users_and_tokens["auth_b"]

    res_new = client.post("/api/v1/new-chat", headers=auth_a)
    session_a = res_new.json()["session_id"]

    # User B attempts delete
    res_del = client.delete(f"/api/v1/session/{session_a}", headers=auth_b)
    assert res_del.status_code == 404

    # User A's session must still be intact
    res_hist = client.get(f"/api/v1/session/{session_a}", headers=auth_a)
    assert res_hist.status_code == 200


def test_user_b_cannot_clear_user_a_clinical_memory(client, users_and_tokens):
    """User B calling /clear with User A's X-Session-ID must fail with 404."""
    auth_a = users_and_tokens["auth_a"]
    auth_b = users_and_tokens["auth_b"]

    res_new = client.post("/api/v1/new-chat", headers=auth_a)
    session_a = res_new.json()["session_id"]

    # User B attempts clear
    res_clear = client.post(
        "/api/v1/clear", headers={**auth_b, "X-Session-ID": session_a}
    )
    assert res_clear.status_code == 404


def test_clinical_memory_multi_user_isolation(users_and_tokens):
    """Direct ClinicalEngine memory test: User A and User B maintain separate memory states."""
    user_a_id = users_and_tokens["user_a"].id
    user_b_id = users_and_tokens["user_b"].id
    session_id = str(uuid.uuid4())

    # User A owns conversation
    db_service.create_conversation(user_id=user_a_id, session_id=session_id)

    # In-memory states must be isolated by user_id
    key_a = clinical_engine._get_memory_key(user_a_id, session_id)
    key_b = clinical_engine._get_memory_key(user_b_id, session_id)
    assert key_a != key_b

    clinical_engine.conversation_states[key_a] = {"patient_note": "User A Medical Note"}
    clinical_engine.conversation_states[key_b] = {"patient_note": "User B Medical Note"}

    assert clinical_engine.conversation_states[key_a]["patient_note"] == "User A Medical Note"
    assert clinical_engine.conversation_states[key_b]["patient_note"] == "User B Medical Note"

    # User B cannot clear User A's state
    assert clinical_engine.clear_conversation(session_id, user_id=user_b_id) is False
    assert key_a in clinical_engine.conversation_states
    assert clinical_engine.conversation_states[key_a]["patient_note"] == "User A Medical Note"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. RESOURCE ENDPOINT AUTHENTICATION TESTS (Images & Voice)
# ═══════════════════════════════════════════════════════════════════════════════

def test_image_and_voice_require_authentication(client):
    """Voice STT, Voice TTS, and Image analysis must return 401 when unauthenticated."""
    res_tts = client.post("/api/v1/voice/tts", json={"text": "Hello clinical consultation"})
    assert res_tts.status_code == 401

    res_stt = client.post(
        "/api/v1/voice/stt",
        files={"file": ("test.wav", b"fake audio content", "audio/wav")},
    )
    assert res_stt.status_code == 401

    res_img = client.post(
        "/api/v1/analyze-image",
        files={"file": ("test.png", b"fake image content", "image/png")},
    )
    assert res_img.status_code == 401


def test_voice_tts_post_contract_and_audio_streaming(client, users_and_tokens):
    """
    POST /voice/tts accepts JSON body { text: ... } with Bearer token.
    Rejects GET requests, query parameters for text, and streams audio.
    """
    from unittest.mock import patch
    auth_a = users_and_tokens["auth_a"]

    # GET is rejected (404/405)
    res_get = client.get("/api/v1/voice/tts", headers=auth_a)
    assert res_get.status_code in [404, 405]

    # Text in query param without JSON body is rejected (422)
    res_query = client.post("/api/v1/voice/tts?text=Hello", headers=auth_a)
    assert res_query.status_code == 422

    # Text too short (< 2 chars) fails schema validation (422)
    res_short = client.post("/api/v1/voice/tts", json={"text": "a"}, headers=auth_a)
    assert res_short.status_code == 422


    # Valid POST with mock edge_tts succeeds and streams audio
    with patch("edge_tts.Communicate") as mock_comm:
        mock_instance = MagicMock()
        async def fake_stream():
            yield {"type": "audio", "data": b"\xff\xfb\x90\x44" + b"\x00" * 100}
        mock_instance.stream = fake_stream
        mock_comm.return_value = mock_instance

        res_ok = client.post(
            "/api/v1/voice/tts",
            json={"text": "Patient reports mild seasonal allergy symptoms."},
            headers=auth_a,
        )
        assert res_ok.status_code == 200
        assert res_ok.headers["content-type"] == "audio/mpeg"
        assert len(res_ok.content) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ARBITRARY CLIENT-SUPPLIED CONVERSATION ID PROTECTION
# ═══════════════════════════════════════════════════════════════════════════════

def test_arbitrary_client_supplied_session_id_fails_closed(client, users_and_tokens):
    """
    Supplying an arbitrary uncreated UUID in X-Session-ID fails closed with 404.
    Does NOT auto-create a conversation for that ID.
    """
    auth_a = users_and_tokens["auth_a"]
    user_a = users_and_tokens["user_a"]
    arbitrary_id = str(uuid.uuid4())

    # Chat endpoint rejects unknown session ID with 404
    res_chat = client.post(
        "/api/v1/chat",
        headers={**auth_a, "X-Session-ID": arbitrary_id},
        json={"message": "Injecting arbitrary session"},
    )
    assert res_chat.status_code == 404
    assert res_chat.json()["detail"] == "Conversation not found"

    # History endpoint rejects unknown session ID with 404
    res_hist = client.get(
        "/api/v1/history",
        headers={**auth_a, "X-Session-ID": arbitrary_id},
    )
    assert res_hist.status_code == 404

    # Verify conversation was not created in database
    assert db_service.get_conversation(arbitrary_id, user_a.id) is None

    # Verify get_or_create_conversation does NOT auto-create arbitrary IDs
    assert db_service.get_or_create_conversation(arbitrary_id, user_a.id) is None

    # Direct save_message raises PermissionError
    with pytest.raises(PermissionError):
        db_service.save_message(arbitrary_id, "user", "Direct save attempt", user_id=user_a.id)


def test_deleted_session_id_cannot_be_reused(client, users_and_tokens):
    """
    Once a conversation is deleted, passing its ID in X-Session-ID returns 404
    and cannot resurrect or append to the conversation.
    """
    auth_a = users_and_tokens["auth_a"]
    user_a = users_and_tokens["user_a"]

    # Create new session via authorized server endpoint
    res_new = client.post("/api/v1/new-chat", headers=auth_a)
    assert res_new.status_code == 200
    session_id = res_new.json()["session_id"]

    # Delete session
    res_del = client.delete(f"/api/v1/session/{session_id}", headers=auth_a)
    assert res_del.status_code == 200

    # Attempt to chat in deleted session returns 404
    res_chat = client.post(
        "/api/v1/chat",
        headers={**auth_a, "X-Session-ID": session_id},
        json={"message": "Resurrect attempt"},
    )
    assert res_chat.status_code == 404

    # Direct save_message raises PermissionError
    with pytest.raises(PermissionError):
        db_service.save_message(session_id, "user", "Resurrect direct", user_id=user_a.id)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DATABASE MIGRATION, WAL BACKUP & RECOVERY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_database_migration_unambiguous_and_quarantine(tmp_path):
    """
    Test safe migration on a synthetic legacy SQLite database:
    - Legacy session with pure single owner is migrated.
    - Legacy session with conflicting owners is quarantined.
    - Legacy session with completely null owners is quarantined.
    - Legacy session with mixed NULL + identified user is quarantined (NEVER backfilled).
    - Legacy session with unknown user (not in users table) is quarantined.
    - Original message records are preserved unmodified.
    - Schema version tracking is verified.
    """
    db_file = str(tmp_path / "legacy.db")
    engine = create_engine(f"sqlite:///{db_file}")

    # Build legacy schema: users and messages only (no conversations table)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id VARCHAR(255) NOT NULL,
                user_id INTEGER,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                source VARCHAR(255),
                timestamp DATETIME NOT NULL
            )
        """))
        # Insert user 10
        conn.execute(text("""
            INSERT INTO users (id, username, hashed_password, created_at)
            VALUES (10, 'legacy_user', 'hash', '2026-01-01 00:00:00')
        """))
        # Session A: Unambiguous pure single owner (all user_id=10, no nulls)
        conn.execute(text("""
            INSERT INTO messages (session_id, user_id, role, content, timestamp)
            VALUES ('sess_clean', 10, 'user', 'My flu symptom', '2026-01-01 10:00:00'),
                   ('sess_clean', 10, 'assistant', 'Take rest', '2026-01-01 10:01:00')
        """))
        # Session B: Conflicting ownership (user_id=10 and user_id=20)
        conn.execute(text("""
            INSERT INTO messages (session_id, user_id, role, content, timestamp)
            VALUES ('sess_conflict', 10, 'user', 'User 10 msg', '2026-01-01 10:00:00'),
                   ('sess_conflict', 20, 'user', 'User 20 msg', '2026-01-01 10:01:00')
        """))
        # Session C: Completely anonymous (user_id is NULL)
        conn.execute(text("""
            INSERT INTO messages (session_id, user_id, role, content, timestamp)
            VALUES ('sess_anon', NULL, 'user', 'Anon msg', '2026-01-01 10:00:00')
        """))
        # Session D: Mixed NULL + identified user (must QUARANTINE, never backfill)
        conn.execute(text("""
            INSERT INTO messages (session_id, user_id, role, content, timestamp)
            VALUES ('sess_mixed', 10, 'user', 'Identified user msg', '2026-01-01 10:00:00'),
                   ('sess_mixed', NULL, 'user', 'Anonymous msg in same session', '2026-01-01 10:01:00')
        """))
        # Session E: Unknown user ID not in users table
        conn.execute(text("""
            INSERT INTO messages (session_id, user_id, role, content, timestamp)
            VALUES ('sess_unknown', 999, 'user', 'Unknown user msg', '2026-01-01 10:00:00')
        """))
        conn.commit()

    # Run migration
    stats = run_database_migration(engine, db_path=db_file)
    assert stats["conversations_table_created"] is True
    assert stats["migrated_conversations"] == 1
    assert stats["quarantined_conversations"] == 4
    assert stats["schema_version"] == 2

    with engine.connect() as conn:
        # Verify sess_clean is owned by user 10 and not quarantined
        clean_row = conn.execute(
            text("SELECT user_id, is_quarantined FROM conversations WHERE id = 'sess_clean'")
        ).fetchone()
        assert clean_row is not None
        assert clean_row[0] == 10
        assert clean_row[1] == 0

        # Verify sess_conflict is quarantined
        conflict_row = conn.execute(
            text("SELECT user_id, is_quarantined FROM conversations WHERE id = 'sess_conflict'")
        ).fetchone()
        assert conflict_row is not None
        assert conflict_row[1] == 1

        # Verify sess_anon is quarantined
        anon_row = conn.execute(
            text("SELECT is_quarantined FROM conversations WHERE id = 'sess_anon'")
        ).fetchone()
        assert anon_row is not None
        assert anon_row[0] == 1

        # Verify sess_mixed is quarantined
        mixed_row = conn.execute(
            text("SELECT user_id, is_quarantined FROM conversations WHERE id = 'sess_mixed'")
        ).fetchone()
        assert mixed_row is not None
        assert mixed_row[1] == 1

        # CRITICAL: Verify original messages in sess_mixed were NOT modified (NULL row is still NULL)
        mixed_null_msg = conn.execute(
            text("SELECT user_id FROM messages WHERE session_id = 'sess_mixed' AND content = 'Anonymous msg in same session'")
        ).fetchone()
        assert mixed_null_msg is not None
        assert mixed_null_msg[0] is None, "Migration must NOT backfill NULL message user_id!"

        # Verify sess_unknown is quarantined
        unknown_row = conn.execute(
            text("SELECT is_quarantined FROM conversations WHERE id = 'sess_unknown'")
        ).fetchone()
        assert unknown_row is not None
        assert unknown_row[0] == 1

        # Verify schema_versions table exists and records version 2
        ver = conn.execute(text("SELECT MAX(version) FROM schema_versions")).scalar()
        assert ver == 2

    # Idempotency test: running migration again does nothing
    stats_repeat = run_database_migration(engine, db_path=db_file)
    assert stats_repeat["migrated_conversations"] == 0
    assert stats_repeat["quarantined_conversations"] == 0
    assert stats_repeat["already_migrated"] == 5
    assert stats_repeat["schema_version"] == 2

    # Online Backup & Rollback test
    backup_file = backup_database(db_file)
    assert backup_file is not None
    assert os.path.exists(backup_file)

    # Corrupt or alter target
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM messages"))
        conn.commit()

    # Restore from online backup
    engine.dispose()
    assert restore_database(backup_file, db_file) is True

    # Check restored state
    engine_restored = create_engine(f"sqlite:///{db_file}")
    with engine_restored.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM messages")).scalar()
        assert count > 0
    engine_restored.dispose()


def test_sqlite_wal_mode_online_backup_and_integrity(tmp_path):
    """
    Test SQLite Online Backup API on a live database with WAL mode enabled.
    Verifies that uncheckpointed WAL frames are captured and integrity passes.
    """
    import sqlite3
    db_file = str(tmp_path / "wal_test.db")

    # Initialize WAL mode database
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT)")
    conn.execute("INSERT INTO notes (text) VALUES ('Uncheckpointed WAL note')")
    conn.commit()
    conn.close()

    # Perform online backup
    backup_file = backup_database(db_file)
    assert backup_file is not None
    assert os.path.exists(backup_file)

    # Verify backup integrity
    verify_conn = sqlite3.connect(backup_file)
    res = verify_conn.execute("PRAGMA integrity_check").fetchone()
    assert res[0] == "ok"

    # Verify uncheckpointed data was captured in backup
    note_row = verify_conn.execute("SELECT text FROM notes").fetchone()
    assert note_row is not None
    assert note_row[0] == "Uncheckpointed WAL note"
    verify_conn.close()

    # Test restore into a fresh location
    restored_db = str(tmp_path / "restored.db")
    assert restore_database(backup_file, restored_db) is True
    restored_conn = sqlite3.connect(restored_db)
    count = restored_conn.execute("SELECT count(*) FROM notes").fetchone()[0]
    assert count == 1
    restored_conn.close()

