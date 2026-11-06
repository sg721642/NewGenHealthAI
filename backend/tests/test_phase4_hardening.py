"""
NewGenHealthAI — tests/test_phase4_hardening.py
Automated regression tests for Phase 4:
1. Cancellation-safe VoiceCapacityManager (STT & TTS)
2. TTS streaming resource bounding (timeout & max bytes)
3. STT retry classification (permanent vs transient)
4. Canonical Vite entrypoint & standalone build configuration
5. Root launcher path and process management
6. Backend import smoke test and health endpoint
"""

import os
import sys
import struct
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

def _create_synthetic_wav(duration_sec: float = 1.0, sample_rate: int = 8000, num_channels: int = 1) -> bytes:
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
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        16,
        b"data",
        data_size,
    )
    samples = b"\x00\x00" * num_samples
    return header + samples

from app.main import app
from app.core.dependencies import get_current_user
from app.models.message import User
from app.tools.voice_capacity import VoiceCapacityManager, VoicePermit, voice_capacity_manager
from app.core.config import (
    MAX_TTS_STREAM_BYTES,
    TTS_STREAM_TIMEOUT_SECONDS,
    TTS_REQUEST_TIMEOUT_SECONDS,
)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
import run


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user():
    user = User(id=42, username="test_patient", hashed_password="argon2id$mock_hashed_password")
    return user


# ─────────────────────────────────────────────────────────────────────────────
# 1. VoiceCapacityManager Cancellation & Concurrency Safety
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancelled_stt_acquisition_cleans_up_active_user():
    """When task awaiting STT semaphore is cancelled, active user reservation is cleanly discarded."""
    manager = VoiceCapacityManager(max_concurrent_stt=1, queue_timeout=10.0)

    # User 1 acquires the only slot
    permit1 = await manager.acquire_stt(user_id=1)
    assert 1 in manager._active_stt_users
    assert manager.stt_semaphore.locked()

    started_event = asyncio.Event()

    async def user2_request():
        started_event.set()
        await manager.acquire_stt(user_id=2)

    task2 = asyncio.create_task(user2_request())
    await started_event.wait()
    # Give event loop a cycle to ensure task2 is waiting inside acquire_stt
    await asyncio.sleep(0.01)

    assert 2 in manager._active_stt_users

    # Cancel User 2 while waiting
    task2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task2

    # User 2 must be purged from active reservations
    assert 2 not in manager._active_stt_users
    # Semaphore must still be held by User 1
    assert manager.stt_semaphore.locked()

    # User 1 releases
    await permit1.release()
    assert 1 not in manager._active_stt_users
    assert not manager.stt_semaphore.locked()

    # User 2 can now acquire without HTTP 429 concurrency violation
    permit2 = await manager.acquire_stt(user_id=2)
    assert 2 in manager._active_stt_users
    await permit2.release()
    assert 2 not in manager._active_stt_users


@pytest.mark.asyncio
async def test_cancelled_tts_acquisition_cleans_up_active_user():
    """When task awaiting TTS semaphore is cancelled, active user reservation is cleanly discarded."""
    manager = VoiceCapacityManager(max_concurrent_tts=1, queue_timeout=10.0)

    permit1 = await manager.acquire_tts(user_id=10)
    assert 10 in manager._active_tts_users
    assert manager.tts_semaphore.locked()

    started_event = asyncio.Event()

    async def user20_request():
        started_event.set()
        await manager.acquire_tts(user_id=20)

    task20 = asyncio.create_task(user20_request())
    await started_event.wait()
    await asyncio.sleep(0.01)

    assert 20 in manager._active_tts_users

    task20.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task20

    assert 20 not in manager._active_tts_users
    assert manager.tts_semaphore.locked()

    await permit1.release()
    assert 10 not in manager._active_tts_users

    permit20 = await manager.acquire_tts(user_id=20)
    assert 20 in manager._active_tts_users
    await permit20.release()
    assert 20 not in manager._active_tts_users


@pytest.mark.asyncio
async def test_permit_release_is_idempotent():
    """Calling permit.release() multiple times releases semaphore only once."""
    manager = VoiceCapacityManager(max_concurrent_stt=2)
    permit = await manager.acquire_stt(user_id=99)
    assert 99 in manager._active_stt_users

    await permit.release()
    assert 99 not in manager._active_stt_users

    # Second release should be a no-op
    await permit.release()
    assert 99 not in manager._active_stt_users
    # Acquire both slots to verify semaphore count is exactly 2, not incremented to 3
    p1 = await manager.acquire_stt(user_id=101)
    p2 = await manager.acquire_stt(user_id=102)
    assert manager.stt_semaphore.locked()
    await p1.release()
    await p2.release()


@pytest.mark.asyncio
async def test_simultaneous_requests_same_user_rejected_with_429():
    """User cannot execute multiple concurrent requests in the same service category."""
    manager = VoiceCapacityManager(max_concurrent_stt=5)
    permit1 = await manager.acquire_stt(user_id=500)

    with pytest.raises(HTTPException) as exc_info:
        await manager.acquire_stt(user_id=500)
    assert exc_info.value.status_code == 429

    await permit1.release()
    assert 500 not in manager._active_stt_users


# ─────────────────────────────────────────────────────────────────────────────
# 2. TTS Streaming Resource Bounds
# ─────────────────────────────────────────────────────────────────────────────

def test_tts_oversized_stream_terminates_cleanly(client, mock_user):
    """TTS stream yielding excessive bytes terminates at MAX_TTS_STREAM_BYTES and releases permit."""
    app.dependency_overrides[get_current_user] = lambda: mock_user

    chunk_size = 64 * 1024  # 64KB chunks
    total_chunks_to_generate = 200  # 12.8 MB total, exceeding 5MB limit

    async def fake_stream():
        for _ in range(total_chunks_to_generate):
            yield {"type": "audio", "data": b"X" * chunk_size}

    mock_comm = MagicMock()
    mock_comm.stream = fake_stream

    with patch("app.api.v1.endpoints.voice.edge_tts.Communicate", return_value=mock_comm):
        with patch("app.api.v1.endpoints.voice.MAX_TTS_STREAM_BYTES", 256 * 1024):  # 256 KB test limit
            response = client.post(
                "/api/v1/voice/tts",
                json={"text": "This is an educational text to synthesize into speech."},
            )
            assert response.status_code == 200
            audio_content = response.content
            # Total received bytes must be bounded and not reach the full 12.8 MB
            assert len(audio_content) <= (256 * 1024) + chunk_size
            assert len(audio_content) > 0

    # Permit must be cleanly released
    assert mock_user.id not in voice_capacity_manager._active_tts_users
    app.dependency_overrides.clear()


def test_tts_stream_timeout_bounds_execution(client, mock_user):
    """TTS stream that exceeds deadline breaks cleanly without hanging."""
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def fake_slow_stream():
        # First chunk ok
        yield {"type": "audio", "data": b"START_AUDIO"}
        # Simulate delay that triggers timeout
        await asyncio.sleep(0.5)
        yield {"type": "audio", "data": b"LATE_AUDIO"}

    mock_comm = MagicMock()
    mock_comm.stream = fake_slow_stream

    with patch("app.api.v1.endpoints.voice.edge_tts.Communicate", return_value=mock_comm):
        with patch("app.api.v1.endpoints.voice.TTS_STREAM_TIMEOUT_SECONDS", 0.1):  # 100ms deadline
            with patch("app.api.v1.endpoints.voice.TTS_REQUEST_TIMEOUT_SECONDS", 0.1):
                response = client.post(
                    "/api/v1/voice/tts",
                    json={"text": "Testing stream timeout deadline."},
                )
                assert response.status_code == 200
                content = response.content
                assert b"START_AUDIO" in content
                assert b"LATE_AUDIO" not in content

    assert mock_user.id not in voice_capacity_manager._active_tts_users
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# 3. STT Permanent vs Transient Error Classification
# ─────────────────────────────────────────────────────────────────────────────

def test_stt_permanent_error_fails_immediately_without_fallback(client, mock_user):
    """Permanent error (e.g. 400 Bad Request) on primary model fails immediately without retry."""
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_client = AsyncMock()
    # Permanent error with status 400
    class MockBadRequest(Exception):
        status_code = 400

    mock_client.audio.transcriptions.create.side_effect = MockBadRequest("Invalid audio parameters")

    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_valid_key"}):
        with patch("app.api.v1.endpoints.voice._get_async_groq_client", return_value=mock_client):
            response = client.post(
                "/api/v1/voice/stt",
                files={"file": ("test.wav", _create_synthetic_wav(1.0), "audio/wav")},
            )
            assert response.status_code == 503
            # Assert primary model was called only once and secondary fallback model was NEVER attempted
            assert mock_client.audio.transcriptions.create.call_count == 1
            call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
            assert call_kwargs["model"] == "whisper-large-v3-turbo"

    app.dependency_overrides.clear()


def test_stt_transient_error_retries_with_fallback(client, mock_user):
    """Transient error (e.g. 429 Too Many Requests) retries with secondary model."""
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_client = AsyncMock()
    mock_success = MagicMock()
    mock_success.text = "Recovered from transient error"
    mock_success.language = "en"

    class MockRateLimit(Exception):
        status_code = 429

    mock_client.audio.transcriptions.create.side_effect = [
        MockRateLimit("Rate limit reached"),
        mock_success,
    ]

    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_valid_key"}):
        with patch("app.api.v1.endpoints.voice._get_async_groq_client", return_value=mock_client):
            response = client.post(
                "/api/v1/voice/stt",
                files={"file": ("test.wav", _create_synthetic_wav(1.0), "audio/wav")},
            )
            assert response.status_code == 200
            assert response.json()["text"] == "Recovered from transient error"
            assert mock_client.audio.transcriptions.create.call_count == 2
            first_call = mock_client.audio.transcriptions.create.call_args_list[0].kwargs
            second_call = mock_client.audio.transcriptions.create.call_args_list[1].kwargs
            assert first_call["model"] == "whisper-large-v3-turbo"
            assert second_call["model"] == "whisper-large-v3"

    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Canonical Frontend Entrypoint & Vite Build Configuration
# ─────────────────────────────────────────────────────────────────────────────

def test_canonical_frontend_entry_html():
    """Verifies frontend/index.html has NewGenHealthAI title, favicon.svg, and no duplicate public/index.html."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    index_html_path = os.path.join(base_dir, "frontend", "index.html")
    public_index_path = os.path.join(base_dir, "frontend", "public", "index.html")

    # 1. Stale duplicate in public/ must NOT exist
    assert not os.path.exists(public_index_path), "frontend/public/index.html must be removed"

    # 2. Canonical index.html must exist and contain proper title & elements
    assert os.path.exists(index_html_path), "frontend/index.html must exist"
    with open(index_html_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "<title>NewGenHealthAI</title>" in content
    assert "favicon.svg" in content
    assert "<div id=\"root\"></div>" in content
    assert "/src/index.jsx" in content
    assert "MediGenius" not in content


def test_favicon_ico_route_serving():
    """Verifies that /favicon.ico is served cleanly (HTTP 200 SVG or 204) rather than 404."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/favicon.ico")
    assert resp.status_code in (200, 204)
    if resp.status_code == 200:
        assert "image/svg+xml" in resp.headers.get("content-type", "")


def test_vite_standalone_build_output_config():
    """Verifies vite.config.js and package.json support standalone build mode."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    vite_config_path = os.path.join(base_dir, "frontend", "vite.config.js")
    pkg_json_path = os.path.join(base_dir, "frontend", "package.json")
    dockerfile_path = os.path.join(base_dir, "frontend", "Dockerfile")

    with open(vite_config_path, "r", encoding="utf-8") as f:
        vite_cfg = f.read()
    assert "mode === 'standalone' ? 'dist' : '../backend/app/static'" in vite_cfg

    with open(pkg_json_path, "r", encoding="utf-8") as f:
        pkg_json = f.read()
    assert "build:standalone" in pkg_json

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        dockerfile = f.read()
    assert "npm run build:standalone" in dockerfile
    assert "COPY --from=build /app/dist /usr/share/nginx/html" in dockerfile


# ─────────────────────────────────────────────────────────────────────────────
# 5. Root Launcher Verification
# ─────────────────────────────────────────────────────────────────────────────

def test_launcher_path_and_executable_resolution():
    """Verifies launcher resolves paths relative to __file__ and resolves python and npm executables."""
    py_exe = run.get_python_executable()
    assert os.path.exists(py_exe) or py_exe == sys.executable

    npm_exe = run.get_npm_executable()
    assert npm_exe is not None
    assert isinstance(npm_exe, str)


def test_launcher_wait_for_backend_timeout():
    """wait_for_backend returns False if server does not respond within max_retries."""
    # Test against unreachable port with small max_retries
    res = run.wait_for_backend(url="http://127.0.0.1:59999/api/v1/health", max_retries=2, delay=0.01)
    assert res is False


def test_launcher_terminate_process():
    """terminate_process handles active and terminated processes gracefully."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    run.terminate_process(mock_proc)
    assert mock_proc.terminate.called or mock_proc.send_signal.called


# ─────────────────────────────────────────────────────────────────────────────
# 6. Backend Smoke & Health Endpoint
# ─────────────────────────────────────────────────────────────────────────────

def test_backend_health_check_public(client):
    """GET /api/v1/health returns HTTP 200 with service health info."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "healthy"
    assert "NewGenHealthAI" in data.get("service", "")


def test_env_example_contains_all_critical_keys():
    """Verifies .env.example documents all essential security, timeout, and resource limits."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_example_path = os.path.join(base_dir, ".env.example")
    with open(env_example_path, "r", encoding="utf-8") as f:
        content = f.read()

    critical_keys = [
        "SESSION_SECRET_KEY",
        "GROQ_API_KEY",
        "TAVILY_API_KEY",
        "CONSULTATION_TIMEOUT_SECONDS",
        "MAX_IMAGE_UPLOAD_BYTES",
        "MAX_AUDIO_UPLOAD_BYTES",
        "MAX_CONCURRENT_INFERENCE",
        "MAX_CONCURRENT_STT",
        "MAX_CONCURRENT_TTS",
        "VOICE_QUEUE_TIMEOUT_SECONDS",
        "TTS_STREAM_TIMEOUT_SECONDS",
        "MAX_TTS_STREAM_BYTES",
        "ALLOW_MODEL_DOWNLOADS",
    ]
    for key in critical_keys:
        assert key in content, f"Missing {key} in .env.example"
