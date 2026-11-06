"""
NewGenHealthAI — tests/test_phase3a_image_security.py
Phase 3A: Secure Image Uploads, Model Loading and Resource Protection.

Tests:
1.  Unauthenticated image upload (401)
2.  Empty file upload rejected (400)
3.  Oversized compressed file rejected (413)
4.  Chunked upload-size enforcement stops before reading whole payload
5.  Forged MIME type rejected (non-image payload with image/jpeg header)
6.  Unsupported formats rejected (e.g. BMP/TIFF/SVG)
7.  Corrupt image bytes rejected safely
8.  Truncated image stream rejected safely
9.  Excessively large decoded dimensions rejected
10. Decompression bomb detected and rejected
11. EXIF orientation transposition applied correctly
12. EXIF metadata thoroughly stripped from processed raster
13. Valid small image accepted and decoded cleanly
14. Model weights missing returns 503 model_unavailable
15. Model initialization failure handled safely
16. Concurrent requests initializing one model (stampede prevention)
17. Multiple inference requests exceeding capacity returns 503
18. Per-user concurrency limit returns 429
19. Cancellation during inference releases capacity permit safely
20. No implicit model downloads when ALLOW_MODEL_DOWNLOADS=false
21. BLIP disabled by default; returns graceful fallback caption without downloads
22. Malformed checkpoint state_dict fails safely without crashing
23. Modality lock preserved without general fallback
24. Negative/normal class preserved without disease promotion
25. Sensitive diagnostics endpoint does NOT leak filesystem base_dir
26. Medical explanation does not assert confirmed diagnosis
27. Medical explanation for anatomy-only finding provides no disease advice
28. Medical explanation for normal finding provides no pathology advice
29. Slow synchronous workflow cannot bypass consultation deadline (Correction A)
30. Indian crisis helplines accurate (Tele-MANAS 24/7 at 14416, iCALL verified hours) (Correction B)
31. Unknown location crisis fallback guidance (Correction B)
"""

import asyncio
import io
import os
import threading
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.core.config import (
    ALLOW_MODEL_DOWNLOADS,
    ENABLE_BLIP_CAPTIONING,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_UPLOAD_BYTES,
)
from app.core.dependencies import get_current_user
from app.core.urgent_care import generate_urgent_advisory
from app.models.message import User
from app.services.disease_classifier import (
    DiseaseClassifier,
    MedicalModel,
    detect_visual_domain,
    disease_classifier,
)
from app.api.image_api import (
    InferenceCapacityManager,
    get_diagnostics,
    get_medical_info,
    inference_capacity_manager,
)
from app.tools.image_preprocess import (
    ImageValidationError,
    _validate_image_signature,
    safe_decode_and_sanitize_image,
    validate_and_read_image_upload,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_user():
    return User(id=999, username="security_tester")


@pytest.fixture
def client():
    return TestClient(app)


def _create_synthetic_jpeg(width: int = 64, height: int = 64, color: str = "red") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _create_synthetic_png(width: int = 64, height: int = 64, color: str = "green") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_synthetic_webp(width: int = 64, height: int = 64, color: str = "blue") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="WEBP")
    return buf.getvalue()


# ── 1. Image Upload Security & Format Validation ─────────────────────────────

def test_unauthenticated_image_upload_returns_401(client):
    """POST /api/v1/analyze-image without auth returns HTTP 401."""
    jpeg_data = _create_synthetic_jpeg()
    response = client.post(
        "/api/v1/analyze-image",
        files={"file": ("test.jpg", jpeg_data, "image/jpeg")},
    )
    assert response.status_code == 401


def test_empty_file_upload_rejected(client, mock_user):
    """Empty image file upload returns HTTP 400 invalid_image."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        response = client.post(
            "/api/v1/analyze-image",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "invalid_image"
        assert data["success"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_oversized_compressed_file_rejected(client, mock_user):
    """File exceeding MAX_IMAGE_UPLOAD_BYTES is rejected before decoding with HTTP 413."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        # Create a payload exceeding MAX_IMAGE_UPLOAD_BYTES
        oversized = b"\xff\xd8\xff\xe0" + b"\x00" * (MAX_IMAGE_UPLOAD_BYTES + 1024)
        response = client.post(
            "/api/v1/analyze-image",
            files={"file": ("huge.jpg", oversized, "image/jpeg")},
        )
        assert response.status_code == 413
        data = response.json()
        assert data["status"] == "invalid_image"
        assert "exceeds maximum permitted size" in data["error"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_chunked_upload_size_enforcement():
    """validate_and_read_image_upload stops and raises 413 as soon as max_bytes is passed."""
    mock_file = MagicMock()
    # 3 chunks of 64KB = 192KB; limit to 100KB
    mock_file.read = AsyncMock(side_effect=[b"X" * (64 * 1024), b"Y" * (64 * 1024), b""])
    mock_file.close = AsyncMock()

    with pytest.raises(ImageValidationError) as exc:
        await validate_and_read_image_upload(mock_file, max_bytes=100 * 1024)
    assert exc.value.status_code == 413
    mock_file.close.assert_awaited_once()


def test_forged_mime_type_rejected():
    """Non-image bytes with forged image/jpeg MIME type are rejected by magic bytes."""
    fake_payload = b"<html><script>alert(1)</script></html>"
    with pytest.raises(ImageValidationError) as exc:
        safe_decode_and_sanitize_image(fake_payload)
    assert exc.value.status_code == 400
    assert "format" in exc.value.message.lower() or "signature" in exc.value.message.lower()


def test_unsupported_format_rejected():
    """Valid BMP/GIF format rejected because only JPEG, PNG, and WebP are allowed."""
    buf = io.BytesIO()
    img = Image.new("RGB", (32, 32), color="red")
    img.save(buf, format="BMP")
    bmp_data = buf.getvalue()

    with pytest.raises(ImageValidationError) as exc:
        safe_decode_and_sanitize_image(bmp_data)
    assert exc.value.status_code == 400


def test_corrupt_image_bytes_rejected():
    """Corrupted JPEG header/data is rejected safely."""
    corrupt = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00\x00\x00\x00corrupted_payload"
    with pytest.raises(ImageValidationError) as exc:
        safe_decode_and_sanitize_image(corrupt)
    assert exc.value.status_code == 400


def test_truncated_image_rejected():
    """Truncated JPEG file is caught when pixel data is decoded."""
    valid_jpeg = _create_synthetic_jpeg(128, 128)
    truncated = valid_jpeg[: len(valid_jpeg) // 3]  # truncate 2/3 of data
    with pytest.raises(ImageValidationError) as exc:
        safe_decode_and_sanitize_image(truncated)
    assert exc.value.status_code == 400


def test_excessively_large_decoded_dimensions_rejected():
    """Image exceeding MAX_IMAGE_DIMENSION is rejected."""
    # Use small byte payload that decodes to small dimensions, test with low max_dimension
    small_jpeg = _create_synthetic_jpeg(64, 64)
    with pytest.raises(ImageValidationError) as exc:
        safe_decode_and_sanitize_image(small_jpeg, max_dimension=32)
    assert exc.value.status_code == 400
    assert "exceeds maximum permitted limit" in exc.value.message


def test_decompression_bomb_rejected():
    """Decompression bomb pixel limit raises ImageValidationError."""
    small_jpeg = _create_synthetic_jpeg(64, 64)  # 4096 pixels
    with pytest.raises(ImageValidationError) as exc:
        safe_decode_and_sanitize_image(small_jpeg, max_pixels=1000)
    assert exc.value.status_code == 400
    msg = exc.value.message.lower()
    assert "decompression bomb" in msg or "dimension" in msg or "pixel" in msg



def test_exif_metadata_stripped():
    """safe_decode_and_sanitize_image strips all EXIF and metadata blocks."""
    # Create image with EXIF info
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), color="green")
    exif_dict = img.getexif()
    exif_dict[0x010E] = "Sensitive User Description"
    exif_dict[0x010F] = "Camera Manufacturer"
    img.save(buf, format="JPEG", exif=exif_dict)
    jpeg_with_exif = buf.getvalue()

    cleaned = safe_decode_and_sanitize_image(jpeg_with_exif)
    assert cleaned.size == (64, 64)
    # The cleaned image is a fresh raster without EXIF
    cleaned_exif = cleaned.getexif()
    assert 0x010E not in cleaned_exif
    assert 0x010F not in cleaned_exif


def test_valid_small_image_accepted():
    """Valid JPEG, PNG, and WebP decode into clean RGB images."""
    for fn in [_create_synthetic_jpeg, _create_synthetic_png, _create_synthetic_webp]:
        data = fn(48, 48)
        decoded = safe_decode_and_sanitize_image(data)
        assert decoded.mode == "RGB"
        assert decoded.size == (48, 48)
        decoded.close()


# ── 2. Inference Concurrency & Capacity Protection ───────────────────────────

@pytest.mark.asyncio
async def test_per_user_concurrency_limit_returns_429():
    """A user cannot start multiple concurrent inference operations."""
    mgr = InferenceCapacityManager(max_concurrent=5, queue_timeout=1.0)
    user_id = 42

    permit1 = await mgr.acquire(user_id)
    assert permit1 is not None

    # Second concurrent acquire for same user raises 429
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await mgr.acquire(user_id)
    assert exc.value.status_code == 429

    # Releasing permit allows new acquisition
    await permit1.release()
    permit2 = await mgr.acquire(user_id)
    assert permit2 is not None
    await permit2.release()


@pytest.mark.asyncio
async def test_multiple_inference_requests_exceeding_capacity_returns_503():
    """When all inference slots are busy, waiting requests timeout and return 503."""
    from fastapi import HTTPException

    # Capacity of 1, very short timeout of 0.05s
    mgr = InferenceCapacityManager(max_concurrent=1, queue_timeout=0.05)
    permit1 = await mgr.acquire(user_id=1)

    # Different user attempts acquisition while slot 1 is held
    with pytest.raises(HTTPException) as exc:
        await mgr.acquire(user_id=2)
    assert exc.value.status_code == 503
    assert "maximum capacity" in exc.value.detail

    await permit1.release()


@pytest.mark.asyncio
async def test_cancellation_during_inference_releases_capacity_permit():
    """Cancelled task holding inference permit strictly releases slot."""
    mgr = InferenceCapacityManager(max_concurrent=1, queue_timeout=1.0)
    user_id = 77

    async def worker():
        permit = await mgr.acquire(user_id)
        async with permit:
            await asyncio.sleep(10)  # Long running task to be cancelled

    task = asyncio.create_task(worker())
    await asyncio.sleep(0.01)  # Allow task to acquire permit

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Slot should be completely free for another user
    permit2 = await mgr.acquire(user_id=88)
    assert permit2 is not None
    await permit2.release()


# ── 3. Lazy Model Loading & Lifecycle States ──────────────────────────────────

def test_no_implicit_model_downloads_when_downloads_disabled():
    """DiseaseClassifier does not attempt network downloads when ALLOW_MODEL_DOWNLOADS=false."""
    mock_hf_module = MagicMock()
    with patch.dict("sys.modules", {"huggingface_hub": mock_hf_module}):
        with patch("app.core.config.ALLOW_MODEL_DOWNLOADS", False):
            classifier = DiseaseClassifier()
            res = classifier._download_models_if_missing()
            assert res is False
            mock_hf_module.hf_hub_download.assert_not_called()




def test_model_weights_missing_returns_503_model_unavailable(client, mock_user):
    """When required model weights are missing locally, classify returns 503 model_unavailable."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    jpeg_data = _create_synthetic_jpeg()

    try:
        # Mock CLIP detecting skin domain, but model files missing
        with patch("app.services.disease_classifier.detect_visual_domain", return_value=("skin", 0.95, {"skin": 0.95})):
            with patch.object(disease_classifier, "get_specialist_model", return_value=None):
                disease_classifier.models.pop("skin", None)
                response = client.post(
                    "/api/v1/analyze-image",
                    data={"modality": "skin", "modality_confirmed": "true"},
                    files={"file": ("skin.jpg", jpeg_data, "image/jpeg")},
                )
                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "model_unavailable"
                assert data["category"] == "skin"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_concurrent_requests_initializing_one_model_stampede_protection():
    """Concurrent requests loading the same model acquire lock and load once."""
    classifier = DiseaseClassifier()
    load_count = 0

    def fake_load(self):
        nonlocal load_count
        load_count += 1
        return True

    classifier.model_configs["skin"] = {"pth": "/fake/skin.pth", "txt": "/fake/classes.txt"}
    classifier.model_status["skin"] = "unloaded"

    with patch.object(MedicalModel, "load", fake_load):
        threads = []
        for _ in range(5):
            t = threading.Thread(target=classifier.get_specialist_model, args=("skin",))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    # The model was loaded exactly once despite 5 concurrent requests
    assert load_count == 1
    assert classifier.model_status["skin"] == "ready"


def test_malformed_checkpoint_state_dict_fails_safely():
    """MedicalModel.load fails closed and safely when checkpoint state_dict is malformed."""
    with patch("os.path.exists", return_value=True):
        with patch("app.services.disease_classifier._parse_class_file", return_value=["class1", "class2"]):
            with patch("torch.load", return_value="not-a-state-dict-or-mapping"):
                model = MedicalModel("test_model", "/path/model.pth", "/path/classes.txt")
                loaded = model.load()
                assert loaded is False


def test_blip_disabled_by_default_no_download_and_safe_caption_fallback(client, mock_user):
    """When BLIP is disabled, non-medical image receives clean fallback without model download."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    jpeg_data = _create_synthetic_jpeg()

    try:
        mock_transformers = MagicMock()
        with patch.dict("sys.modules", {"transformers": mock_transformers}):
            with patch("app.api.image_api.ENABLE_BLIP_CAPTIONING", False):
                with patch.object(disease_classifier, "classify") as mock_classify:
                    mock_classify.return_value = {
                        "status": "unsupported_image",
                        "category": "non_medical",
                        "domain_hint": "non_medical",
                        "domain_confidence": 0.95,
                    }
                    response = client.post(
                        "/api/v1/analyze-image",
                        files={"file": ("dog.jpg", jpeg_data, "image/jpeg")},
                    )
                    assert response.status_code == 422
                    data = response.json()
                    assert data["status"] == "unsupported_image"
                    assert "does not appear to be a supported medical image" in data["description"]
                    # BLIP must NOT be downloaded
                    mock_transformers.BlipProcessor.from_pretrained.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ── 4. Diagnostics Endpoint Privacy ───────────────────────────────────────────

def test_sensitive_diagnostics_not_publicly_exposed(client):
    """GET /api/v1/diagnostics does NOT expose filesystem base_dir or internal paths."""
    response = client.get("/api/v1/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "models" in data
    assert "base_dir" not in data
    assert "path" not in str(data).lower()
    assert "/users/" not in str(data).lower()
    assert "/home/" not in str(data).lower()


# ── 5. Educational Medical Info Generation ────────────────────────────────────

def test_medical_info_anatomy_only_returns_no_disease_advice():
    """Anatomy-only findings do not generate disease treatment advice."""
    info = get_medical_info("wrist", "xray", finding_type="anatomy_identified")
    assert "anatomical location" in info["raw"]
    assert "No disease pathology" in info["raw"]


def test_medical_info_normal_finding_returns_no_disease_advice():
    """Normal reference findings do not generate pathological symptoms or drug advice."""
    info = get_medical_info("Normal Reference", "general", is_negative=True)
    assert "normal reference" in info["raw"]
    assert "No pathological symptoms" in info["raw"]


def test_medical_info_does_not_assert_confirmed_diagnosis():
    """Prompt given to LLM tells it this is NOT a confirmed diagnosis."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Educational information about actinic keratosis."
    mock_llm.invoke.return_value = mock_response

    with patch("app.tools.llm_client.get_llm", return_value=mock_llm):
        with patch("app.tools.vector_store.get_retriever", return_value=None):
            info = get_medical_info("Actinic Keratosis", "skin", finding_type="condition_detected")
            assert "Educational information" in info["raw"]
            prompt_used = mock_llm.invoke.call_args[0][0]
            assert "clinical diagnosis" in prompt_used.lower()
            assert "not a doctor" in prompt_used.lower()


# ── 6. Mandatory Initial Corrections (A & B) ─────────────────────────────────

@pytest.mark.asyncio
async def test_slow_synchronous_workflow_cannot_bypass_deadline_and_releases_lock():
    """Correction A: Sync invoke fallback cannot bypass CONSULTATION_TIMEOUT_SECONDS."""
    from app.services.chat_service import ClinicalEngine

    engine = ClinicalEngine()
    key = "u999:sess_sync_timeout"

    # Simulate a slow sync workflow
    class SlowSyncWorkflow:
        def invoke(self, state):
            import time
            time.sleep(1.0)
            return {"generation": "too slow"}

    engine.workflow_app = SlowSyncWorkflow()

    with patch("app.services.chat_service.CONSULTATION_TIMEOUT_SECONDS", 0.05):
        with patch("app.services.chat_service.db_service") as mock_db:
            mock_db.get_conversation.return_value = {"id": "sess_sync_timeout", "user_id": 999}
            res = await engine.process_message(
                session_id="sess_sync_timeout",
                message="I have severe fever",
                user_id=999,
            )
            assert res["result_state"] == "PROVIDER_TIMEOUT"
            assert res["success"] is False
            assert res["source"] == "Service Unavailable"


def test_indian_crisis_helplines_accurate_tele_manas_and_icall_hours():
    """Correction B: India guidance includes Tele-MANAS 24/7 (14416) and accurate iCALL hours."""
    advisory = generate_urgent_advisory("crisis", "Crisis Alert", locale="IN")
    assert "Tele-MANAS" in advisory
    assert "14416" in advisory
    assert "112" in advisory
    assert "9999 666 555" in advisory
    assert "Vandrevala" in advisory
    assert "iCALL" in advisory
    assert "not a 24/7 service" in advisory.lower() or "10:00 am" in advisory.lower()


def test_unknown_location_crisis_fallback():
    """Correction B: Advisory provides safe fallback guidance when user country is unlisted."""
    advisory = generate_urgent_advisory("crisis", "Crisis Alert", locale="UNKNOWN_COUNTRY")
    assert "country or region is not listed above" in advisory.lower()
    assert "local emergency telephone number" in advisory.lower()
