"""Tests for Phase 1C.1 Hardening: Proxy Verification, Bounded Rate Limiting, Atomic Migrations, and Fail-Closed Quarantine."""
import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.api.v1.endpoints.auth import (
    BoundedRateLimiter,
    get_client_ip,
    is_ip_in_trusted_proxies,
    rate_limiter,
)
from app.db.migrations import CURRENT_SCHEMA_VERSION, run_database_migration
from app.main import app
from starlette.testclient import TestClient


# ===============================================================================
# 1. SEC-01: UNTRUSTED PROXY HEADERS & TRUSTED REVERSE PROXY VALIDATION
# ===============================================================================

def test_proxy_untrusted_peer_ignores_xff():
    """When connecting peer is NOT in TRUSTED_PROXIES, X-Forwarded-For is completely ignored."""
    mock_req = MagicMock()
    mock_req.client.host = "198.51.100.25"  # Public untrusted IP
    mock_req.headers = {"X-Forwarded-For": "127.0.0.1, 10.0.0.1"}

    # Using default trusted proxies ['127.0.0.1', '::1']
    client_ip = get_client_ip(mock_req, trusted_proxies=["127.0.0.1", "::1"])
    assert client_ip == "198.51.100.25"  # Spoofed XFF ignored!


def test_proxy_trusted_peer_extracts_client_ip():
    """When connecting peer IS a trusted proxy, real client IP from X-Forwarded-For is extracted."""
    mock_req = MagicMock()
    mock_req.client.host = "127.0.0.1"  # Trusted reverse proxy
    mock_req.headers = {"X-Forwarded-For": "203.0.113.195"}

    client_ip = get_client_ip(mock_req, trusted_proxies=["127.0.0.1", "::1"])
    assert client_ip == "203.0.113.195"


def test_proxy_cidr_network_matching():
    """Trusted proxies specified as CIDRs are matched correctly and traversal skips proxy hops."""
    mock_req = MagicMock()
    mock_req.client.host = "10.254.1.5"  # Inside 10.0.0.0/8
    mock_req.headers = {"X-Forwarded-For": "203.0.113.50, 10.1.1.1"}

    trusted = ["127.0.0.1", "10.0.0.0/8", "172.16.0.0/12"]
    client_ip = get_client_ip(mock_req, trusted_proxies=trusted)
    assert client_ip == "203.0.113.50"


def test_proxy_spoofed_chain_via_trusted_proxy():
    """If an attacker connects to trusted proxy with spoofed XFF, reverse traversal finds authentic client."""
    mock_req = MagicMock()
    mock_req.client.host = "127.0.0.1"  # Local trusted proxy
    # Attacker 198.51.100.2 injected 1.1.1.1, proxy appended real client IP
    mock_req.headers = {"X-Forwarded-For": "1.1.1.1, 198.51.100.2"}

    client_ip = get_client_ip(mock_req, trusted_proxies=["127.0.0.1"])
    assert client_ip == "198.51.100.2"


def test_proxy_malformed_header_safe_fallback():
    """Malformed IP strings in X-Forwarded-For are skipped safely without crashing."""
    mock_req = MagicMock()
    mock_req.client.host = "127.0.0.1"
    mock_req.headers = {"X-Forwarded-For": "<script>alert(1)</script>, invalid-ip, 203.0.113.88"}

    client_ip = get_client_ip(mock_req, trusted_proxies=["127.0.0.1"])
    assert client_ip == "203.0.113.88"


# ===============================================================================
# 2. SEC-02: BOUNDED RATE LIMITER & PER-ACCOUNT LOCKOUT TESTS
# ===============================================================================

def test_bounded_rate_limiter_memory_cap():
    """BoundedRateLimiter never exceeds max_entries under capacity pressure."""
    limiter = BoundedRateLimiter(max_entries=5, prune_interval_seconds=100.0)

    for i in range(20):
        limiter.record_failure(f"ip_{i}", window_seconds=60.0)

    # Buckets count must not exceed max_entries
    assert len(limiter._buckets) <= 5


def test_register_rate_limiting_enforced(test_client):
    """Registration endpoint enforces rate limiting per client IP."""
    rate_limiter.reset()

    test_ip = "198.51.100.99"
    headers = {"X-Forwarded-For": test_ip}

    # 5 attempts allowed
    for i in range(5):
        unique_username = f"reguser_{uuid.uuid4().hex[:8]}"
        res = test_client.post(
            "/api/v1/auth/register",
            json={"username": unique_username, "password": "Password123!"},
            headers=headers,
        )
        assert res.status_code == 200

    # 6th attempt must trigger 429
    res_exceeded = test_client.post(
        "/api/v1/auth/register",
        json={"username": f"reguser_{uuid.uuid4().hex[:8]}", "password": "Password123!"},
        headers=headers,
    )
    assert res_exceeded.status_code == 429
    assert "Too many registration attempts" in res_exceeded.json()["detail"]

    rate_limiter.reset()


def test_login_per_user_lockout_across_distributed_ips(test_client):
    """Per-account lockout triggers after 5 failed attempts even across distributed client IPs."""
    rate_limiter.reset()
    target_account = f"target_{uuid.uuid4().hex[:6]}"

    # 5 failed attempts from 5 distinct IP addresses
    for i in range(5):
        headers = {"X-Forwarded-For": f"203.0.113.{i + 10}"}
        res = test_client.post(
            "/api/v1/auth/login",
            json={"username": target_account, "password": "WrongPassword123!"},
            headers=headers,
        )
        assert res.status_code == 401

    # 6th attempt from a fresh, unused IP must be locked out due to account lockout
    fresh_headers = {"X-Forwarded-For": "198.51.100.200"}
    res_lockout = test_client.post(
        "/api/v1/auth/login",
        json={"username": target_account, "password": "WrongPassword123!"},
        headers=fresh_headers,
    )
    assert res_lockout.status_code == 429
    assert "Too many failed login attempts for this account" in res_lockout.json()["detail"]

    rate_limiter.reset()


def test_login_success_clears_rate_limit(test_client):
    """Successful authentication clears failed attempt counters for IP and username."""
    rate_limiter.reset()
    username = f"cleartest_{uuid.uuid4().hex[:6]}"
    password = "Password123!"

    # Register user
    reg_res = test_client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert reg_res.status_code == 200

    # Record 4 failed attempts
    for _ in range(4):
        test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "WrongPassword!"},
        )

    # 5th attempt succeeds
    success_res = test_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert success_res.status_code == 200

    # Counter should be cleared; subsequent failure should return 401 (not 429)
    next_fail = test_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "WrongPassword!"},
    )
    assert next_fail.status_code == 401

    rate_limiter.reset()


# ===============================================================================
# 3. MIG-01: ATOMIC STAGING TABLE CUTOVER & ROLLBACK VALIDATION
# ===============================================================================

def test_mig01_atomic_staging_cutover_success(tmp_path):
    """Schema v2 migration populates staging table, validates hashes and counts, and commits atomically."""
    db_file = str(tmp_path / "legacy_v1.db")
    engine = create_engine(f"sqlite:///{db_file}")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE schema_versions (
                version INTEGER PRIMARY KEY,
                applied_at DATETIME NOT NULL,
                description TEXT NOT NULL
            )
        """))
        conn.execute(text("INSERT INTO schema_versions VALUES (1, '2026-10-31 00:00:00', 'v1')"))
        conn.execute(text("""
            CREATE TABLE user_sessions (
                token VARCHAR(255) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("INSERT INTO user_sessions VALUES ('raw_tok_1', 1, '2026-10-31 10:00:00')"))
        conn.execute(text("INSERT INTO user_sessions VALUES ('raw_tok_2', 2, '2026-10-31 11:00:00')"))

    # Run migration
    stats = run_database_migration(engine, db_path=db_file)
    assert stats["schema_version"] == 2
    assert stats["user_sessions_migrated"] is True

    # Verify atomic result
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT MAX(version) FROM schema_versions")).scalar()
        assert ver == 2

        # Staging tables must be gone
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [t[0] for t in tables]
        assert "user_sessions" in table_names
        assert not any(t.startswith("_user_sessions_staging_") for t in table_names)

        # Token hashes must be 64-character SHA-256
        rows = conn.execute(text("SELECT token_hash, user_id, expires_at FROM user_sessions")).fetchall()
        assert len(rows) == 2
        for r in rows:
            assert len(r[0]) == 64
            expected_hash = hashlib.sha256(("raw_tok_1" if r[1] == 1 else "raw_tok_2").encode("utf-8")).hexdigest()
            assert r[0] == expected_hash

    engine.dispose()


def test_mig01_atomic_staging_rollback_on_validation_failure(tmp_path):
    """If staging table validation fails, transaction rolls back and original user_sessions is preserved."""
    db_file = str(tmp_path / "rollback_v1.db")
    engine = create_engine(f"sqlite:///{db_file}")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE schema_versions (
                version INTEGER PRIMARY KEY,
                applied_at DATETIME NOT NULL,
                description TEXT NOT NULL
            )
        """))
        conn.execute(text("INSERT INTO schema_versions VALUES (1, '2026-10-31 00:00:00', 'v1')"))
        conn.execute(text("""
            CREATE TABLE user_sessions (
                token VARCHAR(255) PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("INSERT INTO user_sessions VALUES ('orig_tok_123', 42, '2026-10-31 10:00:00')"))

    # Force a validation failure by mocking hashlib.sha256 to return an invalid non-64 hex string
    mock_hash = MagicMock()
    mock_hash.hexdigest.return_value = "short_invalid_hash"

    with patch("hashlib.sha256", return_value=mock_hash):
        with pytest.raises(RuntimeError, match="Migration validation failed: invalid SHA-256 token hash"):
            run_database_migration(engine, db_path=db_file)

    # Verify rollback: schema_version is still 1, and legacy user_sessions is completely untouched
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT MAX(version) FROM schema_versions")).scalar()
        assert ver == 1

        rows = conn.execute(text("SELECT token, user_id FROM user_sessions")).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "orig_tok_123"
        assert rows[0][1] == 42

    engine.dispose()


# ===============================================================================
# 4. MIG-02: MISSING USERS TABLE EDGE CASE & FAIL-CLOSED QUARANTINE
# ===============================================================================

def test_mig02_missing_users_table_quarantines_all_conversations(tmp_path):
    """When 'users' table is absent, conversations must fail closed into quarantine (is_quarantined=1, user_id=0)."""
    db_file = str(tmp_path / "no_users_table.db")
    engine = create_engine(f"sqlite:///{db_file}")

    # Setup database with messages, but NO users table
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                user_id INTEGER,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                source VARCHAR(50),
                timestamp DATETIME NOT NULL
            )
        """))
        # Legacy message claiming user_id=1, but users table does not exist
        conn.execute(text("""
            INSERT INTO messages (session_id, user_id, role, content, source, timestamp)
            VALUES ('sess_orphaned', 1, 'user', 'Hello without users table', NULL, '2026-10-31 10:00:00')
        """))

    stats = run_database_migration(engine, db_path=db_file)
    assert stats["quarantined_conversations"] == 1
    assert stats["migrated_conversations"] == 0

    with engine.connect() as conn:
        conv = conn.execute(text("SELECT id, user_id, is_quarantined FROM conversations WHERE id = 'sess_orphaned'")).fetchone()
        assert conv is not None
        assert conv[1] == 0  # user_id set to 0 for quarantine
        assert conv[2] == 1  # is_quarantined = 1

        # Original messages table preserved completely
        msg = conn.execute(text("SELECT session_id, user_id, content FROM messages")).fetchone()
        assert msg[0] == "sess_orphaned"
        assert msg[1] == 1  # Original user_id preserved untouched
        assert msg[2] == "Hello without users table"

    engine.dispose()


def test_mig02_unregistered_user_id_quarantined(tmp_path):
    """When messages claim a user_id that does not exist in users table, fail closed into quarantine."""
    db_file = str(tmp_path / "unknown_user.db")
    engine = create_engine(f"sqlite:///{db_file}")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                hashed_password VARCHAR(255) NOT NULL
            )
        """))
        conn.execute(text("INSERT INTO users VALUES (1, 'alice', 'pw_hash')"))

        conn.execute(text("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                user_id INTEGER,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                source VARCHAR(50),
                timestamp DATETIME NOT NULL
            )
        """))
        # Message claims user_id=999 which does NOT exist in users table
        conn.execute(text("""
            INSERT INTO messages (session_id, user_id, role, content, source, timestamp)
            VALUES ('sess_unknown_user', 999, 'user', 'Hello with missing user', NULL, '2026-10-31 10:00:00')
        """))

    stats = run_database_migration(engine, db_path=db_file)
    assert stats["quarantined_conversations"] == 1
    assert stats["migrated_conversations"] == 0

    with engine.connect() as conn:
        conv = conn.execute(text("SELECT id, user_id, is_quarantined FROM conversations WHERE id = 'sess_unknown_user'")).fetchone()
        assert conv is not None
        assert conv[1] == 0
        assert conv[2] == 1

    engine.dispose()
