"""
NewGenHealthAI — tools/llm_client.py
Groq LLM client singleton with multi-model fallback resilience.
"""

import os
import time
from typing import Any, Dict, List, Optional
from app.core.config import GROQ_API_KEY, GROQ_CHAT_MODEL, GROQ_FALLBACK_MODELS, OFFLINE_MODE, is_offline_mode
from app.core.logging_config import logger

_cached_llms = {}
_readiness_cache: Dict[str, Any] = {
    "checked_at": 0.0,
    "ready": False,
    "status": "uninitialized",
    "detail": "",
}
_last_invocation_outcome: Dict[str, Any] = {
    "timestamp": 0.0,
    "success": None,
    "error": None,
}


def get_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
):
    """Return a cached ChatGroq LLM instance for the specified or default model."""
    if is_offline_mode():
        logger.info("get_llm: OFFLINE_MODE is active; skipping LLM client initialization")
        return None

    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not found in environment variables")
        return None

    target_model = (model_name or GROQ_CHAT_MODEL).strip()
    cache_key = (target_model, temperature, max_tokens)

    if cache_key in _cached_llms:
        return _cached_llms[cache_key]

    from langchain_groq import ChatGroq

    try:
        instance = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name=target_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        _cached_llms[cache_key] = instance
        logger.info("LLM client initialized (Groq / %s, temp=%.1f)", target_model, temperature)
        return instance
    except Exception as e:
        logger.error("Failed to initialize ChatGroq for model '%s': %s", target_model, e)
        return None


def invoke_llm_with_fallback(
    prompt: Any,
    candidate_models: Optional[List[str]] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
):
    """
    Invoke Groq LLM across candidate models in priority order.
    Catches NotFoundError / model deprecation errors and attempts the next candidate model.
    """
    if is_offline_mode():
        logger.info("invoke_llm_with_fallback: OFFLINE_MODE is active; skipping external LLM invocation")
        return None

    if not GROQ_API_KEY:
        logger.warning("invoke_llm_with_fallback: GROQ_API_KEY missing")
        return None

    if candidate_models:
        models = [m.strip() for m in candidate_models if m.strip()]
    else:
        models = [GROQ_CHAT_MODEL] + [m for m in GROQ_FALLBACK_MODELS if m != GROQ_CHAT_MODEL]

    last_error = None
    for model_name in models:
        try:
            llm = get_llm(model_name=model_name, temperature=temperature, max_tokens=max_tokens)
            if not llm:
                continue
            response = llm.invoke(prompt)
            _last_invocation_outcome["timestamp"] = time.time()
            _last_invocation_outcome["success"] = True
            _last_invocation_outcome["error"] = None
            return response
        except Exception as e:
            last_error = e
            err_msg = str(e)
            is_not_found = (
                "404" in err_msg
                or "NotFoundError" in type(e).__name__
                or "model_not_found" in err_msg
                or "does not exist" in err_msg
                or "decommissioned" in err_msg
                or "deprecated" in err_msg
            )
            if is_not_found:
                logger.warning(
                    "Groq model '%s' unavailable (not found / deprecated); trying next fallback model...",
                    model_name,
                )
            else:
                logger.warning(
                    "Groq model '%s' invocation error (%s): %s; checking fallbacks...",
                    model_name, type(e).__name__, err_msg[:120],
                )

    if last_error:
        _last_invocation_outcome["timestamp"] = time.time()
        _last_invocation_outcome["success"] = False
        _last_invocation_outcome["error"] = f"{type(last_error).__name__}: {str(last_error)[:100]}"
        logger.error("All candidate Groq models exhausted. Last error: %s", last_error)
    return None


def check_ai_provider_readiness(
    ttl_seconds: float = 60.0,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Low-cost, bounded, cached readiness probe for Groq AI provider.
    Zero token expense: checks recent invocation health or probes models.list().
    Never exposes credentials or API keys.
    """
    if not GROQ_API_KEY or not GROQ_API_KEY.strip():
        return {
            "ready": False,
            "status": "missing_api_key",
            "detail": "GROQ_API_KEY not configured",
        }

    now = time.time()

    # 1. Check if recent invocation outcome occurred within ttl
    if _last_invocation_outcome["timestamp"] > 0:
        age = now - _last_invocation_outcome["timestamp"]
        if age < ttl_seconds:
            if _last_invocation_outcome["success"] is True:
                _readiness_cache.update({
                    "checked_at": now,
                    "ready": True,
                    "status": "operational",
                    "detail": "Recent invocation successful",
                })
                return {
                    "ready": True,
                    "status": "operational",
                    "detail": "Recent invocation successful",
                }
            elif _last_invocation_outcome["success"] is False:
                _readiness_cache.update({
                    "checked_at": now,
                    "ready": False,
                    "status": "degraded",
                    "detail": _last_invocation_outcome["error"] or "Recent invocation failed",
                })
                return {
                    "ready": False,
                    "status": "degraded",
                    "detail": _last_invocation_outcome["error"] or "Recent invocation failed",
                }

    # 2. Return cached readiness if within ttl and not forced
    if (
        not force_refresh
        and (now - _readiness_cache["checked_at"] < ttl_seconds)
        and _readiness_cache["status"] != "uninitialized"
    ):
        return {
            "ready": _readiness_cache["ready"],
            "status": _readiness_cache["status"],
            "detail": _readiness_cache["detail"],
        }

    # 3. Perform low-cost bounded probe via Groq SDK models.list() (zero token cost)
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY, timeout=3.0)
        _ = client.models.list()
        _readiness_cache.update({
            "checked_at": now,
            "ready": True,
            "status": "operational",
            "detail": "Provider reachable and authenticated",
        })
        return {
            "ready": True,
            "status": "operational",
            "detail": "Provider reachable and authenticated",
        }
    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e)[:100]
        safe_detail = f"{err_type}: {err_msg}"
        if GROQ_API_KEY and GROQ_API_KEY in safe_detail:
            safe_detail = safe_detail.replace(GROQ_API_KEY, "[REDACTED]")

        _readiness_cache.update({
            "checked_at": now,
            "ready": False,
            "status": "provider_unreachable",
            "detail": safe_detail,
        })
        return {
            "ready": False,
            "status": "provider_unreachable",
            "detail": safe_detail,
        }

