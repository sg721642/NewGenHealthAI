"""
NewGenHealthAI — db/migrations.py
Safe, versioned, idempotent SQLite migrations with backup and recovery support.
"""

import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import text, inspect, create_engine
from app.core.logging_config import logger


def backup_database(db_path: str) -> Optional[str]:
    """Create a consistent timestamped file backup of the SQLite database."""
    if not os.path.exists(db_path):
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    try:
        shutil.copy2(db_path, backup_path)
        logger.info("Database backed up to: %s", backup_path)
        return backup_path
    except Exception as e:
        logger.error("Failed to backup database at %s: %s", db_path, e)
        raise RuntimeError(f"Database backup failed: {e}") from e


def restore_database(backup_path: str, target_db_path: str) -> bool:
    """Restore database from a previous backup file."""
    if not os.path.exists(backup_path):
        logger.error("Backup file not found: %s", backup_path)
        return False

    try:
        shutil.copy2(backup_path, target_db_path)
        logger.info("Database restored from %s to %s", backup_path, target_db_path)
        return True
    except Exception as e:
        logger.error("Failed to restore database from %s: %s", backup_path, e)
        return False


def run_database_migration(engine_instance, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Run version-guarded, idempotent database migration.
    1. Ensures 'conversations' table exists with proper indices.
    2. Migrates legacy messages without conversation records:
       - If session messages unambiguously belong to one valid user_id: assigns ownership.
       - If session messages have conflicting user_ids or null user_id: quarantines the session.
    3. Preserves all existing user and message records.
    """
    if db_path and os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        backup_database(db_path)

    stats = {
        "conversations_table_created": False,
        "migrated_conversations": 0,
        "quarantined_conversations": 0,
        "already_migrated": 0,
    }

    with engine_instance.connect() as conn:
        # Check existing tables using inspector
        inspector = inspect(engine_instance)
        table_names = inspector.get_table_names()

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
            return stats

        # Step 2: Inspect existing distinct session_ids in messages
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

            # Analyze message ownership for this session
            msg_rows = conn.execute(
                text("SELECT DISTINCT user_id FROM messages WHERE session_id = :sid"),
                {"sid": sid}
            ).fetchall()

            distinct_user_ids = [r[0] for r in msg_rows if r[0] is not None]

            # Get earliest and latest timestamp
            ts_row = conn.execute(
                text("SELECT MIN(timestamp), MAX(timestamp) FROM messages WHERE session_id = :sid"),
                {"sid": sid}
            ).fetchone()
            created_at = ts_row[0] if (ts_row and ts_row[0]) else datetime.now(timezone.utc)
            updated_at = ts_row[1] if (ts_row and ts_row[1]) else datetime.now(timezone.utc)

            # Rule: Unambiguous ownership iff exactly ONE distinct non-null user_id exists
            if len(distinct_user_ids) == 1:
                owner_id = distinct_user_ids[0]
                # Verify that owner exists in users table if users table exists
                user_exists = True
                if "users" in table_names:
                    u_row = conn.execute(
                        text("SELECT id FROM users WHERE id = :uid"),
                        {"uid": owner_id}
                    ).fetchone()
                    user_exists = bool(u_row)

                if user_exists:
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
                    # Also backfill any null user_ids in this session to the confirmed owner
                    conn.execute(text("""
                        UPDATE messages SET user_id = :user_id
                        WHERE session_id = :sid AND user_id IS NULL
                    """), {"user_id": owner_id, "sid": sid})
                    conn.commit()
                    stats["migrated_conversations"] += 1
                    logger.info("Migrated conversation %s to owner %s", sid[:8], owner_id)
                    continue

            # Conflicting, orphaned, or completely anonymous -> Quarantine
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
            logger.warning("Quarantined ambiguous/anonymous conversation %s", sid[:8])

    return stats
