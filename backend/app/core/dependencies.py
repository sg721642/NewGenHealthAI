"""
NewGenHealthAI — core/dependencies.py
Authoritative, reusable authentication and authorization dependencies.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request, status

from app.models.message import User
from app.services.database_service import db_service


def get_current_user(request: Request) -> User:
    """
    Enforce authenticated principal from Authorization: Bearer <token>.
    Fails closed with HTTP 401 if missing, invalid, or expired.
    Never falls back to anonymous access for protected resources.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    user = db_service.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_user(request: Request) -> Optional[User]:
    """
    Extract user from Bearer token if present and valid; otherwise None.
    Use ONLY for public endpoints with non-sensitive progressive enhancements.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None

    token = parts[1].strip()
    return db_service.get_user_by_token(token)

