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
    Preserves active triage follow-up chips.
    """
    messages = db_service.get_chat_history(session_id, user_id=current_user.id)
    if messages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    req.session["session_id"] = session_id

    # Retrieve or reconstruct active triage follow-up chips if session is mid-intake
    follow_up = None
    from app.services.chat_service import clinical_engine
    memory_key = clinical_engine._get_memory_key(current_user.id, session_id)
    if memory_key in clinical_engine.conversation_states:
        state = clinical_engine.conversation_states[memory_key]
        if state.get("triage_status") == "needs_info":
            follow_up = state.get("follow_up_data")

    if not follow_up and messages and len(messages) > 0:
        last_msg = messages[-1]
        if last_msg.get("role") == "assistant" and last_msg.get("source") == "Clinical Triage":
            rehydrated = clinical_engine._get_or_restore_state(session_id, current_user.id)
            r = rehydrated.get("triage_round", 0)
            if 0 < r <= 3:
                from app.agents.triage_agent import _get_fallback_triage_question
                fb = _get_fallback_triage_question(
                    r - 1,
                    rehydrated.get("question", ""),
                    rehydrated.get("collected_symptoms", []),
                    rehydrated.get("questions_asked", []),
                )
                if fb:
                    follow_up = {
                        "questions": [{"text": fb["question_text"], "options": fb["options"]}],
                        "triage_round": r,
                        "max_rounds": 3,
                    }

    # If follow-up exists, tag the last assistant message so frontend maps it
    if follow_up and messages and len(messages) > 0:
        messages[-1]["follow_up"] = follow_up

    return {
        "messages": messages,
        "session_id": session_id,
        "follow_up": follow_up,
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
    if hasattr(deleted, "__await__"):
        deleted = await deleted
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if req.session.get("session_id") == session_id:
        req.session.pop("session_id", None)

    return {"message": "Session deleted", "success": True}


@router.delete("/sessions")
async def clear_all_sessions_endpoint(
    req: Request, current_user: User = Depends(get_current_user)
):
    """
    Delete all conversations and in-memory states belonging to the authenticated user.
    Never touches records belonging to other users.
    """
    count = db_service.clear_all_user_sessions(user_id=current_user.id)
    clinical_engine.clear_user_states(user_id=current_user.id)
    req.session.pop("session_id", None)
    return {
        "message": f"Successfully deleted {count} consultation(s)",
        "deleted_count": count,
        "success": True,
    }
