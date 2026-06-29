"""
NewGenHealthAI — api/v1/endpoints/session.py
Session management endpoints: /history, /sessions, /session/{id}.
Supports per-user isolation when Authorization token is provided.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Request

from app.services.database_service import db_service

router = APIRouter(tags=["Session"])


def _get_session_id(request: Request) -> str:
    """Get or create a session ID from X-Session-ID header or cookie session."""
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        return session_id
    if "session_id" not in request.session:
        request.session["session_id"] = str(uuid.uuid4())
    return request.session["session_id"]


def _get_user_id(request: Request) -> Optional[int]:
    """Extract user_id from Authorization Bearer token, or None if unauthenticated."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        return db_service.get_user_id_by_token(token)
    return None


@router.get("/history")
async def get_history_endpoint(req: Request):
    """Return the chat history for the current session (user-isolated)."""
    user_id = _get_user_id(req)
    return {
        "messages": db_service.get_chat_history(_get_session_id(req), user_id=user_id),
        "success": True,
    }


@router.get("/sessions")
async def get_sessions_endpoint(req: Request):
    """Return a list of all chat sessions for the current user."""
    user_id = _get_user_id(req)
    return {"sessions": db_service.get_all_sessions(user_id=user_id), "success": True}


@router.get("/session/{session_id}")
async def load_session_endpoint(session_id: str, req: Request):
    """Load a specific session by ID and set it as the active session."""
    user_id = _get_user_id(req)
    req.session["session_id"] = session_id
    return {
        "messages": db_service.get_chat_history(session_id, user_id=user_id),
        "session_id": session_id,
        "success": True,
    }


@router.delete("/session/{session_id}")
async def delete_session_endpoint(session_id: str, req: Request):
    """Delete a session (user-isolated) and reset active session if it matches."""
    user_id = _get_user_id(req)
    db_service.delete_session(session_id, user_id=user_id)
    if req.session.get("session_id") == session_id:
        req.session["session_id"] = str(uuid.uuid4())
    return {"message": "Session deleted", "success": True}

