"""
NewGenHealthAI — api/v1/endpoints/auth.py
Authentication endpoints: /register, /login, /logout, /me.
Hardened with Argon2id rehashing, rate limiting, and strict input boundaries.
"""

from collections import defaultdict
import re
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import LEGACY_PBKDF2_SALT
from app.core.dependencies import get_current_user
from app.core.logging_config import logger
from app.models.message import User
from app.services.database_service import db_service

router = APIRouter(prefix="/auth", tags=["Auth"])

# Regex for allowed username characters: letters, numbers, underscores, periods, hyphens
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")

# Simple in-memory rate limiter for failed login attempts
_failed_attempts: Dict[str, List[float]] = defaultdict(list)
_MAX_FAILED_ATTEMPTS = 10
_RATE_LIMIT_WINDOW = 60.0  # seconds


def _get_client_ip(req: Request) -> str:
    forwarded = req.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return req.client.host if req.client else "unknown"


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _failed_attempts[client_ip] if now - t < _RATE_LIMIT_WINDOW]
    _failed_attempts[client_ip] = attempts
    return len(attempts) < _MAX_FAILED_ATTEMPTS


def _record_failed_attempt(client_ip: str) -> None:
    now = time.time()
    _failed_attempts[client_ip].append(now)


def _clear_failed_attempts(client_ip: str) -> None:
    _failed_attempts.pop(client_ip, None)


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=256)


@router.post("/register")
async def register(req: AuthRequest):
    """Register a new user account with strict boundaries."""
    username_clean = req.username.strip()
    if len(username_clean) < 3 or len(username_clean) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be between 3 and 50 characters long",
        )
    if not _USERNAME_PATTERN.match(username_clean):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username may only contain letters, numbers, underscores, periods, and hyphens",
        )
    if len(req.password) < 8 or len(req.password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be between 8 and 128 characters long",
        )

    user = db_service.create_user(username_clean, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Generate cryptographically secure session token
    token = db_service.create_user_session(user.id)
    return {
        "success": True,
        "token": token,
        "username": user.username,
        "user_id": user.id,
    }


@router.post("/login")
async def login(req: AuthRequest, request: Request):
    """Authenticate credentials, rate limit brute force, and rehash legacy passwords."""
    client_ip = _get_client_ip(request)

    if not _check_rate_limit(client_ip):
        logger.warning("Rate limit exceeded for login attempts from IP %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )

    username_clean = req.username.strip()
    user = db_service.get_user_by_username(username_clean)
    if not user:
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Verify password (supports both Argon2id and legacy PBKDF2 with migration salt)
    verification = user.verify_password(req.password, legacy_salt=LEGACY_PBKDF2_SALT)
    if not verification.is_valid:
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Authentication succeeded: clear rate limit counter
    _clear_failed_attempts(client_ip)

    # Automatic safe credential migration to Argon2id
    if verification.needs_rehash and verification.new_hash:
        success = db_service.update_user_password_hash(
            user.id, verification.new_hash, expected_old_hash=user.hashed_password
        )
        if success:
            logger.info("Successfully rehashed credentials to Argon2id for user %d", user.id)

    token = db_service.create_user_session(user.id)
    return {
        "success": True,
        "token": token,
        "username": user.username,
        "user_id": user.id,
    }


@router.post("/logout")
async def logout(req: Request):
    """Invalidate active session token."""
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.strip().lower().startswith("bearer "):
        token = auth_header.strip().split(" ", 1)[1].strip()
        db_service.delete_user_session(token)
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve details for active authenticated user."""
    return {
        "success": True,
        "username": current_user.username,
        "user_id": current_user.id,
    }
