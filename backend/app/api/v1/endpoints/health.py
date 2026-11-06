"""
NewGenHealthAI — api/v1/endpoints/health.py
Health check endpoint.
"""

from fastapi import APIRouter
from app.core.config import TAVILY_API_KEY, GROQ_CHAT_MODEL
from app.tools.llm_client import check_ai_provider_readiness

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Returns service health status and truthful AI provider availability."""
    readiness = check_ai_provider_readiness()
    tavily_ready = bool(TAVILY_API_KEY and TAVILY_API_KEY.strip())
    return {
        "status": "healthy",
        "service": "NewGenHealthAI Backend v3",
        "ai_ready": readiness["ready"],
        "providers": {
            "groq": readiness["ready"],
            "groq_status": readiness["status"],
            "groq_detail": readiness["detail"],
            "tavily": tavily_ready,
            "chat_model": GROQ_CHAT_MODEL,
        },
    }

