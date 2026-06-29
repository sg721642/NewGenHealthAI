"""
NewGenHealthAI — api/v1/endpoints/voice.py
Voice-related endpoints: /stt (Groq Whisper) and /tts (Edge-TTS).
"""

import os
import re
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from groq import Groq
import edge_tts
from starlette.responses import StreamingResponse
import langid

logger = logging.getLogger("dr_susham")

router = APIRouter(tags=["Voice"])

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def _get_groq_client():
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    return Groq(api_key=GROQ_API_KEY)


def _strip_markdown_for_tts(text: str) -> str:
    """Remove markdown formatting so TTS reads clean text."""
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
async def speech_to_text(file: UploadFile = File(...)):
    """
    Transcribe uploaded audio using Groq Whisper.
    Returns: { "text": "...", "language": "en" }
    """
    client = _get_groq_client()

    try:
        content = await file.read()
        content_size = len(content)

        logger.info("STT: file='%s', size=%d, type=%s",
                     file.filename, content_size, file.content_type)

        if content_size < 100:
            return {"text": "", "language": None, "error": "Audio file is empty"}

        # Determine file extension
        original_name = file.filename or "audio.webm"
        ext = os.path.splitext(original_name)[1].lower()

        supported = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".flac"}
        if ext not in supported:
            ct = (file.content_type or "").lower()
            if "webm" in ct:
                ext = ".webm"
            elif "ogg" in ct:
                ext = ".ogg"
            elif "mp4" in ct or "m4a" in ct:
                ext = ".mp4"
            elif "wav" in ct:
                ext = ".wav"
            else:
                ext = ".webm"

        # Write temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                audio_data = f.read()

            logger.info("STT: Sending %d bytes to Whisper (ext=%s)", len(audio_data), ext)

            transcription = None
            last_error = None

            for model_name in ["whisper-large-v3-turbo", "whisper-large-v3"]:
                try:
                    transcription = client.audio.transcriptions.create(
                        file=(f"recording{ext}", audio_data),
                        model=model_name,
                        response_format="json",
                    )
                    raw_text = transcription.text if transcription else ""
                    logger.info("STT: %s returned: '%s'", model_name, raw_text[:200])
                    break
                except Exception as e:
                    last_error = str(e)
                    logger.warning("STT: %s failed: %s", model_name, e)
                    continue

            if transcription is None:
                logger.error("STT: All models failed: %s", last_error)
                return {"text": "", "language": None, "error": f"Whisper failed: {last_error}"}

            result_text = (transcription.text or "").strip()
            lang = getattr(transcription, "language", None)

            # No filtering — return whatever Whisper gives us.
            # The old hallucination filter was blocking legitimate speech.
            logger.info("STT: Result: '%s' (lang=%s)", result_text[:200], lang)
            return {"text": result_text, "language": lang}

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("STT error: %s", str(e))
        return {"text": "", "language": None, "error": str(e)}


@router.get("/voice/tts")
async def text_to_speech(text: str = Query(...)):
    """Convert text to speech using Edge-TTS with auto language detection."""
    try:
        clean_text = _strip_markdown_for_tts(text)
        if not clean_text or len(clean_text) < 2:
            raise HTTPException(status_code=400, detail="Text too short for TTS")

        if len(clean_text) > 2000:
            clean_text = clean_text[:1997] + "..."

        lang, _ = langid.classify(clean_text)

        voice_map = {
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

        voice = voice_map.get(lang, "en-US-AvaNeural")
        logger.info("TTS: lang=%s, voice=%s, len=%d", lang, voice, len(clean_text))

        communicate = edge_tts.Communicate(clean_text, voice)

        async def audio_generator():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        return StreamingResponse(
            audio_generator(),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=tts_output.mp3"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("TTS error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"TTS Error: {str(e)}")
