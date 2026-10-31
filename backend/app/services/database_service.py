"""
NewGenHealthAI — services/database_service.py
DatabaseService: CRUD operations for conversations, messages, and user accounts.
Strictly enforces server-side conversation ownership and data isolation.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.db.session import SessionLocal, engine
from app.models.message import Base, Conversation, Message, User, UserSession
from app.db.migrations import run_database_migration


class DatabaseService:
    """All database operations with strict conversation ownership enforcement."""

    def __init__(self, session_local=None, engine_instance=None):
        self.SessionLocal = session_local or SessionLocal
        self.engine = engine_instance or engine
        logger.info("DatabaseService initialized")

    def init_db(self) -> None:
        """Create all tables and run migrations if needed."""
        logger.info("Initializing database tables and running migrations...")
        Base.metadata.create_all(bind=self.engine)
        run_database_migration(self.engine)

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
        Verify existing conversation ownership, or create a new conversation if ID does not exist.
        If the conversation exists but is owned by another user, returns None (fail-closed).
        """
        if not session_id or not user_id:
            return None

        with self.get_session() as session:
            existing = session.execute(
                select(Conversation).where(Conversation.id == session_id)
            ).scalar_one_or_none()

            if existing:
                if existing.user_id == user_id and existing.is_quarantined == 0:
                    return existing
                # Owned by someone else or quarantined -> Fail closed
                logger.warning(
                    "Conversation %s requested by user %s but belongs to user %s",
                    session_id[:8], user_id, existing.user_id
                )
                return None

        # Does not exist yet -> create for this user
        return self.create_conversation(user_id=user_id, session_id=session_id)

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        source: Optional[str] = None,
        user_id: int = None,
    ) -> None:
        """
        Persist a message, verifying that the target conversation belongs to user_id.
        Updates conversation updated_at timestamp.
        """
        if not user_id:
            raise ValueError("user_id is strictly required to persist chat messages")

        with self.get_session() as session:
            conv = session.execute(
                select(Conversation).where(Conversation.id == session_id)
            ).scalar_one_or_none()

            if conv:
                if conv.user_id != user_id or conv.is_quarantined != 0:
                    raise PermissionError(
                        f"Cannot append message: session {session_id} is not owned by user {user_id}"
                    )
                conv.updated_at = datetime.now(timezone.utc)
            else:
                # Register new conversation for this user
                now = datetime.now(timezone.utc)
                session.add(
                    Conversation(
                        id=session_id,
                        user_id=user_id,
                        title=content[:30] + "..." if len(content) > 30 else content,
                        created_at=now,
                        updated_at=now,
                        is_quarantined=0,
                    )
                )

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
            for conv in conversations:
                # Find latest user message for preview
                latest_msg = session.execute(
                    select(Message.content)
                    .where(Message.session_id == conv.id, Message.user_id == user_id, Message.role == "user")
                    .order_by(desc(Message.timestamp))
                    .limit(1)
                ).scalar_one_or_none()

                preview = latest_msg or conv.title or "New Consultation"
                if len(preview) > 50:
                    preview = preview[:50] + "..."

                results.append({
                    "session_id": conv.id,
                    "preview": preview,
                    "last_active": conv.updated_at.isoformat() if conv.updated_at else None,
                })

            return results

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

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Fetch a user record by username."""
        with self.get_session() as session:
            return session.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()

    def create_user_session(self, user_id: int) -> str:
        """Create a new session token for the user."""
        token = str(uuid.uuid4())
        with self.get_session() as session:
            user_session = UserSession(token=token, user_id=user_id)
            session.add(user_session)
            session.commit()
            return token

    def get_user_id_by_token(self, token: str) -> Optional[int]:
        """Validate token and return associated user ID."""
        if not token or not token.strip():
            return None
        with self.get_session() as session:
            user_session = session.execute(
                select(UserSession).where(UserSession.token == token.strip())
            ).scalar_one_or_none()
            if user_session:
                return user_session.user_id
            return None

    def get_user_by_token(self, token: str) -> Optional[User]:
        """Validate token and return associated User record."""
        if not token or not token.strip():
            return None
        with self.get_session() as session:
            user_session = session.execute(
                select(UserSession).where(UserSession.token == token.strip())
            ).scalar_one_or_none()
            if not user_session:
                return None
            return session.get(User, user_session.user_id)

    def delete_user_session(self, token: str) -> None:
        """Delete/invalidate the session token."""
        if not token:
            return
        with self.get_session() as session:
            session.execute(
                delete(UserSession).where(UserSession.token == token.strip())
            )
            session.commit()


# Module-level singleton
db_service = DatabaseService()
