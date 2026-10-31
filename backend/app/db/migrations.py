"""
NewGenHealthAI — db/migrations.py
Safe, versioned, idempotent SQLite migrations with online backup and recovery support.
Uses SQLite Online Backup API for crash-consistent live snapshots even in WAL mode.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import text, inspect
from app.core.logging_config import logger

CURRENT_SCHEMA_VERSION = 1


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
    1. Online backup executed before any schema modifications.
    2. Version-tracked via 'schema_versions' table.
    3. Ensures 'conversations' table exists with proper indices.
    4. Migrates legacy messages with conservative ownership reconstruction:
       - Pure single-owner sessions (no NULL rows, exactly one valid user_id in users table): migrated.
       - Mixed sessions (NULL + user_id): strictly quarantined (never backfilled).
       - Conflicting sessions (multiple user_ids): strictly quarantined.
       - Anonymous sessions (all NULL user_ids): strictly quarantined.
       - Original messages and ownership are preserved unmodified during quarantine.
    """
    # Extract dynamic db_path from engine if not provided
    if db_path is None:
        engine_db = getattr(engine_instance.url, "database", None)
        if engine_db and engine_db != ":memory:":
            db_path = engine_db

    # Execute online backup BEFORE any schema operations
    if db_path and os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        backup_database(db_path)

    stats = {
        "conversations_table_created": False,
        "migrated_conversations": 0,
        "quarantined_conversations": 0,
        "already_migrated": 0,
        "schema_version": 0,
    }

    with engine_instance.connect() as conn:
        inspector = inspect(engine_instance)
        table_names = inspector.get_table_names()

        # Step 0: Check schema_versions if it already exists
        if "schema_versions" in table_names:
            latest_version = conn.execute(text("SELECT MAX(version) FROM schema_versions")).scalar()
            if latest_version is not None and latest_version >= CURRENT_SCHEMA_VERSION:
                logger.info("Database schema already at version %d. Skipping migration.", latest_version)
                already_migrated = 0
                if "conversations" in table_names:
                    already_migrated = conn.execute(text("SELECT count(*) FROM conversations")).scalar() or 0
                stats["already_migrated"] = already_migrated
                stats["schema_version"] = latest_version
                return stats

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

        # Step 1: Ensure conversations table exists
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
            stats["conversations_table_created"] = True
            logger.info("Created 'conversations' table with indices.")

        if "messages" not in table_names:
            now_dt = datetime.now(timezone.utc)
            conn.execute(text("""
                INSERT INTO schema_versions (version, applied_at, description)
                VALUES (:ver, :applied_at, :desc)
            """), {
                "ver": CURRENT_SCHEMA_VERSION,
                "applied_at": now_dt,
                "desc": "Phase 1B: conversations table, conservative ownership reconstruction, schema tracking",
            })
            conn.commit()
            stats["schema_version"] = CURRENT_SCHEMA_VERSION
            return stats

        # Step 2: Inspect existing messages and reconstruct ownership conservatively
        message_cols = [c["name"] for c in inspector.get_columns("messages")]
        users_exist = "users" in table_names

        existing_sessions = conn.execute(text("SELECT DISTINCT session_id FROM messages")).fetchall()
        session_ids = [row[0] for row in existing_sessions if row[0]]

        for sid in session_ids:
            # Check if conversation already registered
            existing_conv = conn.execute(
                text("SELECT id FROM conversations WHERE id = :sid"),
                {"sid": sid}
            ).fetchone()
            if existing_conv:
                stats["already_migrated"] += 1
                continue

            # Fetch timestamps
            ts_row = conn.execute(
                text("SELECT MIN(timestamp), MAX(timestamp) FROM messages WHERE session_id = :sid"),
                {"sid": sid}
            ).fetchone()
            created_at = ts_row[0] if (ts_row and ts_row[0]) else datetime.now(timezone.utc)
            updated_at = ts_row[1] if (ts_row and ts_row[1]) else datetime.now(timezone.utc)

            # If messages table lacks user_id column, quarantine immediately
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

            # Analyze message ownership for this session
            msg_rows = conn.execute(
                text("SELECT DISTINCT user_id FROM messages WHERE session_id = :sid"),
                {"sid": sid}
            ).fetchall()

            has_null = any(r[0] is None for r in msg_rows)
            distinct_non_null = [r[0] for r in msg_rows if r[0] is not None]

            # Verify that user exists in users table
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

            # Conservative ownership rule:
            # ONLY migrate cleanly if:
            # 1. No NULL user_id rows exist for this session
            # 2. Exactly ONE distinct non-null user_id exists
            # 3. The user exists in the users table
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
                # Ambiguous, mixed NULL + user, NULL-only, conflicting, or unknown user -> Quarantine
                # CRITICAL: Preserve all original messages and their user_id values unmodified
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
                logger.warning(
                    "Quarantined session %s (has_null=%s, distinct_non_null=%s, user_exists=%s)",
                    sid[:8], has_null, distinct_non_null, user_exists
                )

        # Record schema version in schema_versions table
        now_dt = datetime.now(timezone.utc)
        conn.execute(text("""
            INSERT INTO schema_versions (version, applied_at, description)
            VALUES (:ver, :applied_at, :desc)
        """), {
            "ver": CURRENT_SCHEMA_VERSION,
            "applied_at": now_dt,
            "desc": "Phase 1B: conversations table, conservative ownership reconstruction, schema tracking",
        })
        conn.commit()
        stats["schema_version"] = CURRENT_SCHEMA_VERSION

    return stats
