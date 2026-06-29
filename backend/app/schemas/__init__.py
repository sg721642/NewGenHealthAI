"""
NewGenHealthAI — schemas/__init__.py
Exports all Pydantic schemas.
"""

from app.schemas.chat import ChatRequest, ChatResponse, FollowUpData, FollowUpQuestion
from app.schemas.session import MessageResponse, SessionResponse

__all__ = [
    "ChatRequest", "ChatResponse", "FollowUpData", "FollowUpQuestion",
    "SessionResponse", "MessageResponse",
]

