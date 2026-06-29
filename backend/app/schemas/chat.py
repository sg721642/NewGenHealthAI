"""
NewGenHealthAI — schemas/chat.py
Pydantic schemas for chat request and response.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class FollowUpQuestion(BaseModel):
    text: str
    options: List[str] = []


class FollowUpData(BaseModel):
    questions: List[FollowUpQuestion] = []
    triage_round: int = 0
    max_rounds: int = 3


class ChatResponse(BaseModel):
    response: str
    source: str
    timestamp: str
    success: bool
    follow_up: Optional[FollowUpData] = None
