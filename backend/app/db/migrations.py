"""
NewGenHealthAI — db/migrations.py
Safe, versioned, idempotent SQLite migrations with online backup and recovery support.
Uses SQLite Online Backup API for crash-consistent live snapshots even in WAL mode.
"""

import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from sqlalchemy import text, inspect
from app.core.logging_config import logger

CURRENT_SCHEMA_VERSION = 2


def backup_database(db_path: str, backup_dir: Optional[str] = None) -> Optional[str]:
    """
    Create a crash-consistent, verified point-in-time backup of the SQLite database
    using SQLite's Online Backup API. Safe with active WAL-mode concurrency.
    """
    if not db_path or not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:8]

    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        base_name = os.path.basename(db_path)
        backup_path = os.path.join(backup_dir, f"{base_name}.backup_{timestamp}_{unique_suffix}")
    else:
        backup_path = f"{db_path}.backup_{timestamp}_{unique_suffix}"

    try:
        # SQLite Online Backup API safely snapshots database pages including uncheckpointed WAL frames
        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        # Verify backup integrity
        with sqlite3.connect(backup_path) as verify_conn:
            res = verify_conn.execute("PRAGMA integrity_check").fetchone()
            if not res or str(res[0]).strip().lower() != "ok":
                raise RuntimeError(f"Integrity check failed for backup {backup_path}: {res}")

        logger.info("Database online backup verified and stored at: %s", backup_path)
        return backup_path

    except Exception as e:
        logger.error("Failed to safely backup database at %s: %s", db_path, e)
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                pass
        raise RuntimeError(f"Database online backup failed: {e}") from e


def restore_database(backup_path: str, target_db_path: str) -> bool:
    """
    Restore database from an online backup file using SQLite Online Backup API.
    Verifies backup integrity before replacing target database.
    """
    if not backup_path or not os.path.exists(backup_path):
        logger.error("Backup file not found: %s", backup_path)
        return False

    try:
        # Verify source backup integrity before restore
        with sqlite3.connect(backup_path) as verify_conn:
            res = verify_conn.execute("PRAGMA integrity_check").fetchone()
            if not res or str(res[0]).strip().lower() != "ok":
                logger.error("Restore aborted: backup file %s failed integrity check: %s", backup_path, res)
                return False

        # Online restore
        src_conn = sqlite3.connect(backup_path)
        dst_conn = sqlite3.connect(target_db_path)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        logger.info("Database successfully restored from %s to %s", backup_path, target_db_path)
        return True

    except Exception as e:
        logger.error("Failed to restore database from %s to %s: %s", backup_path, target_db_path, e)
        return False


def run_database_migration(engine_instance, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Run version-guarded, idempotent database migration.
    1. Check current schema version BEFORE performing backup to avoid runaway backup accumulation.
    2. Online backup executed only when migration actions are needed.
    3. Version-tracked via 'schema_versions' table.
    4. Version 1: Ensures 'conversations' table exists and migrates legacy messages conservatively.
    5. Version 2: Migrates 'user_sessions' to store SHA-256 token hashes and explicit expires_at.
    """
    # Extract dynamic db_path from engine if not provided
    if db_path is None:
        engine_db = getattr(engine_instance.url, "database", None)
        if engine_db and engine_db != ":memory:":
            db_path = engine_db

    stats = {
        "conversations_table_created": False,
        "migrated_conversations": 0,
        "quarantined_conversations": 0,
        "already_migrated": 0,
        "schema_version": 0,
        "user_sessions_migrated": False,
    }

    # Step 0: Pre-check schema_versions BEFORE creating any backups
    with engine_instance.connect() as conn:
        inspector = inspect(engine_instance)
        table_names = inspector.get_table_names()

        latest_version = 0
        if "schema_versions" in table_names:
            ver = conn.execute(text("SELECT MAX(version) FROM schema_versions")).scalar()
            if ver is not None:
                latest_version = ver

        if latest_version >= CURRENT_SCHEMA_VERSION:
            logger.info("Database schema already at version %d. Skipping migration.", latest_version)
            if "conversations" in table_names:
                stats["already_migrated"] = conn.execute(text("SELECT count(*) FROM conversations")).scalar() or 0
            stats["schema_version"] = latest_version
            return stats

    # Migration is genuinely required -> Execute online backup before schema operations
    if db_path and os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        backup_database(db_path)

    with engine_instance.connect() as conn:
        inspector = inspect(engine_instance)
        table_names = inspector.get_table_names()

        # Ensure schema_versions table exists
        if "schema_versions" not in table_names:
            conn.execute(text("""
                CREATE TABLE schema_versions (
                    version INTEGER PRIMARY KEY,
                    applied_at DATETIME NOT NULL,
                    description TEXT NOT NULL
                )
            """))
            conn.commit()
            table_names.append("schema_versions")

        latest_version = conn.execute(text("SELECT MAX(version) FROM schema_versions")).scalar() or 0

        # ── Step 1: Version 1 Migration (Conversations & Ownership Reconstruction) ──
        if latest_version < 1:
            if "conversations" not in table_names:
                conn.execute(text("""
                    CREATE TABLE conversations (
                        id VARCHAR(255) PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        title VARCHAR(255),
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        is_quarantined INTEGER NOT NULL DEFAULT 0
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id)"))
                conn.commit()
                table_names.append("conversations")
                stats["conversations_table_created"] = True
                logger.info("Created 'conversations' table with indices.")

            if "messages" in table_names:
                message_cols = [c["name"] for c in inspector.get_columns("messages")]
                users_exist = "users" in table_names

                existing_sessions = conn.execute(text("SELECT DISTINCT session_id FROM messages")).fetchall()
                session_ids = [row[0] for row in existing_sessions if row[0]]

                for sid in session_ids:
                    existing_conv = conn.execute(
                        text("SELECT id FROM conversations WHERE id = :sid"),
                        {"sid": sid}
                    ).fetchone()
                    if existing_conv:
                        stats["already_migrated"] += 1
                        continue

                    ts_row = conn.execute(
                        text("SELECT MIN(timestamp), MAX(timestamp) FROM messages WHERE session_id = :sid"),
                        {"sid": sid}
                    ).fetchone()
                    created_at = ts_row[0] if (ts_row and ts_row[0]) else datetime.now(timezone.utc)
                    updated_at = ts_row[1] if (ts_row and ts_row[1]) else datetime.now(timezone.utc)

                    if "user_id" not in message_cols:
                        conn.execute(text("""
                            INSERT INTO conversations (id, user_id, title, created_at, updated_at, is_quarantined)
                            VALUES (:id, 0, :title, :created_at, :updated_at, 1)
                        """), {
                            "id": sid,
                            "title": f"Quarantined Legacy Session {sid[:8]}",
                            "created_at": created_at,
                            "updated_at": updated_at,
                        })
                        conn.commit()
                        stats["quarantined_conversations"] += 1
                        continue

                    msg_rows = conn.execute(
                        text("SELECT DISTINCT user_id FROM messages WHERE session_id = :sid"),
                        {"sid": sid}
                    ).fetchall()

                    has_null = any(r[0] is None for r in msg_rows)
                    distinct_non_null = [r[0] for r in msg_rows if r[0] is not None]

                    user_exists = False
                    if len(distinct_non_null) == 1:
                        owner_id = distinct_non_null[0]
                        if users_exist:
                            u_row = conn.execute(
                                text("SELECT id FROM users WHERE id = :uid"),
                                {"uid": owner_id}
                            ).fetchone()
                            user_exists = bool(u_row)
                        else:
                            user_exists = True

                    if not has_null and len(distinct_non_null) == 1 and user_exists:
                        owner_id = distinct_non_null[0]
                        conn.execute(text("""
                            INSERT INTO conversations (id, user_id, title, created_at, updated_at, is_quarantined)
                            VALUES (:id, :user_id, :title, :created_at, :updated_at, 0)
                        """), {
                            "id": sid,
                            "user_id": owner_id,
                            "title": f"Consultation {sid[:8]}",
                            "created_at": created_at,
                            "updated_at": updated_at,
                        })
                        conn.commit()
                        stats["migrated_conversations"] += 1
                        logger.info("Migrated clean session %s to confirmed owner %s", sid[:8], owner_id)
                    else:
                        conn.execute(text("""
                            INSERT INTO conversations (id, user_id, title, created_at, updated_at, is_quarantined)
                            VALUES (:id, 0, :title, :created_at, :updated_at, 1)
                        """), {
                            "id": sid,
                            "title": f"Quarantined Legacy Session {sid[:8]}",
                            "created_at": created_at,
                            "updated_at": updated_at,
                        })
                        conn.commit()
                        stats["quarantined_conversations"] += 1

            now_dt = datetime.now(timezone.utc)
            conn.execute(text("""
                INSERT INTO schema_versions (version, applied_at, description)
                VALUES (1, :applied_at, :desc)
            """), {
                "applied_at": now_dt,
                "desc": "Phase 1B: conversations table, conservative ownership reconstruction, schema tracking",
            })
            conn.commit()
            latest_version = 1

        # ── Step 2: Version 2 Migration (user_sessions Token Hashing & Expiration) ──
        if latest_version < 2:
            if "user_sessions" not in table_names:
                conn.execute(text("""
                    CREATE TABLE user_sessions (
                        token_hash VARCHAR(64) PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        created_at DATETIME NOT NULL,
                        expires_at DATETIME NOT NULL
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions (user_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions (expires_at)"))
                conn.commit()
                stats["user_sessions_migrated"] = True
                logger.info("Created 'user_sessions' table with schema v2.")
            else:
                session_cols = [c["name"] for c in inspector.get_columns("user_sessions")]
                if "token_hash" not in session_cols:
                    logger.info("Upgrading user_sessions to schema v2 (SHA-256 token hashing & expires_at)...")
                    conn.execute(text("""
                        CREATE TABLE user_sessions_v2 (
                            token_hash VARCHAR(64) PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            created_at DATETIME NOT NULL,
                            expires_at DATETIME NOT NULL
                        )
                    """))
                    conn.commit()

                    legacy_sessions = conn.execute(text("SELECT token, user_id, created_at FROM user_sessions")).fetchall()
                    for row in legacy_sessions:
                        raw_tok = str(row[0]).strip() if row[0] else ""
                        if not raw_tok:
                            continue
                        tok_hash = hashlib.sha256(raw_tok.encode("utf-8")).hexdigest()
                        uid = row[1]
                        c_at = row[2]
                        if isinstance(c_at, str):
                            try:
                                c_dt = datetime.fromisoformat(c_at)
                            except Exception:
                                c_dt = datetime.now(timezone.utc)
                        elif isinstance(c_at, datetime):
                            c_dt = c_at
                        else:
                            c_dt = datetime.now(timezone.utc)

                        exp_dt = c_dt + timedelta(hours=24)

                        conn.execute(text("""
                            INSERT OR REPLACE INTO user_sessions_v2 (token_hash, user_id, created_at, expires_at)
                            VALUES (:th, :uid, :cat, :exp)
                        """), {"th": tok_hash, "uid": uid, "cat": c_dt, "exp": exp_dt})
                    conn.commit()

                    conn.execute(text("DROP TABLE user_sessions"))
                    conn.execute(text("ALTER TABLE user_sessions_v2 RENAME TO user_sessions"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions (user_id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions (expires_at)"))
                    conn.commit()
                    stats["user_sessions_migrated"] = True
                    logger.info("Successfully migrated %d legacy sessions to schema v2.", len(legacy_sessions))

            now_dt = datetime.now(timezone.utc)
            conn.execute(text("""
                INSERT INTO schema_versions (version, applied_at, description)
                VALUES (2, :applied_at, :desc)
            """), {
                "applied_at": now_dt,
                "desc": "Phase 1C: user_sessions SHA-256 token hashing and explicit session expiration",
            })
            conn.commit()
            latest_version = 2

        stats["schema_version"] = latest_version

    return stats
