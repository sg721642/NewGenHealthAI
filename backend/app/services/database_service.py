"""
NewGenHealthAI — services/database_service.py
DatabaseService: all CRUD operations for chat history.
"""

from typing import Dict, List, Optional

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.db.session import SessionLocal, engine
from app.models.message import Base, Message, User, UserSession


class DatabaseService:
    """All database CRUD operations for chat history."""

    def __init__(self, session_local=None, engine_instance=None):
        self.SessionLocal = session_local or SessionLocal
        self.engine = engine_instance or engine
        logger.info("DatabaseService initialized")

    def init_db(self) -> None:
        """Create all tables if they don't exist."""
        logger.info("Initializing database tables...")
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        source: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> None:
        logger.debug("Saving %s message for session %s...", role, session_id[:8])
        with self.get_session() as session:
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

    def get_chat_history(self, session_id: str, user_id: Optional[int] = None) -> List[Dict]:
        with self.get_session() as session:
            stmt = select(Message).where(Message.session_id == session_id)
            if user_id is not None:
                stmt = stmt.where(Message.user_id == user_id)
            stmt = stmt.order_by(Message.timestamp)
            return [msg.to_dict() for msg in session.execute(stmt).scalars().all()]

    def get_all_sessions(self, user_id: Optional[int] = None) -> List[Dict]:
        with self.get_session() as session:
            latest_sub = (
                select(
                    Message.session_id,
                    func.max(Message.timestamp).label("max_ts"),
                )
                .where(Message.role == "user")
            )
            if user_id is not None:
                latest_sub = latest_sub.where(Message.user_id == user_id)

            latest_sub = latest_sub.group_by(Message.session_id).subquery()

            stmt = (
                select(Message.session_id, Message.content, Message.timestamp)
                .join(
                    latest_sub,
                    (Message.session_id == latest_sub.c.session_id)
                    & (Message.timestamp == latest_sub.c.max_ts),
                )
                .order_by(desc(Message.timestamp))
            )
            return [
                {
                    "session_id": row[0],
                    "preview": row[1][:50] + "..." if len(row[1]) > 50 else row[1],
                    "last_active": row[2].isoformat() if row[2] else None,
                }
                for row in session.execute(stmt).all()
            ]

    def delete_session(self, session_id: str, user_id: Optional[int] = None) -> None:
        logger.info("Deleting session %s...", session_id[:8])
        with self.get_session() as session:
            stmt = delete(Message).where(Message.session_id == session_id)
            if user_id is not None:
                stmt = stmt.where(Message.user_id == user_id)
            session.execute(stmt)
            session.commit()

    # ─────────────────────────────────────────────────────────────
    # User & Session CRUD operations (100% Free Multi-User)
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
        import uuid
        token = str(uuid.uuid4())
        with self.get_session() as session:
            user_session = UserSession(token=token, user_id=user_id)
            session.add(user_session)
            session.commit()
            return token

    def get_user_id_by_token(self, token: str) -> Optional[int]:
        """Validate token and return associated user ID."""
        with self.get_session() as session:
            user_session = session.execute(
                select(UserSession).where(UserSession.token == token)
            ).scalar_one_or_none()
            if user_session:
                return user_session.user_id
            return None

    def delete_user_session(self, token: str) -> None:
        """Delete/invalidate the session token."""
        with self.get_session() as session:
            session.execute(
                delete(UserSession).where(UserSession.token == token)
            )
            session.commit()



# Module-level singleton
db_service = DatabaseService()
