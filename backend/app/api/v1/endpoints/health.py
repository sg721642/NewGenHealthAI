"""
NewGenHealthAI — api/v1/endpoints/health.py
Health check endpoint.
"""

from fastapi import APIRouter
from app.core.config import GROQ_API_KEY, TAVILY_API_KEY, GROQ_CHAT_MODEL

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Returns service health status and AI provider availability."""
    groq_ready = bool(GROQ_API_KEY and GROQ_API_KEY.strip())
    tavily_ready = bool(TAVILY_API_KEY and TAVILY_API_KEY.strip())
    return {
        "status": "healthy",
        "service": "NewGenHealthAI Backend v3",
        "ai_ready": groq_ready,
        "providers": {
            "groq": groq_ready,
            "tavily": tavily_ready,
            "chat_model": GROQ_CHAT_MODEL,
        },
    }
