"""
Tests for Phase 2A: Critical Image-Classification Correctness, Negative Class Handling,
Hard Modality Locking, and Explicit API Response Contracts.

Covers the full 20-scenario offline regression test matrix:
 1. Normal vs Condition (normal=0.96 vs pneumonia=0.04) -> normal preserved, no pneumonia diagnosis.
 2. Valid negative classes preservation (normal, notumor, notinfected, uninfected, non-covid, benign, healthy eye).
 3. Invalid dataset artifact top prediction -> status="inconclusive", no disease promotion.
 4. X-ray anatomy-only -> finding_type="anatomy_identified", no fracture/abnormality diagnosed.
 5. X-ray mixed anatomy and condition -> proper prioritization without disease fabrication.
 6. Hard modality lock: skin specialist missing -> status="model_unavailable", HTTP 503, no fallback to general.
 7. Hard modality lock: xray specialist missing -> status="model_unavailable", HTTP 503.
 8. Hard modality lock: retina specialist missing -> status="model_unavailable", HTTP 503.
 9. Hard modality lock: general model missing -> status="model_unavailable", HTTP 503.
10. All models missing -> status="model_unavailable", HTTP 503.
11. CLIP failure / exception -> status="inconclusive", no fallback to general.
12. Ambiguous CLIP domain -> status="inconclusive".
13. Non-medical image -> status="unsupported_image", HTTP 422.
14. Model exception during inference -> status="inconclusive", no cross-modality fallback.
15. Empty predictions from model -> status="inconclusive".
16. Low-ranked disease not promoted when normal or negative class is top rank.
17. Score interpretation present: raw score returned, calibrated_confidence is None.
18. Image API endpoint: HTTP 400 on invalid or corrupted image bytes.
19. Image API endpoint: HTTP 422 on unsupported non-medical image.
20. Image API endpoint: HTTP 503 on model unavailable and HTTP 200 on analysis_complete / inconclusive.
"""

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.dependencies import get_current_user
from app.main import app
from app.models.message import User
from app.services.disease_classifier import (
    DATASET_ARTIFACT_CLASSES,
    VALID_NEGATIVE_CLASSES,
    DiseaseClassifier,
    detect_visual_domain,
    disease_classifier,
)


@pytest.fixture
def dummy_image():
    """Create a minimal valid RGB test image in memory."""
    img = Image.new("RGB", (64, 64), color=(200, 200, 200))
    return img


@pytest.fixture
def dummy_image_bytes(dummy_image):
    """Create JPEG bytes for a minimal valid image."""
    buf = io.BytesIO()
    dummy_image.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def mock_auth_user():
    """Mock user fixture to satisfy get_current_user dependency."""
    user = User(id=1, username="test_clinician", hashed_password="mock_argon2_hash")
    setattr(user, "user_id", 1)
    return user


# ==============================================================================
# SCENARIOS 1 & 16: NORMAL PRESERVATION & SUPPRESSION OF DISEASE PROMOTION
# ==============================================================================

def test_scenario_01_normal_preserved_no_disease_promotion():
    """
    Scenario 1 & 16:
    When model outputs normal=0.96 and pneumonia=0.04:
    - Normal finding MUST be preserved as the top finding.
    - Pneumonia MUST NOT be promoted as a primary condition.
    - finding_type must be 'normal_or_negative'.
    - is_negative_finding must be True.
    - Score is preserved (0.96), calibrated_confidence is None.
    """
    classifier = DiseaseClassifier()
    predictions = [
        {"disease": "normal", "confidence": 0.9600},
        {"disease": "pneumonia", "confidence": 0.0400},
    ]

    result = classifier._interpret_predictions("general", predictions, 0.9600)

    assert result["status"] == "analysis_complete"
    assert result["finding_type"] == "normal_or_negative"
    assert result["is_negative_finding"] is True
    assert "Normal" in result["disease"]
    assert result["score"] == 0.9600
    assert "clinical_note" in result
    assert "does not establish medical health" in result["clinical_note"]

    # Verify pneumonia is in differential predictions list but NOT primary disease
    assert result["disease"] != "Pneumonia"
    assert any(p["disease"] == "Pneumonia" for p in result["predictions"])


# ==============================================================================
# SCENARIO 2: ALL VALID NEGATIVE CLASSES PRESERVED
# ==============================================================================

@pytest.mark.parametrize("neg_class", list(VALID_NEGATIVE_CLASSES))
def test_scenario_02_valid_negative_classes_preserved(neg_class):
    """
    Scenario 2:
    Every valid negative class in VALID_NEGATIVE_CLASSES must be recognized as
    normal_or_negative with is_negative_finding=True and never treated as an artifact.
    """
    classifier = DiseaseClassifier()
    predictions = [
        {"disease": neg_class, "confidence": 0.8800},
        {"disease": "some_other_pathology", "confidence": 0.1200},
    ]

    result = classifier._interpret_predictions("general", predictions, 0.8800)

    assert result["status"] == "analysis_complete"
    assert result["finding_type"] == "normal_or_negative"
    assert result["is_negative_finding"] is True
    assert result["score"] == 0.8800
    assert result["raw_prediction"] == neg_class


# ==============================================================================
# SCENARIO 3: TOP ARTIFACT CLASS TRIGGERS INCONCLUSIVE (NO PROMOTION)
# ==============================================================================

@pytest.mark.parametrize("artifact_class", ["preview", "train", "val", "cropped", "jpegimages", "all"])
def test_scenario_03_top_artifact_triggers_inconclusive(artifact_class):
    """
    Scenario 3:
    When highest-ranked class is a dataset artifact (e.g. 'preview', 'train'):
    - Result MUST be status='inconclusive'.
    - reason must be 'top_prediction_is_artifact'.
    - Lower-ranked condition MUST NOT be promoted to primary diagnosis.
    """
    classifier = DiseaseClassifier()
    predictions = [
        {"disease": artifact_class, "confidence": 0.9100},
        {"disease": "melanoma", "confidence": 0.0900},
    ]

    result = classifier._interpret_predictions("skin", predictions, 0.9100)

    assert result["status"] == "inconclusive"
    assert result["reason"] == "top_prediction_is_artifact"
    assert result["disease"] is None
    assert result["score"] == 0.0


# ==============================================================================
# SCENARIOS 4 & 5: X-RAY ANATOMY VS MEDICAL CONDITIONS
# ==============================================================================

def test_scenario_04_xray_anatomy_only_wrist():
    """
    Scenario 4:
    When X-ray top prediction is wrist=0.95 and no condition is present:
    - finding_type MUST be 'anatomy_identified'.
    - disease MUST be 'Wrist (Anatomical Region Only)'.
    - MUST NOT diagnose fracture or manufacture 'Abnormality Detected'.
    """
    classifier = DiseaseClassifier()
    predictions = [
        {"disease": "wrist", "confidence": 0.9500},
        {"disease": "forearm", "confidence": 0.0300},
        {"disease": "hand", "confidence": 0.0200},
    ]

    result = classifier._interpret_xray_predictions(predictions, 0.9500)

    assert result["status"] == "analysis_complete"
    assert result["finding_type"] == "anatomy_identified"
    assert result["is_negative_finding"] is False
    assert result["disease"] == "Anatomy Identified: Wrist (No pathology classified)"
    assert result["anatomical_region"] == "Wrist"
    assert "cannot determine the presence or absence of an abnormality" in result["clinical_note"]


def test_scenario_05_xray_condition_top_with_secondary_anatomy():
    """
    Scenario 5A:
    When fracture is top rank (0.75) and wrist is secondary (0.25):
    - finding_type is 'condition_detected'.
    - disease is 'Wrist Fracture'.
    - anatomical_region is 'Wrist'.
    """
    classifier = DiseaseClassifier()
    predictions = [
        {"disease": "fracture", "confidence": 0.7500},
        {"disease": "wrist", "confidence": 0.2500},
    ]

    result = classifier._interpret_xray_predictions(predictions, 0.7500)

    assert result["status"] == "analysis_complete"
    assert result["finding_type"] == "condition_detected"
    assert result["disease"] in ("Wrist Fracture", "Bone Fracture")
    assert result["anatomical_region"] == "Wrist"


def test_scenario_05_xray_anatomy_top_with_subthreshold_condition():
    """
    Scenario 5B:
    When anatomy is top rank (wrist=0.85) and condition is lower (fracture=0.15):
    - Wrist anatomy remains the primary finding ('anatomy_identified').
    - Fracture is NOT promoted to primary disease.
    """
    classifier = DiseaseClassifier()
    predictions = [
        {"disease": "wrist", "confidence": 0.8500},
        {"disease": "fracture", "confidence": 0.1500},
    ]

    result = classifier._interpret_xray_predictions(predictions, 0.8500)

    assert result["status"] == "analysis_complete"
    assert result["finding_type"] == "anatomy_identified"
    assert result["disease"] == "Anatomy Identified: Wrist (No pathology classified)"
    assert any("Fracture" in p["disease"] for p in result["predictions"])


# ==============================================================================
# SCENARIOS 6, 7, 8, 9, 10: HARD MODALITY LOCKING & MODEL UNAVAILABLE
# ==============================================================================

@pytest.mark.parametrize("modality", ["skin", "xray", "retina", "general"])
def test_scenarios_06_to_09_hard_modality_lock_missing_model(dummy_image, modality):
    """
    Scenarios 6-9:
    When CLIP routes to a specialist modality ('skin', 'xray', 'retina', 'general')
    and that specific specialist model is not loaded in classifier.models:
    - MUST return status='model_unavailable'.
    - MUST NOT fall back to 'general' or run other models.
    """
    classifier = DiseaseClassifier()
    classifier.models = {}  # No models loaded

    with patch("app.services.disease_classifier.detect_visual_domain", return_value=(modality, 0.85, {modality: 0.85})):
        result = classifier.classify(dummy_image)

    assert result["status"] == "model_unavailable"
    assert result["category"] == modality
    assert f"Specialist AI model for '{modality}' is not loaded" in result["message"]
    assert result["disease"] is None


def test_scenario_10_all_models_missing(dummy_image):
    """
    Scenario 10:
    When all models are missing, classifier safely returns status='model_unavailable'
    without unhandled crashes.
    """
    classifier = DiseaseClassifier()
    classifier.models = {}

    with patch("app.services.disease_classifier.detect_visual_domain", return_value=("xray", 0.90, {"xray": 0.90})):
        result = classifier.classify(dummy_image)

    assert result["status"] == "model_unavailable"
    assert result["category"] == "xray"


# ==============================================================================
# SCENARIOS 11 & 12: CLIP FAILURE & AMBIGUOUS DOMAINS
# ==============================================================================

def test_scenario_11_clip_exception_fails_inconclusive(dummy_image):
    """
    Scenario 11:
    When CLIP domain detection raises an exception:
    - detect_visual_domain returns ('unknown', 0.0, {}).
    - classify() returns status='inconclusive'.
    - MUST NOT fall back to 'general' or run any specialist models.
    """
    with patch("app.services.disease_classifier._get_clip", side_effect=RuntimeError("CLIP CUDA OOM")):
        domain, conf, scores = detect_visual_domain(dummy_image)
        assert domain == "unknown"
        assert conf == 0.0

    classifier = DiseaseClassifier()
    with patch("app.services.disease_classifier.detect_visual_domain", return_value=("unknown", 0.0, {})):
        result = classifier.classify(dummy_image)

    assert result["status"] == "inconclusive"
    assert "could not be reliably determined" in result["message"]


def test_scenario_12_ambiguous_clip_domain(dummy_image):
    """
    Scenario 12:
    When CLIP domain confidence is ambiguous:
    - classify() returns status='inconclusive'.
    - No specialist model is invoked.
    """
    classifier = DiseaseClassifier()
    with patch("app.services.disease_classifier.detect_visual_domain", return_value=("ambiguous", 0.22, {"skin": 0.22, "xray": 0.21})):
        result = classifier.classify(dummy_image)

    assert result["status"] == "inconclusive"
    assert result["category"] == "ambiguous"


# ==============================================================================
# SCENARIO 13: NON-MEDICAL IMAGE DETECTION
# ==============================================================================

def test_scenario_13_non_medical_image_returns_unsupported(dummy_image):
    """
    Scenario 13:
    When image is non-medical (e.g. landscape, animal, furniture):
    - classify() returns status='unsupported_image'.
    - Disease models are skipped completely.
    """
    classifier = DiseaseClassifier()
    with patch("app.services.disease_classifier.detect_visual_domain", return_value=("non_medical", 0.78, {"non_medical": 0.78})):
        result = classifier.classify(dummy_image)

    assert result["status"] == "unsupported_image"
    assert result["category"] == "non_medical"
    assert result["disease"] is None


# ==============================================================================
# SCENARIOS 14 & 15: INFERENCE EXCEPTION & EMPTY PREDICTIONS
# ==============================================================================

def test_scenario_14_inference_exception_handled_inconclusive(dummy_image):
    """
    Scenario 14:
    When specialist model raises an exception during inference:
    - classify() catches it and returns status='inconclusive'.
    - Does NOT attempt cross-modality fallback.
    """
    classifier = DiseaseClassifier()
    mock_model = MagicMock()
    mock_model.predict.side_effect = RuntimeError("Forward pass tensor error")
    classifier.models["skin"] = mock_model

    with patch("app.services.disease_classifier.detect_visual_domain", return_value=("skin", 0.85, {"skin": 0.85})):
        result = classifier.classify(dummy_image)

    assert result["status"] == "inconclusive"
    assert "error occurred during skin model inference" in result["message"]


def test_scenario_15_empty_predictions_handled_inconclusive():
    """
    Scenario 15:
    When model returns empty predictions:
    - Returns status='inconclusive' with reason='empty_predictions'.
    """
    classifier = DiseaseClassifier()
    result = classifier._interpret_predictions("general", [], 0.0)

    assert result["status"] == "inconclusive"
    assert result["reason"] == "empty_predictions"
    assert result["disease"] is None


# ==============================================================================
# SCENARIO 17: SCORE INTERPRETATION & UNCALIBRATED VALUES
# ==============================================================================

def test_scenario_17_score_interpretation_and_no_calibrated_confidence(dummy_image):
    """
    Scenario 17:
    Verify that output scores are explicitly uncalibrated:
    - 'score' is present and matches model raw output.
    - 'calibrated_confidence' is None.
    - 'score_interpretation' warning is present.
    """
    classifier = DiseaseClassifier()
    mock_model = MagicMock()
    mock_model.predict.return_value = (
        [{"disease": "melanoma", "confidence": 0.8234}],
        0.8234
    )
    classifier.models["skin"] = mock_model

    with patch("app.services.disease_classifier.detect_visual_domain", return_value=("skin", 0.90, {"skin": 0.90})):
        result = classifier.classify(dummy_image)

    assert result["status"] == "analysis_complete"
    assert result["score"] == 0.8234
    assert result["calibrated_confidence"] is None
    assert result["calibrated_conf"] is None
    assert "Unvalidated model score" in result["score_interpretation"]


# ==============================================================================
# SCENARIOS 18, 19, 20: FASTAPI IMAGE ENDPOINT STATUS CODES
# ==============================================================================

def test_scenario_18_endpoint_invalid_image_returns_400(test_client, mock_auth_user):
    """
    Scenario 18:
    POST /api/v1/analyze-image with invalid non-image bytes returns HTTP 400 invalid_image.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    try:
        response = test_client.post(
            "/api/v1/analyze-image",
            files={"file": ("corrupted.jpg", b"not-a-real-jpeg-data", "image/jpeg")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "invalid_image"
        assert data["success"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_scenario_19_endpoint_unsupported_image_returns_422(test_client, mock_auth_user, dummy_image_bytes):
    """
    Scenario 19:
    POST /api/v1/analyze-image with non-medical image returns HTTP 422 unsupported_image.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    try:
        with patch.object(disease_classifier, "classify") as mock_classify, \
             patch("app.api.image_api._get_blip") as mock_blip:

            mock_classify.return_value = {
                "status": "unsupported_image",
                "category": "non_medical",
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
            }
            # Mock BLIP processor and model
            mock_proc = MagicMock()
            mock_proc.return_value = {"pixel_values": MagicMock()}
            mock_proc.decode.return_value = "a cute golden retriever in a park"
            mock_blip_model = MagicMock()
            mock_blip_model.generate.return_value = [MagicMock()]
            mock_blip.return_value = (mock_proc, mock_blip_model)

            response = test_client.post(
                "/api/v1/analyze-image",
                files={"file": ("dog.jpg", dummy_image_bytes, "image/jpeg")},
            )
            assert response.status_code == 422
            data = response.json()
            assert data["status"] == "unsupported_image"
            assert data["success"] is False
            assert "description" in data
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_scenario_20a_endpoint_model_unavailable_returns_503(test_client, mock_auth_user, dummy_image_bytes):
    """
    Scenario 20A:
    POST /api/v1/analyze-image when matching specialist is missing returns HTTP 503 model_unavailable.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    try:
        with patch.object(disease_classifier, "classify") as mock_classify:
            mock_classify.return_value = {
                "status": "model_unavailable",
                "category": "skin",
                "message": "Specialist AI model for 'skin' is not loaded on this server.",
            }

            response = test_client.post(
                "/api/v1/analyze-image",
                files={"file": ("skin_lesion.jpg", dummy_image_bytes, "image/jpeg")},
            )
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "model_unavailable"
            assert data["category"] == "skin"
            assert data["success"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_scenario_20b_endpoint_inconclusive_returns_200(test_client, mock_auth_user, dummy_image_bytes):
    """
    Scenario 20B:
    POST /api/v1/analyze-image when classification is ambiguous or inconclusive returns HTTP 200 inconclusive.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    try:
        with patch.object(disease_classifier, "classify") as mock_classify:
            mock_classify.return_value = {
                "status": "inconclusive",
                "message": "Image modality could not be reliably determined from visual features.",
                "category": "ambiguous",
                "disease": None,
                "score": 0.0,
            }

            response = test_client.post(
                "/api/v1/analyze-image",
                files={"file": ("blurry.jpg", dummy_image_bytes, "image/jpeg")},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "inconclusive"
            assert data["success"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_scenario_20c_endpoint_analysis_complete_returns_200(test_client, mock_auth_user, dummy_image_bytes):
    """
    Scenario 20C:
    POST /api/v1/analyze-image when classification succeeds returns HTTP 200 analysis_complete.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    try:
        with patch.object(disease_classifier, "classify") as mock_classify:
            mock_classify.return_value = {
                "status": "analysis_complete",
                "category": "skin",
                "finding_type": "condition_detected",
                "is_negative_finding": False,
                "disease": "Actinic Keratosis",
                "score": 0.8543,
                "predictions": [
                    {"disease": "Actinic Keratosis", "score": 0.8543},
                ],
            }

            response = test_client.post(
                "/api/v1/analyze-image",
                files={"file": ("lesion.jpg", dummy_image_bytes, "image/jpeg")},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "analysis_complete"
            assert data["success"] is True
            assert data["disease"] == "Actinic Keratosis"
            assert data["score"] == 0.8543
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_scenario_security_endpoint_unauthenticated_returns_401(test_client, dummy_image_bytes):
    """
    Verification:
    POST /api/v1/analyze-image without valid Authorization header or session cookie returns HTTP 401.
    """
    response = test_client.post(
        "/api/v1/analyze-image",
        files={"file": ("test.jpg", dummy_image_bytes, "image/jpeg")},
    )
    assert response.status_code == 401
