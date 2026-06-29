"""
NewGenHealthAI — api/v1/endpoints/auth.py
Authentication endpoints: /register, /login, /logout, /me.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.models.message import User
from app.services.database_service import db_service

router = APIRouter(prefix="/auth", tags=["Auth"])


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register(req: AuthRequest):
    """Register a new user account."""
    username_clean = req.username.strip()
    if len(username_clean) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long",
        )
    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long",
        )

    user = db_service.create_user(username_clean, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Generate session token automatically upon registration
    token = db_service.create_user_session(user.id)
    return {
        "success": True,
        "token": token,
        "username": user.username,
        "user_id": user.id,
    }


@router.post("/login")
async def login(req: AuthRequest):
    """Authenticate credentials and return a session token."""
    username_clean = req.username.strip()
    user = db_service.get_user_by_username(username_clean)
    if not user or not user.verify_password(req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = db_service.create_user_session(user.id)
    return {
        "success": True,
        "token": token,
        "username": user.username,
        "user_id": user.id,
    }


@router.post("/logout")
async def logout(req: Request):
    """Invalidate the session token."""
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        db_service.delete_user_session(token)
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_me(req: Request):
    """Retrieve details for the active authenticated user."""
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = auth_header.split(" ")[1]
    user_id = db_service.get_user_id_by_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token",
        )

    with db_service.get_session() as session:
        from app.models.message import User as DBUser
        user = session.get(DBUser, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return {
            "success": True,
            "username": user.username,
            "user_id": user.id,
        }
