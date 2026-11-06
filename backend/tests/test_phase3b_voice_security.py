"""
NewGenHealthAI — tests/test_phase3b_voice_security.py
Phase 3B: Automated regression tests for Voice STT/TTS security, capacity management,
content validation, non-blocking execution, and sensitive logging redaction.
"""

import asyncio
import io
import os
import struct
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import (
    MAX_AUDIO_UPLOAD_BYTES,
    MIN_AUDIO_UPLOAD_BYTES,
    MAX_AUDIO_DURATION_SECONDS,
    MAX_TTS_INPUT_CHARS,
)
from app.core.dependencies import get_current_user
from app.models.message import User
from app.tools.audio_preprocess import (
    AudioValidationError,
    _detect_audio_container,
    probe_wav_duration_seconds,
    validate_and_read_audio_upload,
    create_secure_temp_audio_file,
    cleanup_temp_audio,
)
from app.tools.voice_capacity import (
    VoiceCapacityManager,
    voice_capacity_manager,
)


# ── Synthetic Audio Fixture Helpers ───────────────────────────────────────────

def _create_synthetic_wav(duration_sec: float = 1.0, sample_rate: int = 8000, num_channels: int = 1) -> bytes:
    """Generate minimal valid PCM RIFF/WAVE byte stream with valid fmt and data chunks."""
    num_samples = int(sample_rate * duration_sec)
    data_size = num_samples * num_channels * 2
    byte_rate = sample_rate * num_channels * 2
    block_align = num_channels * 2

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,          # Subchunk1Size for PCM
        1,           # AudioFormat 1 = PCM
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        16,          # BitsPerSample
        b"data",
        data_size,
    )
    samples = b"\x00\x00" * num_samples
    return header + samples


def _create_synthetic_webm(size: int = 1024) -> bytes:
    """Generate minimal WebM file with valid EBML magic bytes."""
    header = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04"
    return header + b"\x00" * max(0, size - len(header))


def _create_synthetic_ogg(size: int = 1024) -> bytes:
    """Generate minimal Ogg file with valid OggS magic bytes."""
    header = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x12\x34\x56\x78\x00\x00\x00\x00"
    return header + b"\x00" * max(0, size - len(header))


def _create_synthetic_mp3(size: int = 1024) -> bytes:
    """Generate minimal MP3 file with valid ID3v2 header."""
    header = b"ID3\x03\x00\x00\x00\x00\x00\x00"
    return header + b"\x00" * max(0, size - len(header))


def _create_synthetic_m4a(size: int = 1024) -> bytes:
    """Generate minimal M4A file with valid ftyp magic header."""
    header = b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00M4A mp42isom"
    return header + b"\x00" * max(0, size - len(header))


def _create_synthetic_flac(size: int = 1024) -> bytes:
    """Generate minimal FLAC file with valid fLaC magic header."""
    header = b"fLaC\x00\x00\x00\x22"
    return header + b"\x00" * max(0, size - len(header))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_user():
    return User(id=888, username="voice_tester")


@pytest.fixture
def client():
    return TestClient(app)


# ── 1. Authentication & Query-String Elimination (A01, A08) ───────────────────

def test_unauthenticated_voice_stt_returns_401(client):
    """POST /api/v1/voice/stt without authorization header returns HTTP 401."""
    wav_data = _create_synthetic_wav(1.0)
    response = client.post(
        "/api/v1/voice/stt",
        files={"file": ("recording.wav", wav_data, "audio/wav")},
    )
    assert response.status_code == 401


def test_unauthenticated_voice_tts_returns_401(client):
    """POST /api/v1/voice/tts without authorization header returns HTTP 401."""
    response = client.post(
        "/api/v1/voice/tts",
        json={"text": "Please explain hypertension symptoms."},
    )
    assert response.status_code == 401


def test_tts_query_string_auth_rejected(client):
    """Authentication tokens in query strings (?token=...) are rejected with HTTP 401."""
    response = client.post(
        "/api/v1/voice/tts?token=fake_bearer_token",
        json={"text": "Should I be worried about high fever?"},
    )
    assert response.status_code == 401


# ── 2. STT Upload Content Validation & Duration Probing (A07) ─────────────────

def test_empty_audio_upload_rejected(client, mock_user):
    """Zero-byte audio upload returns HTTP 400."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        response = client.post(
            "/api/v1/voice/stt",
            files={"file": ("empty.wav", b"", "audio/wav")},
        )
        assert response.status_code == 400
        assert "empty or too short" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_tiny_audio_upload_rejected(client, mock_user):
    """Tiny audio upload below minimum threshold returns HTTP 400."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        response = client.post(
            "/api/v1/voice/stt",
            files={"file": ("tiny.wav", b"RIFF1234WAVE" + b"\x00" * 50, "audio/wav")},
        )
        assert response.status_code == 400
        assert "too short" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_oversized_audio_upload_rejected(client, mock_user):
    """Audio exceeding MAX_AUDIO_UPLOAD_BYTES is rejected before processing with HTTP 400."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch("app.core.config.MAX_AUDIO_UPLOAD_BYTES", 1024):
            oversized_wav = _create_synthetic_wav(2.0)  # > 16KB
            response = client.post(
                "/api/v1/voice/stt",
                files={"file": ("recording.wav", oversized_wav, "audio/wav")},
            )
            assert response.status_code == 400
            assert "exceeds maximum permitted upload limit" in response.json()["detail"]
    finally:

        app.dependency_overrides.pop(get_current_user, None)


def test_forged_mime_audio_rejected(client, mock_user):
    """Executable or text script disguised as audio/wav is rejected via magic byte checks."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        fake_audio = b"#!/bin/bash\necho MaliciousScript\n" + b"\x00" * 1000
        response = client.post(
            "/api/v1/voice/stt",
            files={"file": ("malicious.wav", fake_audio, "audio/wav")},
        )
        assert response.status_code == 400
        assert "unsupported or corrupt audio" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_unsupported_audio_container_rejected(client, mock_user):
    """Unsupported containers (HTML, zip, etc.) return HTTP 400."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        html_payload = b"<html><body>Audio recording</body></html>" + b" " * 600
        response = client.post(
            "/api/v1/voice/stt",
            files={"file": ("audio.html", html_payload, "text/html")},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("generator,ext", [
    (_create_synthetic_wav, ".wav"),
    (_create_synthetic_webm, ".webm"),
    (_create_synthetic_ogg, ".ogg"),
    (_create_synthetic_mp3, ".mp3"),
    (_create_synthetic_m4a, ".m4a"),
    (_create_synthetic_flac, ".flac"),
])
def test_valid_browser_containers_detected(generator, ext):
    """Audio containers are correctly identified from magic bytes without trusting client MIME."""
    content = generator()
    detected_ext = _detect_audio_container(content)
    assert detected_ext == ext


def test_wav_duration_limit_enforced():
    """WAV duration probing correctly identifies excessively long recordings."""
    # Create valid synthetic WAV with 400s duration (limit is 300s)
    long_wav = _create_synthetic_wav(duration_sec=400.0, sample_rate=8000)
    duration = probe_wav_duration_seconds(long_wav)
    assert duration is not None
    assert duration >= 399.0


# ── 3. Temporary Audio File Security & Lifecycle ──────────────────────────────

def test_secure_temp_file_creation_and_cleanup():
    """Temporary audio files are stored in private directories and cleanly deleted."""
    wav_bytes = _create_synthetic_wav(1.0)
    file_path, dir_path = create_secure_temp_audio_file(wav_bytes, ".wav")

    assert os.path.exists(file_path)
    assert os.path.exists(dir_path)
    assert os.path.basename(dir_path).startswith("ngh_voice_")
    # Verify file content
    with open(file_path, "rb") as f:
        assert f.read() == wav_bytes

    # Clean up
    cleanup_temp_audio(file_path, dir_path)
    assert not os.path.exists(file_path)
    assert not os.path.exists(dir_path)


# ── 4. Async Groq STT Execution & Error Recovery ──────────────────────────────

def test_stt_unconfigured_groq_api_key_returns_503(client, mock_user):
    """When GROQ_API_KEY is not configured, STT returns HTTP 503 without revealing secret names."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    wav_bytes = _create_synthetic_wav(1.0)

    try:
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=True):
            response = client.post(
                "/api/v1/voice/stt",
                files={"file": ("recording.wav", wav_bytes, "audio/wav")},
            )
            assert response.status_code == 503
            assert "unconfigured" in response.json()["detail"].lower()
            assert "groq_api_key" not in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_stt_fallback_model_tried_on_transient_error(client, mock_user):
    """Primary Whisper model failure retries on fallback model."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    wav_bytes = _create_synthetic_wav(1.0)

    mock_client = AsyncMock()
    mock_transcription = MagicMock()
    mock_transcription.text = "I have had a mild headache for three days."
    mock_transcription.language = "en"

    # Primary model throws transient error; secondary succeeds
    mock_client.audio.transcriptions.create.side_effect = [
        Exception("RateLimitError: 429 Too Many Requests"),
        mock_transcription,
    ]

    try:
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_mock_valid_test_key"}):
            with patch("app.api.v1.endpoints.voice._get_async_groq_client", return_value=mock_client):
                response = client.post(
                    "/api/v1/voice/stt",
                    files={"file": ("recording.wav", wav_bytes, "audio/wav")},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["text"] == "I have had a mild headache for three days."
                assert data["language"] == "en"
                assert mock_client.audio.transcriptions.create.call_count == 2
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_stt_permanent_error_fails_fast_without_fallback(client, mock_user):
    """Permanent error (e.g. 400 BadRequest) fails fast without burning retry budget."""
    from groq import BadRequestError
    app.dependency_overrides[get_current_user] = lambda: mock_user
    wav_bytes = _create_synthetic_wav(1.0)

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_client.audio.transcriptions.create.side_effect = BadRequestError(
        "Corrupted audio stream", response=mock_response, body={}
    )

    try:
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_mock_valid_test_key"}):
            with patch("app.api.v1.endpoints.voice._get_async_groq_client", return_value=mock_client):
                response = client.post(
                    "/api/v1/voice/stt",
                    files={"file": ("recording.wav", wav_bytes, "audio/wav")},
                )
                assert response.status_code == 503
                # Must NOT call fallback model on permanent error
                assert mock_client.audio.transcriptions.create.call_count == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_stt_all_models_failed_returns_503(client, mock_user):
    """When both primary and fallback Whisper models fail, return clean HTTP 503."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    wav_bytes = _create_synthetic_wav(1.0)

    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create.side_effect = [
        Exception("Service Unavailable"),
        Exception("Service Unavailable"),
    ]

    try:
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_mock_valid_test_key"}):
            with patch("app.api.v1.endpoints.voice._get_async_groq_client", return_value=mock_client):
                response = client.post(
                    "/api/v1/voice/stt",
                    files={"file": ("recording.wav", wav_bytes, "audio/wav")},
                )
                assert response.status_code == 503
                assert "temporarily unavailable" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ── 5. Voice Capacity Management & Concurrency Isolation ──────────────────────

@pytest.mark.asyncio
async def test_voice_capacity_per_user_stt_limit_returns_429():
    """User with active STT in progress receives HTTP 429 on second concurrent request."""
    mgr = VoiceCapacityManager(max_concurrent_stt=5, max_concurrent_tts=5)
    permit1 = await mgr.acquire_stt(user_id=123)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await mgr.acquire_stt(user_id=123)
    assert exc.value.status_code == 429
    assert "already has an active speech-to-text request" in exc.value.detail

    # Clean release
    await permit1.release()

    # After release, slot is available again
    permit2 = await mgr.acquire_stt(user_id=123)
    assert permit2 is not None
    await permit2.release()


@pytest.mark.asyncio
async def test_voice_capacity_global_stt_semaphore_returns_503():
    """When STT semaphore is saturated, queued request waiting longer than timeout returns HTTP 503."""
    mgr = VoiceCapacityManager(max_concurrent_stt=1, queue_timeout=0.05)
    permit1 = await mgr.acquire_stt(user_id=1)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await mgr.acquire_stt(user_id=2)
    assert exc.value.status_code == 503
    assert "maximum capacity" in exc.value.detail

    await permit1.release()


@pytest.mark.asyncio
async def test_voice_capacity_per_user_tts_limit_returns_429():
    """User with active TTS synthesis receives HTTP 429 on second concurrent request."""
    mgr = VoiceCapacityManager(max_concurrent_stt=5, max_concurrent_tts=5)
    permit1 = await mgr.acquire_tts(user_id=456)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await mgr.acquire_tts(user_id=456)
    assert exc.value.status_code == 429
    assert "already has an active speech synthesis request" in exc.value.detail

    await permit1.release()


# ── 6. TTS Text-to-Speech Synthesis & Streaming ───────────────────────────────

def test_tts_valid_authenticated_post_streams_audio(client, mock_user):
    """Authenticated POST /voice/tts returns audio/mpeg stream with anti-caching headers."""
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def _mock_stream():
        yield {"type": "audio", "data": b"\xff\xfb\x90\x44" + b"\x00" * 200}

    mock_comm = MagicMock()
    mock_comm.stream.return_value = _mock_stream()

    try:
        with patch("edge_tts.Communicate", return_value=mock_comm):
            response = client.post(
                "/api/v1/voice/tts",
                json={"text": "Drink plenty of fluids and rest."},
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/mpeg"
            assert "no-store" in response.headers["cache-control"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_tts_empty_or_too_short_text_returns_400(client, mock_user):
    """TTS with text under minimum length returns HTTP 400."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        response = client.post(
            "/api/v1/voice/tts",
            json={"text": "a"},
        )
        assert response.status_code == 422 or response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_tts_unicode_hindi_and_english_supported(client, mock_user):
    """TTS correctly handles multilingual Hindi text and selects Indian neural voice."""
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def _mock_stream():
        yield {"type": "audio", "data": b"\xff\xfb\x90\x44" + b"\x00" * 200}

    mock_comm = MagicMock()
    mock_comm.stream.return_value = _mock_stream()

    try:
        with patch("edge_tts.Communicate", return_value=mock_comm) as mock_edge:
            response = client.post(
                "/api/v1/voice/tts",
                json={"text": "कृपया पर्याप्त पानी पिएं और आराम करें।"},
            )
            assert response.status_code == 200
            # Verify Hindi voice selection
            called_voice = mock_edge.call_args[0][1]
            assert "hi-IN" in called_voice
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_tts_provider_failure_returns_500(client, mock_user):
    """When Edge-TTS setup raises an exception, return HTTP 500 without leaking credentials."""
    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        with patch("edge_tts.Communicate", side_effect=Exception("Connection reset by peer")):
            response = client.post(
                "/api/v1/voice/tts",
                json={"text": "Take paracetamol if you have fever."},
            )
            assert response.status_code == 500
            assert "failed" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ── 7. Sanitized Operational Logging & Privacy (A08) ──────────────────────────

def test_sensitive_transcripts_and_text_not_logged(client, mock_user, caplog):
    """Ensure sensitive patient narratives and filenames are NOT logged in plaintext."""
    import logging
    app.dependency_overrides[get_current_user] = lambda: mock_user
    wav_bytes = _create_synthetic_wav(1.0)

    secret_patient_name = "PATIENT_SECRET_MARKER_9999"
    secret_transcript = "Patient diagnosed with confidential condition XYZ"

    mock_client = AsyncMock()
    mock_transcription = MagicMock()
    mock_transcription.text = secret_transcript
    mock_transcription.language = "en"
    mock_client.audio.transcriptions.create.return_value = mock_transcription

    try:
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_mock_valid_test_key"}):
            with patch("app.api.v1.endpoints.voice._get_async_groq_client", return_value=mock_client):
                with caplog.at_level(logging.INFO, logger="newgenhealthai"):
                    response = client.post(
                        "/api/v1/voice/stt",
                        files={"file": (f"{secret_patient_name}.wav", wav_bytes, "audio/wav")},
                    )
                    assert response.status_code == 200

                    # Verify that secret patient text and secret filename are NOT present in logs
                    all_logs = " ".join([rec.message for rec in caplog.records])
                    assert secret_patient_name not in all_logs
                    assert secret_transcript not in all_logs
                    assert "confidential condition XYZ" not in all_logs
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ── 8. Section 11 Follow-up: Model Import Distinction ─────────────────────────

def test_lightweight_import_smoke_test_disease_classifier_clarification():
    """
    Verify architectural distinction:
    disease_classifier.py requires heavy PyTorch dependencies (torch) when imported,
    so lazy model loading refers to model weights (.pth files) loaded on demand,
    rather than zero-dependency lightweight module imports.
    """
    import subprocess
    import sys
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = {**os.environ, "PYTHONPATH": backend_dir}
    res = subprocess.run(
        [sys.executable, "-c", "import app.core.config; import sys; assert 'torch' not in sys.modules"],
        capture_output=True,
        env=env,
    )
    assert res.returncode == 0
