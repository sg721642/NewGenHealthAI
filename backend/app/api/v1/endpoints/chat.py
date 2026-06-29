"""
NewGenHealthAI — api/v1/endpoints/chat.py
Clinical Intelligence endpoints: /chat, /clear, /new-chat.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import clinical_engine
from app.services.database_service import db_service

router = APIRouter(tags=["Chat"])


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


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, req: Request):
    """Process a user message through the clinical intelligence pipeline."""
    if not clinical_engine.workflow_app:
        raise HTTPException(status_code=503, detail="System not initialized")
    session_id = _get_session_id(req)
    user_id = _get_user_id(req)
    return await clinical_engine.process_message(session_id, request.message, user_id=user_id)


@router.post("/clear")
async def clear_endpoint(req: Request):
    """Clear the in-memory clinical state for the current session."""
    clinical_engine.clear_conversation(_get_session_id(req))
    return {"message": "Clinical state cleared", "success": True}


@router.post("/new-chat")
async def new_chat_endpoint(req: Request):
    """Create a new clinical session with a fresh session ID."""
    new_id = str(uuid.uuid4())
    req.session["session_id"] = new_id
    return {"message": "New clinical session created", "session_id": new_id, "success": True}

