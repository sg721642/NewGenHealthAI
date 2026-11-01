"""
NewGenHealthAI — api/v1/endpoints/voice.py
Voice-related endpoints: authenticated, rate-limited, and resource-bounded /stt (Groq Whisper) and /tts (Edge-TTS).
"""

import os
import re
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from groq import AsyncGroq, BadRequestError, AuthenticationError, PermissionDeniedError
import edge_tts
from starlette.responses import StreamingResponse
import langid

from app.core.dependencies import get_current_user
from app.models.message import User
from app.core.config import (
    GROQ_API_KEY,
    STT_REQUEST_TIMEOUT_SECONDS,
    STT_OVERALL_DEADLINE_SECONDS,
    TTS_REQUEST_TIMEOUT_SECONDS,
    MAX_TTS_INPUT_CHARS,
)
from app.tools.audio_preprocess import (
    validate_and_read_audio_upload,
    create_secure_temp_audio_file,
    cleanup_temp_audio,
    AudioValidationError,
)
from app.tools.voice_capacity import voice_capacity_manager

logger = logging.getLogger("newgenhealthai")

router = APIRouter(tags=["Voice"])

# Maintained allowlist of tested neural voices
TTS_VOICE_MAP = {
    "en": "en-US-AvaNeural",
    "hi": "hi-IN-MadhurNeural",
    "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-VivienneNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-ElsaNeural",
    "bn": "bn-IN-BashkarNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-MohanNeural",
    "mr": "mr-IN-ManoharNeural",
}
TTS_ALLOWED_VOICES = frozenset(TTS_VOICE_MAP.values())


def _get_async_groq_client() -> AsyncGroq:
    """Instantiate non-blocking AsyncGroq client with request timeout."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("STT requested but GROQ_API_KEY is not configured")
        raise HTTPException(
            status_code=503,
            detail="Voice transcription service is unconfigured on this server",
        )
    return AsyncGroq(api_key=api_key, timeout=STT_REQUEST_TIMEOUT_SECONDS)


def _strip_markdown_for_tts(text: str) -> str:
    """Remove markdown formatting so TTS reads clean text."""
    if not text:
        return ""
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"---+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(
        r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\U0001FA00-\U0001FAFF]+",
        "", text,
    )
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


@router.post("/voice/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Transcribe uploaded audio using Groq Whisper with bounded chunked reading,
    magic byte validation, process-local capacity management, and temporary file isolation.
    """
    # 1. Enforce upload validation and bounded streaming read
    try:
        audio_bytes, canonical_ext = await validate_and_read_audio_upload(file)
    except AudioValidationError as e:
        logger.warning("STT validation rejected upload: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 2. Acquire STT capacity permit (bounds global concurrency and per-user active requests)
    async with await voice_capacity_manager.acquire_stt(current_user.id):
        # 3. Create isolated temporary file with restrictive permissions
        temp_file_path, temp_dir = create_secure_temp_audio_file(audio_bytes, canonical_ext)
        try:
            client = _get_async_groq_client()
            models = ["whisper-large-v3-turbo", "whisper-large-v3"]
            transcription = None

            async def _transcribe():
                nonlocal transcription
                for model_name in models:
                    try:
                        with open(temp_file_path, "rb") as f_audio:
                            transcription = await client.audio.transcriptions.create(
                                file=(f"recording{canonical_ext}", f_audio),
                                model=model_name,
                                response_format="json",
                            )
                        if transcription and getattr(transcription, "text", None):
                            logger.info("STT: %s completed successfully", model_name)
                            break
                    except (BadRequestError, AuthenticationError, PermissionDeniedError) as perm_err:
                        # Non-retryable error: malformed input or permanent auth failure
                        logger.error("STT permanent error (%s): %s", model_name, type(perm_err).__name__)
                        break
                    except Exception as transient_err:
                        # Transient error: rate limit or network glitch, attempt fallback
                        logger.warning("STT transient error (%s): %s", model_name, type(transient_err).__name__)
                        continue

            try:
                await asyncio.wait_for(_transcribe(), timeout=STT_OVERALL_DEADLINE_SECONDS)
            except asyncio.TimeoutError:
                logger.error("STT overall deadline exceeded (limit=%.1fs)", STT_OVERALL_DEADLINE_SECONDS)
                raise HTTPException(status_code=504, detail="Transcription request timed out")

            if transcription is None or not getattr(transcription, "text", None):
                logger.error("STT: all candidate models failed or returned empty response")
                raise HTTPException(
                    status_code=503,
                    detail="Transcription service temporarily unavailable",
                )

            result_text = transcription.text.strip()
            lang = getattr(transcription, "language", None)

            # Sanitized logging: log byte count, character count, and language only
            logger.info(
                "STT: transcription successful (bytes=%d, chars=%d, lang=%s)",
                len(audio_bytes), len(result_text), lang,
            )
            return {"text": result_text, "language": lang}

        finally:
            cleanup_temp_audio(temp_file_path, temp_dir)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=5000, description="Text to synthesize into speech")


@router.post("/voice/tts")
async def text_to_speech(
    body: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Convert text to speech using Edge-TTS with auto language detection,
    voice allowlisting, streaming backpressure handling, and per-user concurrency bounding.
    """
    clean_text = _strip_markdown_for_tts(body.text)
    if not clean_text or len(clean_text) < 2:
        raise HTTPException(status_code=400, detail="Text too short for TTS")

    if len(clean_text) > MAX_TTS_INPUT_CHARS:
        clean_text = clean_text[:MAX_TTS_INPUT_CHARS].rstrip()

    # Detect language safely with fallback
    try:
        lang, _ = langid.classify(clean_text)
    except Exception:
        lang = "en"

    voice = TTS_VOICE_MAP.get(lang, "en-US-AvaNeural")
    if voice not in TTS_ALLOWED_VOICES:
        voice = "en-US-AvaNeural"

    # Acquire TTS capacity permit
    permit = await voice_capacity_manager.acquire_tts(current_user.id)

    try:
        communicate = edge_tts.Communicate(clean_text, voice)
    except Exception as e:
        await permit.release()
        logger.error("TTS setup failed: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="Text-to-speech synthesis failed")

    async def audio_stream_generator():
        try:
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    yield chunk["data"]
        except (asyncio.CancelledError, GeneratorExit):
            logger.info("TTS streaming disconnected by client")
            raise
        except Exception as e:
            logger.error("TTS stream chunk error: %s", type(e).__name__)
            raise
        finally:
            await permit.release()

    return StreamingResponse(
        audio_stream_generator(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=tts_output.mp3",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )
