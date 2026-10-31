"""
NewGenHealthAI — api/v1/endpoints/session.py
Session management endpoints: /history, /sessions, /session/{id}.
Strictly requires authenticated user; enforces server-side conversation ownership.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.dependencies import get_current_user
from app.models.message import User
from app.services.chat_service import clinical_engine
from app.services.database_service import db_service

router = APIRouter(tags=["Session"])


def _get_session_id(request: Request) -> str:
    """Get or generate a session ID from X-Session-ID header or cookie session."""
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        return session_id
    if "session_id" not in request.session:
        request.session["session_id"] = str(uuid.uuid4())
    return request.session["session_id"]


@router.get("/history")
async def get_history_endpoint(
    req: Request, current_user: User = Depends(get_current_user)
):
    """
    Return the chat history for the current session.
    Fails with 401 if unauthenticated, 404 if conversation not owned.
    """
    session_id = _get_session_id(req)
    messages = db_service.get_chat_history(session_id, user_id=current_user.id)
    if messages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return {
        "messages": messages,
        "session_id": session_id,
        "success": True,
    }


@router.get("/sessions")
async def get_sessions_endpoint(
    req: Request, current_user: User = Depends(get_current_user)
):
    """Return all chat sessions belonging to the authenticated user."""
    return {
        "sessions": db_service.get_all_sessions(user_id=current_user.id),
        "success": True,
    }


@router.get("/session/{session_id}")
async def load_session_endpoint(
    session_id: str, req: Request, current_user: User = Depends(get_current_user)
):
    """
    Load a specific session by ID and set it as active session.
    Fails with 404 if session does not exist or belongs to another user.
    """
    messages = db_service.get_chat_history(session_id, user_id=current_user.id)
    if messages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    req.session["session_id"] = session_id
    return {
        "messages": messages,
        "session_id": session_id,
        "success": True,
    }


@router.delete("/session/{session_id}")
async def delete_session_endpoint(
    session_id: str, req: Request, current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation and in-memory state, strictly verifying ownership.
    Fails with 404 if session not owned or not found.
    """
    deleted = clinical_engine.delete_conversation(session_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if req.session.get("session_id") == session_id:
        req.session.pop("session_id", None)

    return {"message": "Session deleted", "success": True}
