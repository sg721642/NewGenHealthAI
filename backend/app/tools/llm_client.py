"""
NewGenHealthAI — tools/llm_client.py
Groq LLM client singleton with multi-model fallback resilience.
"""

from typing import Any, List, Optional
from app.core.config import GROQ_API_KEY, GROQ_CHAT_MODEL, GROQ_FALLBACK_MODELS
from app.core.logging_config import logger

_cached_llms = {}


def get_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
):
    """Return a cached ChatGroq LLM instance for the specified or default model."""
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
        logger.error("All candidate Groq models exhausted. Last error: %s", last_error)
    return None
