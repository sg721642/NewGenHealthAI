"""
NewGenHealthAI — services/database_service.py
DatabaseService: CRUD operations for conversations, messages, and user accounts.
Strictly enforces server-side conversation ownership and data isolation.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.orm import Session

from app.core.config import SESSION_EXPIRE_HOURS
from app.core.logging_config import logger
from app.db.session import SessionLocal, engine
from app.models.message import Base, Conversation, Message, User, UserSession, _format_utc_iso
from app.db.migrations import run_database_migration


def generate_conversation_title(first_message: str) -> str:
    """Generate a clean, permanent title for a conversation based on the initial query."""
    if not first_message or not first_message.strip():
        return "New Consultation"
    msg = first_message.strip()

    # Common quick recognitions
    msg_lower = msg.lower()
    if any(k in msg_lower for k in ["heart attack", "cardiac", "dil ka daura", "seene me"]):
        return "Cardiac Emergency Consultation"
    if any(k in msg_lower for k in ["brain hemorrhage", "stroke", "behosh", "unconscious"]):
        return "Neurological Emergency Consultation"
    if any(k in msg_lower for k in ["fever", "bukhar", "temperature"]):
        return "Fever Consultation"
    if any(k in msg_lower for k in ["cough", "cold", "flu", "khansi"]):
        return "Respiratory Symptoms Consultation"
    if any(k in msg_lower for k in ["headache", "migraine", "sir dard"]):
        return "Headache Consultation"
    if any(k in msg_lower for k in ["diabetes", "sugar"]):
        return "Diabetes Inquiry"
    if any(k in msg_lower for k in ["hypertension", "bp", "blood pressure"]):
        return "Blood Pressure Inquiry"
    if any(k in msg_lower for k in ["uploaded medical image", "image", "photo"]):
        return "Medical Image Consultation"

    # Take first 4-6 words, up to 35 chars
    words = msg.split()
    clean_words = []
    for w in words[:6]:
        clean_w = w.strip(".,?!;:-_\"'")
        if clean_w:
            clean_words.append(clean_w)
    title = " ".join(clean_words)
    if len(title) > 35:
        title = title[:35] + "..."
    if not title:
        return "New Consultation"
    return title.title()


class DatabaseService:
    """All database operations with strict conversation ownership enforcement."""

    def __init__(self, session_local=None, engine_instance=None):
        self.SessionLocal = session_local or SessionLocal
        self.engine = engine_instance or engine
        logger.info("DatabaseService initialized")

    def init_db(self) -> None:
        """Create all tables and run migrations if needed."""
        logger.info("Initializing database tables and running migrations...")
        db_path = None
        if hasattr(self.engine, "url") and self.engine.url.database:
            db_path = self.engine.url.database
        run_database_migration(self.engine, db_path=db_path)
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    # ─────────────────────────────────────────────────────────────
    # Conversation & Chat History Operations (Strictly Owner-Enforced)
    # ─────────────────────────────────────────────────────────────

    def create_conversation(
        self, user_id: int, session_id: Optional[str] = None, title: Optional[str] = None
    ) -> Conversation:
        """Create and register a new conversation owned by user_id."""
        if not user_id:
            raise ValueError("user_id is required to create a conversation")

        conv_id = session_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id=conv_id,
            user_id=user_id,
            title=title or f"Consultation {conv_id[:8]}",
            created_at=now,
            updated_at=now,
            is_quarantined=0,
        )
        with self.get_session() as session:
            session.add(conv)
            session.commit()
            session.refresh(conv)
            return conv

    def get_conversation(self, session_id: str, user_id: int) -> Optional[Conversation]:
        """Fetch conversation by ID, verifying ownership and non-quarantine status."""
        if not session_id or not user_id:
            return None
        with self.get_session() as session:
            return session.execute(
                select(Conversation).where(
                    Conversation.id == session_id,
                    Conversation.user_id == user_id,
                    Conversation.is_quarantined == 0,
                )
            ).scalar_one_or_none()

    def get_or_create_conversation(self, session_id: str, user_id: int) -> Optional[Conversation]:
        """
        Verify existing conversation ownership and non-quarantine status.
        Returns the Conversation if it exists and belongs to user_id.
        Returns None if not found, owned by another user, or quarantined.
        Does NOT automatically create conversations for arbitrary client-supplied IDs.
        """
        return self.get_conversation(session_id, user_id)

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        source: Optional[str] = None,
        user_id: int = None,
    ) -> None:
        """
        Persist a message, strictly verifying that target conversation exists and belongs to user_id.
        Never creates conversations from arbitrary client-supplied IDs.
        Updates conversation updated_at timestamp.
        """
        if not user_id:
            raise ValueError("user_id is strictly required to persist chat messages")
        if not session_id:
            raise ValueError("session_id is strictly required to persist chat messages")

        with self.get_session() as session:
            conv = session.execute(
                select(Conversation).where(Conversation.id == session_id)
            ).scalar_one_or_none()

            if not conv:
                raise PermissionError(
                    f"Cannot append message: session {session_id} does not exist"
                )
            if conv.user_id != user_id or conv.is_quarantined != 0:
                raise PermissionError(
                    f"Cannot append message: session {session_id} is not owned by user {user_id}"
                )

            conv.updated_at = datetime.now(timezone.utc)
            if role == "user":
                if not conv.title or conv.title.startswith("Consultation ") or conv.title == "New Consultation":
                    conv.title = generate_conversation_title(content)

            session.add(
                Message(
                    session_id=session_id,
                    role=role,
                    content=content,
                    source=source,
                    user_id=user_id,
                )
            )
            session.commit()


    def get_chat_history(self, session_id: str, user_id: int) -> Optional[List[Dict]]:
        """
        Retrieve messages for a conversation owned by user_id.
        Returns None if conversation does not exist or belongs to another user (for 404).
        """
        if not user_id or not session_id:
            return None

        conv = self.get_conversation(session_id, user_id)
        if not conv:
            return None

        with self.get_session() as session:
            stmt = (
                select(Message)
                .where(Message.session_id == session_id, Message.user_id == user_id)
                .order_by(Message.timestamp.asc())
            )
            return [msg.to_dict() for msg in session.execute(stmt).scalars().all()]

    def get_all_sessions(self, user_id: int, limit: int = 100) -> List[Dict]:
        """
        Return a list of all active conversations owned by user_id.
        Never returns records belonging to other users or unauthenticated callers.
        """
        if not user_id:
            return []

        with self.get_session() as session:
            # Query conversations owned by user_id
            conversations = session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id, Conversation.is_quarantined == 0)
                .order_by(desc(Conversation.updated_at))
                .limit(limit)
            ).scalars().all()

            results = []
            needs_commit = False
            for conv in conversations:
                display_title = conv.title
                if not display_title or display_title.startswith("Consultation ") or display_title == "New Consultation":
                    first_msg = session.execute(
                        select(Message.content)
                        .where(Message.session_id == conv.id, Message.user_id == user_id, Message.role == "user")
                        .order_by(Message.timestamp.asc())
                        .limit(1)
                    ).scalar_one_or_none()
                    if first_msg:
                        display_title = generate_conversation_title(first_msg)
                        conv.title = display_title
                        needs_commit = True
                    else:
                        display_title = "New Consultation"

                results.append({
                    "session_id": conv.id,
                    "title": display_title,
                    "preview": display_title,
                    "last_active": _format_utc_iso(conv.updated_at),
                })

            if needs_commit:
                session.commit()

            return results

    def clear_all_user_sessions(self, user_id: int) -> int:
        """
        Delete all conversations and their messages belonging to user_id.
        Returns the number of conversations deleted.
        """
        if not user_id:
            return 0

        with self.get_session() as session:
            # Delete messages belonging to user
            session.execute(
                delete(Message).where(Message.user_id == user_id)
            )
            # Delete conversations belonging to user
            res = session.execute(
                delete(Conversation).where(Conversation.user_id == user_id)
            )
            session.commit()
            logger.info("Cleared all (%d) sessions for user %s", res.rowcount, user_id)
            return res.rowcount

    def delete_session(self, session_id: str, user_id: int) -> bool:
        """
        Delete a conversation and all its messages, verifying ownership.
        Returns True if deleted, False if not found or unauthorized.
        """
        if not session_id or not user_id:
            return False

        with self.get_session() as session:
            conv = session.execute(
                select(Conversation).where(
                    Conversation.id == session_id,
                    Conversation.user_id == user_id,
                    Conversation.is_quarantined == 0,
                )
            ).scalar_one_or_none()

            if not conv:
                logger.warning("Delete attempt on unauthorized or non-existent session %s by user %s", session_id[:8], user_id)
                return False

            # Delete all messages for this session
            session.execute(
                delete(Message).where(Message.session_id == session_id, Message.user_id == user_id)
            )
            # Delete conversation record
            session.delete(conv)
            session.commit()
            logger.info("Deleted session %s for user %s", session_id[:8], user_id)
            return True

    def clear_session(self, session_id: str, user_id: int) -> bool:
        """
        Clear all messages for a session while retaining the conversation entity.
        Returns True if cleared, False if not found or unauthorized.
        """
        if not session_id or not user_id:
            return False

        with self.get_session() as session:
            conv = session.execute(
                select(Conversation).where(
                    Conversation.id == session_id,
                    Conversation.user_id == user_id,
                    Conversation.is_quarantined == 0,
                )
            ).scalar_one_or_none()

            if not conv:
                return False

            session.execute(
                delete(Message).where(Message.session_id == session_id, Message.user_id == user_id)
            )
            conv.updated_at = datetime.now(timezone.utc)
            session.commit()
            logger.info("Cleared messages in session %s for user %s", session_id[:8], user_id)
            return True

    # ─────────────────────────────────────────────────────────────
    # User & Session CRUD operations
    # ─────────────────────────────────────────────────────────────

    def create_user(self, username: str, password_raw: str) -> Optional[User]:
        """Register a new user, returning the user if successful, or None if username exists."""
        with self.get_session() as session:
            try:
                existing = session.execute(
                    select(User).where(User.username == username)
                ).scalar_one_or_none()
                if existing:
                    return None

                hashed = User.hash_password(password_raw)
                user = User(username=username, hashed_password=hashed)
                session.add(user)
                session.commit()
                session.refresh(user)
                return user
            except Exception as e:
                session.rollback()
                logger.warning("Error creating user %s: %s", username, e)
                return None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Fetch a user record by username."""
        with self.get_session() as session:
            return session.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()

    def update_user_password_hash(
        self, user_id: int, new_hash: str, expected_old_hash: str
    ) -> bool:
        """
        Safely update user's password hash using optimistic concurrency control.
        Ensures race-safe credential rehash during migration.
        """
        with self.get_session() as session:
            res = session.execute(
                update(User)
                .where(User.id == user_id, User.hashed_password == expected_old_hash)
                .values(hashed_password=new_hash)
            )
            session.commit()
            return res.rowcount > 0

    def create_user_session(self, user_id: int, expire_hours: Optional[int] = None) -> str:
        """
        Create a new cryptographically secure session token.
        Stores SHA-256 hash in DB; returns raw token to client.
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=expire_hours or SESSION_EXPIRE_HOURS)

        with self.get_session() as session:
            user_session = UserSession(
                token_hash=token_hash,
                user_id=user_id,
                created_at=now,
                expires_at=expires_at,
            )
            session.add(user_session)
            session.commit()
            return raw_token

    def get_user_id_by_token(self, token: str) -> Optional[int]:
        """Validate raw token hash and expiration, returning user_id if active."""
        if not token or not token.strip():
            return None
        token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        with self.get_session() as session:
            user_session = session.execute(
                select(UserSession).where(UserSession.token_hash == token_hash)
            ).scalar_one_or_none()
            if not user_session:
                return None

            now = datetime.now(timezone.utc)
            exp = user_session.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                return None

            return user_session.user_id

    def get_user_by_token(self, token: str) -> Optional[User]:
        """Validate raw token hash and expiration, returning User if active."""
        if not token or not token.strip():
            return None
        token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        with self.get_session() as session:
            user_session = session.execute(
                select(UserSession).where(UserSession.token_hash == token_hash)
            ).scalar_one_or_none()
            if not user_session:
                return None

            now = datetime.now(timezone.utc)
            exp = user_session.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                logger.info("Session token expired for user %s", user_session.user_id)
                return None

            return session.get(User, user_session.user_id)

    def delete_user_session(self, token: str) -> bool:
        """Revoke session token by its SHA-256 hash."""
        if not token or not token.strip():
            return False
        token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        with self.get_session() as session:
            res = session.execute(
                delete(UserSession).where(UserSession.token_hash == token_hash)
            )
            session.commit()
            return res.rowcount > 0

    def cleanup_expired_sessions(self) -> int:
        """Purge all expired session rows."""
        now = datetime.now(timezone.utc)
        with self.get_session() as session:
            res = session.execute(
                delete(UserSession).where(UserSession.expires_at < now)
            )
            session.commit()
            return res.rowcount


# Module-level singleton
db_service = DatabaseService()
