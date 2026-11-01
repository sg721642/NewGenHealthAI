"""
NewGenHealthAI — api/v1/endpoints/chat.py
Clinical Intelligence endpoints: /chat, /clear, /new-chat.
Strictly requires authenticated user and enforces conversation ownership.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.dependencies import get_current_user
from app.models.message import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import clinical_engine
from app.services.database_service import db_service

router = APIRouter(tags=["Chat"])


def _get_session_id(request: Request) -> str:
    """Get or generate a session ID from X-Session-ID header or cookie session."""
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        return session_id
    if "session_id" not in request.session:
        request.session["session_id"] = str(uuid.uuid4())
    return request.session["session_id"]


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Process a user message through the clinical intelligence pipeline.
    Strictly user-authenticated; enforces ownership of session.
    Rejects unknown or unowned client-supplied X-Session-ID with 404.
    """
    if not clinical_engine.workflow_app:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System not initialized",
        )

    client_session_id = req.headers.get("X-Session-ID")
    if client_session_id:
        conv = db_service.get_conversation(client_session_id, current_user.id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        session_id = conv.id
    else:
        # Check if active session in cookie is valid and owned; otherwise create new
        cookie_session_id = req.session.get("session_id")
        conv = None
        if cookie_session_id:
            conv = db_service.get_conversation(cookie_session_id, current_user.id)
        if not conv:
            conv = db_service.create_conversation(user_id=current_user.id)
        session_id = conv.id

    req.session["session_id"] = session_id

    try:
        return await clinical_engine.process_message(
            session_id, request.message, user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except PermissionError:
        # Fails closed without disclosing existence of other user's session
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    except RuntimeError as e:
        if "cleared or deleted" in str(e).lower() or "no longer exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conversation was cleared or deleted during processing",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the consultation",
        )


@router.post("/clear")
async def clear_endpoint(
    req: Request, current_user: User = Depends(get_current_user)
):
    """
    Clear in-memory clinical state and persisted messages for the active session.
    Verifies that the session is owned by current_user.
    """
    session_id = req.headers.get("X-Session-ID") or req.session.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    conv = db_service.get_conversation(session_id, current_user.id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    cleared = clinical_engine.clear_conversation(session_id, user_id=current_user.id)
    if hasattr(cleared, "__await__"):
        cleared = await cleared
    if not cleared:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return {
        "message": "Clinical state and conversation history cleared",
        "session_id": session_id,
        "success": True,
    }


@router.post("/new-chat")
async def new_chat_endpoint(
    req: Request, current_user: User = Depends(get_current_user)
):
    """
    Create a new clinical session with a fresh server-generated conversation ID.
    Registers the conversation under current_user ownership.
    """
    conv = db_service.create_conversation(user_id=current_user.id)
    req.session["session_id"] = conv.id
    return {
        "message": "New clinical session created",
        "session_id": conv.id,
        "success": True,
    }
