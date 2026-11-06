"""
NewGenHealthAI — tools/audio_preprocess.py
Secure audio upload validation, magic byte checking, duration probing, and temporary file management.
"""

import os
import io
import shutil
import struct
import tempfile
import secrets
import logging
from typing import Optional, Tuple
from fastapi import UploadFile

from app.core.config import (
    MAX_AUDIO_UPLOAD_BYTES,
    MIN_AUDIO_UPLOAD_BYTES,
    MAX_AUDIO_DURATION_SECONDS,
)

logger = logging.getLogger("newgenhealthai")


class AudioValidationError(Exception):
    """Raised when uploaded audio fails security, container, or size validation."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# Canonical supported audio signatures
SUPPORTED_CONTAINERS = frozenset({".wav", ".webm", ".ogg", ".mp3", ".m4a", ".mp4", ".flac"})


def _detect_audio_container(content: bytes) -> Optional[str]:
    """
    Detect audio container format from header magic bytes without trusting client MIME or extension.
    Returns canonical extension (e.g. '.wav', '.webm') or None if unsupported/corrupt.
    """
    if len(content) < 4:
        return None

    # 1. WAV / RIFF: 'RIFF....WAVE'
    if content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WAVE":
        return ".wav"

    # 2. Ogg: 'OggS'
    if content.startswith(b"OggS"):
        return ".ogg"

    # 3. WebM / Matroska: EBML header '\x1a\x45\xdf\xa3'
    if content.startswith(b"\x1a\x45\xdf\xa3"):
        return ".webm"

    # 4. FLAC: 'fLaC'
    if content.startswith(b"fLaC"):
        return ".flac"

    # 5. MP3: ID3v2 header ('ID3') or MPEG audio frame sync (\xff\xfb, \xff\xf3, \xff\xf2, \xff\xe3)
    if content.startswith(b"ID3"):
        return ".mp3"
    if len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0:
        return ".mp3"

    # 6. MP4 / M4A: ISO base media file format ('....ftyp' within first 16 bytes)
    if len(content) >= 12:
        if content[4:8] == b"ftyp":
            return ".m4a"
        if content[8:12] == b"ftyp":
            return ".m4a"

    return None


def probe_wav_duration_seconds(content: bytes) -> Optional[float]:
    """
    Lightweight, safe duration extraction from WAV header without running shell commands.
    Returns duration in seconds, or None if not a valid WAV or duration cannot be parsed safely.
    """
    if len(content) < 44 or not (content.startswith(b"RIFF") and content[8:12] == b"WAVE"):
        return None

    try:
        fmt_idx = content.find(b"fmt ")
        if fmt_idx == -1 or fmt_idx + 24 > len(content):
            return None

        byte_rate = struct.unpack("<I", content[fmt_idx + 16 : fmt_idx + 20])[0]
        if byte_rate == 0:
            return None

        data_idx = content.find(b"data", fmt_idx)
        if data_idx == -1 or data_idx + 8 > len(content):
            return None

        data_size = struct.unpack("<I", content[data_idx + 4 : data_idx + 8])[0]
        if data_size == 0 or data_size > len(content):
            data_size = len(content) - (data_idx + 8)

        duration = data_size / byte_rate
        return duration
    except Exception:
        return None


async def validate_and_read_audio_upload(
    file: UploadFile,
    max_bytes: Optional[int] = None,
    min_bytes: Optional[int] = None,
    chunk_size: int = 64 * 1024,
) -> Tuple[bytes, str]:
    """
    Read uploaded audio in bounded chunks to prevent unbounded memory allocation.
    Validates magic bytes, checks file bounds, and probes duration.
    Returns (audio_bytes, canonical_extension).
    """
    if max_bytes is None:
        from app.core.config import MAX_AUDIO_UPLOAD_BYTES
        max_bytes = MAX_AUDIO_UPLOAD_BYTES
    if min_bytes is None:
        from app.core.config import MIN_AUDIO_UPLOAD_BYTES
        min_bytes = MIN_AUDIO_UPLOAD_BYTES
    if chunk_size <= 0:
        chunk_size = 64 * 1024

    chunks = []
    total_bytes = 0


    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                logger.warning(
                    "Audio upload exceeded limit (limit=%d bytes, current=%d bytes)",
                    max_bytes, total_bytes,
                )
                raise AudioValidationError(
                    f"Audio file exceeds maximum permitted upload limit of {max_bytes} bytes",
                    status_code=400,
                )
            chunks.append(chunk)
    finally:
        await file.close()

    if total_bytes < min_bytes:
        logger.warning("Audio upload too short (size=%d bytes, min=%d bytes)", total_bytes, min_bytes)
        raise AudioValidationError(
            "Audio file is empty or too short to contain valid speech",
            status_code=400,
        )

    audio_bytes = b"".join(chunks)

    # Magic byte container verification
    canonical_ext = _detect_audio_container(audio_bytes)
    if not canonical_ext:
        logger.warning(
            "Unsupported or corrupt audio container uploaded (size=%d bytes)",
            len(audio_bytes),
        )
        raise AudioValidationError(
            "Unsupported or corrupt audio container. Supported formats: WAV, WebM, OGG, MP3, M4A, FLAC",
            status_code=400,
        )

    # Lightweight duration check for WAV
    if canonical_ext == ".wav":
        wav_duration = probe_wav_duration_seconds(audio_bytes)
        if wav_duration is not None and wav_duration > MAX_AUDIO_DURATION_SECONDS:
            logger.warning(
                "Audio duration exceeded limit (duration=%.1fs, limit=%.1fs)",
                wav_duration, MAX_AUDIO_DURATION_SECONDS,
            )
            raise AudioValidationError(
                f"Audio recording duration ({wav_duration:.1f}s) exceeds maximum permitted limit of {MAX_AUDIO_DURATION_SECONDS:.0f}s",
                status_code=400,
            )

    return audio_bytes, canonical_ext


def create_secure_temp_audio_file(audio_bytes: bytes, ext: str) -> Tuple[str, str]:
    """
    Write audio to a temporary file inside an isolated, private directory with restrictive permissions (0o700/0o600).
    Returns (file_path, directory_path).
    """
    temp_dir = tempfile.mkdtemp(prefix="ngh_voice_")
    try:
        os.chmod(temp_dir, 0o700)
    except Exception:
        pass

    safe_filename = f"audio_{secrets.token_hex(16)}{ext}"
    file_path = os.path.join(temp_dir, safe_filename)

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    mode = 0o600
    fd = os.open(file_path, flags, mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)
    except Exception:
        cleanup_temp_audio(file_path, temp_dir)
        raise

    return file_path, temp_dir


def cleanup_temp_audio(file_path: Optional[str] = None, dir_path: Optional[str] = None):
    """
    Safely delete temporary audio file and directory without leaking exceptions or touching other files.
    """
    if file_path:
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception:
            pass

    if dir_path:
        try:
            if os.path.isdir(dir_path) and os.path.basename(dir_path).startswith("ngh_voice_"):
                shutil.rmtree(dir_path, ignore_errors=True)
        except Exception:
            pass
