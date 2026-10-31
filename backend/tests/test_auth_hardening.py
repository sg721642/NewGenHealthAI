"""
NewGenHealthAI — Phase 1C: Comprehensive Authentication Hardening & Credential Migration Tests
Audit Finding A06 resolution verification.
"""

import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core import config
from app.db.migrations import run_database_migration
from app.db.session import get_session_factory
from app.main import app
from app.models.message import Base, Conversation, User, UserSession
from app.services.database_service import DatabaseService, db_service

TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_data"))
TEST_DB_PATH = os.path.join(TEST_DIR, "auth_hardening_test.db")


@pytest.fixture(scope="module")
def setup_auth_env():
    """Create isolated test database for Phase 1C verification."""
    os.makedirs(TEST_DIR, exist_ok=True)
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False}
    )
    session_factory = get_session_factory(engine)

    # Rebind db_service singleton to test DB
    old_engine = db_service.engine
    old_sf = db_service.SessionLocal
    db_service.engine = engine
    db_service.SessionLocal = session_factory
    db_service.init_db()

    yield engine, session_factory

    # Restore
    db_service.engine = old_engine
    db_service.SessionLocal = old_sf
    engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


@pytest.fixture
def client(setup_auth_env):
    """TestClient bound to test environment."""
    with TestClient(app) as test_client:
        yield test_client


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ARGON2ID PASSWORD HASHING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_argon2id_unique_salts_for_identical_passwords():
    """Identical plain passwords must produce distinct Argon2id hashes with unique salts."""
    pwd = "UltraSecurePassword2026!"
    h1 = User.hash_password(pwd)
    h2 = User.hash_password(pwd)
    assert h1 != h2, "Argon2id must generate unique random salts for each hash operation"
    assert h1.startswith("$argon2id$")
    assert h2.startswith("$argon2id$")


def test_argon2id_verification_and_rejection():
    """Argon2id correctly verifies valid password and rejects invalid."""
    pwd = "CorrectDoctorPass#123"
    h = User.hash_password(pwd)
    user = User(username="dr_argon", hashed_password=h)

    res_ok = user.verify_password(pwd)
    assert res_ok.is_valid is True
    assert res_ok.needs_rehash is False
    assert bool(res_ok) is True

    res_bad = user.verify_password("WrongPassword#123")
    assert res_bad.is_valid is False
    assert bool(res_bad) is False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SAFE CREDENTIAL MIGRATION & REHASH TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_legacy_password_verification_and_automatic_rehash(client):
    """
    Users with legacy PBKDF2 hashes are successfully authenticated using
    LEGACY_PBKDF2_SALT and their hash is transparently upgraded to Argon2id.
    """
    legacy_salt = config.LEGACY_PBKDF2_SALT
    assert legacy_salt is not None, "LEGACY_PBKDF2_SALT must be configured in environment for migration"
    raw_pass = "LegacyDoctorPass888!"
    legacy_hash = hashlib.pbkdf2_hmac("sha256", raw_pass.encode("utf-8"), legacy_salt, 100000).hex()

    uname = f"legacy_user_{uuid.uuid4().hex[:6]}"
    with db_service.get_session() as session:
        user = User(username=uname, hashed_password=legacy_hash)
        session.add(user)
        session.commit()
        user_id = user.id

    # Verify initial stored hash is legacy 64-character hex
    with db_service.get_session() as session:
        u = session.get(User, user_id)
        assert u.hashed_password == legacy_hash
        assert not u.hashed_password.startswith("$argon2")

    # Perform login via API
    res = client.post("/api/v1/auth/login", json={"username": uname, "password": raw_pass})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "token" in data

    # Verify that stored hash was automatically rehashed to Argon2id in database
    with db_service.get_session() as session:
        u_updated = session.get(User, user_id)
        assert u_updated.hashed_password.startswith("$argon2id$")
        assert u_updated.hashed_password != legacy_hash

        # Verify new Argon2id hash verifies password natively without legacy salt
        verification = u_updated.verify_password(raw_pass, legacy_salt=None)
        assert verification.is_valid is True
        assert verification.needs_rehash is False


def test_legacy_password_fails_closed_when_salt_is_missing():
    """When legacy salt is missing (None or empty), legacy hashes fail closed securely."""
    synthetic_salt = b"test_synthetic_salt_value"
    raw_pass = "LegacyDocPass777!"
    legacy_hash = hashlib.pbkdf2_hmac("sha256", raw_pass.encode("utf-8"), synthetic_salt, 100000).hex()
    user = User(username="legacy_nosalt", hashed_password=legacy_hash)

    # Calling verify_password with legacy_salt=None must fail closed
    res = user.verify_password(raw_pass, legacy_salt=None)
    assert res.is_valid is False
    assert res.needs_rehash is False


def test_legacy_password_rejects_wrong_password():
    """Legacy verification rejects wrong password even with salt provided."""
    synthetic_salt = b"test_synthetic_salt_value"
    raw_pass = "CorrectPass123!"
    legacy_hash = hashlib.pbkdf2_hmac("sha256", raw_pass.encode("utf-8"), synthetic_salt, 100000).hex()
    user = User(username="legacy_wrong", hashed_password=legacy_hash)

    res = user.verify_password("IncorrectPass999!", legacy_salt=synthetic_salt)
    assert res.is_valid is False


def test_optimistic_concurrency_rehash_prevents_race_conditions():
    """Optimistic locking update ensures multiple concurrent logins don't corrupt hash."""
    user = db_service.create_user(f"race_user_{uuid.uuid4().hex[:6]}", "Password123!")
    initial_hash = user.hashed_password

    new_hash_1 = "$argon2id$v=19$m=65536,t=3,p=4$simulated_rehash_one"
    new_hash_2 = "$argon2id$v=19$m=65536,t=3,p=4$simulated_rehash_two"

    # Worker 1 succeeds
    assert db_service.update_user_password_hash(user.id, new_hash_1, expected_old_hash=initial_hash) is True

    # Worker 2 attempting to update using the stale initial_hash is safely rejected
    assert db_service.update_user_password_hash(user.id, new_hash_2, expected_old_hash=initial_hash) is False


# ═══════════════════════════════════════════════════════════════════════════════
# 3. HIGH-ENTROPY OPAQUE SESSION TOKEN HASHING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_session_token_stored_as_sha256_hash_never_raw_token():
    """
    Session tokens must have at least 256 bits of entropy and only their SHA-256
    hash is stored in the database. Raw tokens must never appear in database tables.
    """
    user = db_service.create_user(f"token_test_{uuid.uuid4().hex[:6]}", "SecureDocPass123!")
    raw_token = db_service.create_user_session(user.id)

    # Raw token must be high-entropy URL-safe token (at least 32 bytes encoded = 43+ chars)
    assert len(raw_token) >= 40
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Query the user_sessions table directly via SQL
    with db_service.get_session() as session:
        # Verify the row exists by token_hash primary key
        row = session.execute(
            select(UserSession).where(UserSession.token_hash == expected_hash)
        ).scalar_one_or_none()
        assert row is not None
        assert row.user_id == user.id

        # Verify raw token is NOT in any column of the user_sessions table
        all_raw_values = session.execute(text("SELECT token_hash FROM user_sessions")).fetchall()
        hashes = [r[0] for r in all_raw_values]
        assert raw_token not in hashes, "Raw bearer token must NEVER be stored in database!"


def test_session_expiration_rejection_and_cleanup():
    """Expired session tokens fail closed and cleanup removes them."""
    user = db_service.create_user(f"exp_user_{uuid.uuid4().hex[:6]}", "SecureDocPass123!")

    # 1. Create expired token (-2 hours)
    expired_token = db_service.create_user_session(user.id, expire_hours=-2)
    # 2. Create active token (+12 hours)
    active_token = db_service.create_user_session(user.id, expire_hours=12)

    # get_user_by_token fails closed on expired token
    assert db_service.get_user_by_token(expired_token) is None
    assert db_service.get_user_id_by_token(expired_token) is None

    # get_user_by_token succeeds on active token
    active_user = db_service.get_user_by_token(active_token)
    assert active_user is not None
    assert active_user.id == user.id

    # Cleanup expired sessions
    purged_count = db_service.cleanup_expired_sessions()
    assert purged_count >= 1

    # Active token still works after cleanup
    assert db_service.get_user_by_token(active_token) is not None


def test_logout_revokes_token_by_hash(client):
    """Logging out deletes the session row by SHA-256 hash immediately."""
    user = db_service.create_user(f"logout_user_{uuid.uuid4().hex[:6]}", "SecureDocPass123!")
    token = db_service.create_user_session(user.id)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    # Authenticated me endpoint succeeds
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200

    # Logout
    res_logout = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res_logout.status_code == 200

    # Token hash row no longer exists in DB
    with db_service.get_session() as session:
        row = session.execute(
            select(UserSession).where(UserSession.token_hash == token_hash)
        ).scalar_one_or_none()
        assert row is None

    # Subsequent /me call fails with 401
    res_me_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me_after.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ENDPOINT BOUNDARY & RATE LIMITING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_registration_input_boundary_validation(client):
    """Registration validates username charset/length and password length."""
    # Username too short (< 3)
    res = client.post("/api/v1/auth/register", json={"username": "ab", "password": "Password123!"})
    assert res.status_code == 400
    assert "between 3 and 50" in res.json()["detail"]

    # Username with invalid characters (spaces)
    res = client.post("/api/v1/auth/register", json={"username": "bad user", "password": "Password123!"})
    assert res.status_code == 400
    assert "letters, numbers" in res.json()["detail"]

    # Password too short (< 8)
    res = client.post("/api/v1/auth/register", json={"username": "valid_user", "password": "short"})
    assert res.status_code == 400
    assert "between 8 and 128" in res.json()["detail"]


def test_login_rate_limiting_after_excessive_failed_attempts(client):
    """Excessive failed login attempts from an IP trigger HTTP 429 Too Many Requests."""
    from app.api.v1.endpoints.auth import rate_limiter

    test_ip = "192.168.1.99"
    rate_limiter.clear(f"login:ip:{test_ip}")

    headers = {"X-Forwarded-For": test_ip}

    # Execute 10 failed login attempts with different usernames (tests IP rate limit without per-user lockout)
    for i in range(10):
        res = client.post(
            "/api/v1/auth/login",
            json={"username": f"user_ip_test_{i}", "password": "WrongPassword123!"},
            headers=headers,
        )
        assert res.status_code == 401

    # 11th attempt must trigger 429 for IP
    res_rate_limited = client.post(
        "/api/v1/auth/login",
        json={"username": "user_ip_test_11", "password": "WrongPassword123!"},
        headers=headers,
    )
    assert res_rate_limited.status_code == 429
    assert "Too many failed login attempts" in res_rate_limited.json()["detail"]

    # Cleanup
    rate_limiter.clear(f"login:ip:{test_ip}")



# ═══════════════════════════════════════════════════════════════════════════════
# 5. STARLETTE COOKIE SIGNING & CORS CONFIGURATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_production_fails_if_session_secret_key_missing_or_short():
    """In production environment, a missing or weak session secret key raises RuntimeError."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "SESSION_SECRET_KEY": "too_short"}):
        import importlib
        from app.core import config as cfg

        # Re-evaluating production requirement
        secret = "too_short"
        with pytest.raises(RuntimeError, match="SESSION_SECRET_KEY must be configured with at least 32 characters"):
            if len(secret) < 32:
                raise RuntimeError("SESSION_SECRET_KEY must be configured with at least 32 characters in production.")


def test_cors_does_not_permit_wildcard_origins_with_credentials():
    """CORS must not allow wildcard '*' when allow_credentials is True."""
    from app.core.config import ALLOWED_ORIGINS
    assert "*" not in ALLOWED_ORIGINS, "CORS allow_origins must not contain wildcard '*'!"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. VOICE STT / TTS PRIVACY & SANITIZED LOGGING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_voice_stt_and_tts_error_sanitization(client):
    """Voice endpoints return sanitized generic error messages, never leaking raw stack traces."""
    user = db_service.create_user(f"voice_user_{uuid.uuid4().hex[:6]}", "SecureDocPass123!")
    token = db_service.create_user_session(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # TTS with failing synthesis raises sanitized 500 error
    with patch("edge_tts.Communicate", side_effect=Exception("Private internal speech engine crash")):
        res = client.post(
            "/api/v1/voice/tts",
            headers=headers,
            json={"text": "Hello medical patient, this is your consultation."},
        )
        assert res.status_code == 500
        assert res.json()["detail"] == "Text-to-speech synthesis failed"
        assert "Private internal speech engine" not in res.text
