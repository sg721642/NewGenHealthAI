"""
NewGenHealthAI — models/message.py
SQLAlchemy ORM model for chat messages.
"""

from datetime import datetime
import hashlib
from typing import Dict

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using robust, dependency-free pbkdf2_hmac."""
        salt = b"susham_health_ai_salt_12983719"
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return key.hex()

    def verify_password(self, password: str) -> bool:
        """Verify the password against the stored hash."""
        return self.hashed_password == self.hash_password(password)


class UserSession(Base):
    """User authentication session token."""

    __tablename__ = "user_sessions"

    token = Column(String(255), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Message(Base):
    """Persisted chat message (user or assistant turn)."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # Nullable for legacy chats
    role = Column(String(50), nullable=False)          # "user" | "assistant"
    content = Column(Text, nullable=False)
    source = Column(String(255), nullable=True)        # e.g. "Wikipedia Medical Information"
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

