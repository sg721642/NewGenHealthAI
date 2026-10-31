"""
NewGenHealthAI — models/message.py
SQLAlchemy ORM models for chat messages, conversations, and user authentication.
Uses Argon2id for secure password hashing with safe legacy PBKDF2 upgrade support.
"""

from datetime import datetime, timezone
import hashlib
import hmac
from typing import Dict, NamedTuple, Optional, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

_hasher = PasswordHasher()


class PasswordVerificationResult(NamedTuple):
    """Result of password verification, indicating rehash requirements."""
    is_valid: bool
    needs_rehash: bool
    new_hash: Optional[str]

    def __bool__(self) -> bool:
        return self.is_valid


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using modern, memory-hard Argon2id."""
        return _hasher.hash(password)

    def verify_password(
        self, password: str, legacy_salt: Optional[bytes] = None
    ) -> PasswordVerificationResult:
        """
        Verify password against stored hash.
        Supports both modern Argon2id ($argon2id$) and legacy PBKDF2 hashes.
        If a legacy hash or outdated parameters are detected, indicates needs_rehash=True with new Argon2id hash.
        Fails closed if legacy salt is missing for legacy hashes.
        """
        if not self.hashed_password or not password:
            return PasswordVerificationResult(False, False, None)

        # 1. Modern Argon2id verification
        if self.hashed_password.startswith("$argon2"):
            try:
                _hasher.verify(self.hashed_password, password)
                needs_rehash = _hasher.check_needs_rehash(self.hashed_password)
                new_hash = _hasher.hash(password) if needs_rehash else None
                return PasswordVerificationResult(True, needs_rehash, new_hash)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return PasswordVerificationResult(False, False, None)

        # 2. Legacy PBKDF2 verification (for safe migration)
        # Note: Fails closed if legacy_salt is not configured
        if not legacy_salt:
            return PasswordVerificationResult(False, False, None)

        legacy_computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), legacy_salt, 100000).hex()
        if hmac.compare_digest(self.hashed_password, legacy_computed):
            new_hash = _hasher.hash(password)
            return PasswordVerificationResult(True, True, new_hash)

        return PasswordVerificationResult(False, False, None)


class UserSession(Base):
    """User authentication session token stored as SHA-256 hash with explicit expiration."""

    __tablename__ = "user_sessions"

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class Conversation(Base):
    """Explicit persistent conversation entity owned by a user."""

    __tablename__ = "conversations"

    id = Column(String(255), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_quarantined = Column(Integer, default=0, nullable=False)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_quarantined": bool(self.is_quarantined),
        }


class Message(Base):
    """Persisted chat message (user or assistant turn)."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # Nullable for legacy chats
    role = Column(String(50), nullable=False)          # "user" | "assistant"
    content = Column(Text, nullable=False)
    source = Column(String(255), nullable=True)        # e.g. "Wikipedia Medical Information"
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

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

