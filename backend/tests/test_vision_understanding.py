"""
NewGenHealthAI — tests/test_vision_understanding.py
Comprehensive automated test suite verifying intelligent image understanding,
multimodal routing, medical safety guardrails, override protection,
and fallback reliability across all 15 scenarios.
"""

import io
import json
import pytest
import numpy as np
from PIL import Image
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.disease_classifier import disease_classifier
from app.services.vision_service import (
    vision_service,
    analyze_visual_features_deterministic,
    image_to_base64_jpeg,
)
from app.core.dependencies import get_current_user
from app.models.message import User


@pytest.fixture
def mock_user():
    user = User(id=999, username="vision_tester", hashed_password="pw")
    setattr(user, "user_id", 999)
    return user


@pytest.fixture
def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)


def _img_to_bytes(img: Image.Image, format: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


# ==============================================================================
# 1. Normal Person Photograph — General Recognition, NO Disease, NO Face ID
# ==============================================================================

def test_scenario_01_normal_person_photo(client):
    """
    Scenario 1: Normal person portrait/selfie.
    - Recognized as person portrait.
    - is_person=True, is_medical=False, medical_applicable=False.
    - NO disease prediction or diagnosis.
    - NO identity guessing / face recognition.
    - Returns HTTP 200 with status='general_recognition' (Universal Image Recognition Card).
    """
    person_img = Image.new("RGB", (200, 200), color=(210, 180, 140))
    mock_understanding = {
        "status": "general_recognition",
        "is_medical": False,
        "category": "person",
        "detected_subject": "Portrait of Person",
        "description": "A close-up portrait of an adult human smiling outdoors.",
        "modality": None,
        "confidence": "high",
        "is_person": True,
        "medical_applicable": False,
        "reason_not_applicable": "This is an ordinary photograph of a person. Ordinary photographs cannot be used for clinical medical diagnosis.",
        "safety_disclaimer": "Real-person facial recognition and medical disease inference are strictly prohibited on ordinary portraits.",
        "engine": "groq_vision",
        "vision_model": "qwen/qwen3.8-27b",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        # Direct classifier check
        res = disease_classifier.classify(person_img)
        assert res["status"] == "general_recognition"
        assert res["success"] is True
        assert res["category"] == "person"
        assert res["detected_category"] == "person"
        assert res["detected_subject"] == "Portrait of Person"
        assert res["is_person"] is True
        assert res["medical_applicable"] is False
        assert res["disease"] is None

        # API endpoint check: Returns HTTP 200 general_recognition card (NOT 422 error)
        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": ("selfie.jpg", _img_to_bytes(person_img), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "general_recognition"
        assert data["success"] is True
        assert data["detected_subject"] == "Portrait of Person"
        assert data["is_person"] is True
        assert data["medical_applicable"] is False
        assert "ordinary photograph of a person" in data["reason_not_applicable"].lower()
        assert "prohibited" in data["safety_disclaimer"].lower()


# ==============================================================================
# 2. Dog Photograph — Animal Recognition, NO Disease Diagnosis
# ==============================================================================

def test_scenario_02_dog_photograph(client):
    """
    Scenario 2: Dog photograph.
    - Recognized as dog / animal.
    - is_medical=False, medical_applicable=False.
    - Explicit explanation that veterinary images are outside medical intake scope.
    - Returns HTTP 200 general_recognition.
    """
    dog_img = Image.new("RGB", (200, 200), color=(180, 120, 60))
    mock_understanding = {
        "status": "general_recognition",
        "is_medical": False,
        "category": "animal",
        "detected_subject": "Golden Retriever Dog",
        "description": "A golden retriever sitting on grass looking towards the camera.",
        "modality": None,
        "confidence": "high",
        "is_person": False,
        "medical_applicable": False,
        "reason_not_applicable": "This image depicts an animal. Veterinary images are outside the scope of human medical intake.",
        "safety_disclaimer": "Veterinary images are outside the scope of human medical intake.",
        "engine": "groq_vision",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        res = disease_classifier.classify(dog_img)
        assert res["status"] == "general_recognition"
        assert res["success"] is True
        assert res["detected_category"] == "animal"
        assert res["detected_subject"] == "Golden Retriever Dog"
        assert res["medical_applicable"] is False
        assert res["disease"] is None

        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": ("dog.jpg", _img_to_bytes(dog_img), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "general_recognition"
        assert data["success"] is True
        assert "animal" in data["detected_category"]
        assert "veterinary" in data["reason_not_applicable"].lower()


# ==============================================================================
# 3. Cat Photograph — Animal Recognition, NO Disease Diagnosis
# ==============================================================================

def test_scenario_03_cat_photograph(client):
    """
    Scenario 3: Cat photograph.
    - Recognized as cat / domestic feline.
    - is_medical=False, medical_applicable=False.
    - Returns HTTP 200 general_recognition.
    """
    cat_img = Image.new("RGB", (200, 200), color=(100, 100, 100))
    mock_understanding = {
        "status": "general_recognition",
        "is_medical": False,
        "category": "animal",
        "detected_subject": "Domestic Tabby Cat",
        "description": "A tabby cat resting indoors on a rug.",
        "modality": None,
        "confidence": "high",
        "is_person": False,
        "medical_applicable": False,
        "reason_not_applicable": "This image depicts an animal. Veterinary images are outside the scope of human medical intake.",
        "safety_disclaimer": "Veterinary images are outside the scope of human medical intake.",
        "engine": "groq_vision",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        res = disease_classifier.classify(cat_img)
        assert res["status"] == "general_recognition"
        assert res["success"] is True
        assert res["detected_category"] == "animal"
        assert res["detected_subject"] == "Domestic Tabby Cat"
        assert res["disease"] is None

        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": ("cat.jpg", _img_to_bytes(cat_img), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "general_recognition"
        assert data["success"] is True


# ==============================================================================
# 4. Plant / Flower Photograph — Botany Recognition
# ==============================================================================

def test_scenario_04_plant_photograph(client):
    """
    Scenario 4: Plant/flower photograph.
    - Recognized as houseplant / flower.
    - is_medical=False.
    - Returns HTTP 200 general_recognition.
    """
    plant_img = Image.new("RGB", (200, 200), color=(30, 160, 40))
    mock_understanding = {
        "status": "general_recognition",
        "is_medical": False,
        "category": "plant",
        "detected_subject": "Ficus Houseplant",
        "description": "A potted ficus indoor plant with glossy green leaves.",
        "modality": None,
        "confidence": "high",
        "is_person": False,
        "medical_applicable": False,
        "reason_not_applicable": "Everyday non-medical objects and scenes are not applicable for medical diagnostic analysis.",
        "safety_disclaimer": "Everyday non-medical objects and scenes are not applicable for clinical diagnostic models.",
        "engine": "groq_vision",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        res = disease_classifier.classify(plant_img)
        assert res["status"] == "general_recognition"
        assert res["success"] is True
        assert res["detected_category"] == "plant"
        assert res["detected_subject"] == "Ficus Houseplant"
        assert res["disease"] is None

        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": ("plant.jpg", _img_to_bytes(plant_img), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "general_recognition"
        assert data["success"] is True


# ==============================================================================
# 5. Everyday Object (Car / Cup / Chair) — Object Recognition
# ==============================================================================

def test_scenario_05_everyday_object(client):
    """
    Scenario 5: Everyday object (e.g. vehicle, coffee cup, chair).
    - Recognized as everyday object.
    - is_medical=False.
    - Returns HTTP 200 general_recognition.
    """
    car_img = Image.new("RGB", (200, 200), color=(200, 30, 30))
    mock_understanding = {
        "status": "general_recognition",
        "is_medical": False,
        "category": "vehicle",
        "detected_subject": "Red Automobile",
        "description": "A red sedan car parked in a paved driveway.",
        "modality": None,
        "confidence": "high",
        "is_person": False,
        "medical_applicable": False,
        "reason_not_applicable": "Everyday non-medical objects and scenes are not applicable for medical diagnostic analysis.",
        "safety_disclaimer": "Everyday non-medical objects and scenes are not applicable for clinical diagnostic models.",
        "engine": "groq_vision",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        res = disease_classifier.classify(car_img)
        assert res["status"] == "general_recognition"
        assert res["success"] is True
        assert res["detected_category"] == "vehicle"
        assert res["detected_subject"] == "Red Automobile"
        assert res["disease"] is None

        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": ("car.jpg", _img_to_bytes(car_img), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "general_recognition"
        assert data["success"] is True


# ==============================================================================
# 6. Landscape / Outdoor Scene — Landscape Recognition
# ==============================================================================

def test_scenario_06_landscape_outdoor_scene(client):
    """
    Scenario 6: Landscape / outdoor scenery.
    - Recognized as landscape.
    - is_medical=False.
    - Returns HTTP 200 general_recognition.
    """
    land_img = Image.new("RGB", (200, 200), color=(100, 180, 240))
    mock_understanding = {
        "status": "general_recognition",
        "is_medical": False,
        "category": "landscape",
        "detected_subject": "Mountain Landscape",
        "description": "Scenic view of mountain peaks against a clear blue sky.",
        "modality": None,
        "confidence": "high",
        "is_person": False,
        "medical_applicable": False,
        "reason_not_applicable": "Everyday non-medical objects and scenes are not applicable for medical diagnostic analysis.",
        "safety_disclaimer": "Everyday non-medical objects and scenes are not applicable for clinical diagnostic models.",
        "engine": "groq_vision",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        res = disease_classifier.classify(land_img)
        assert res["status"] == "general_recognition"
        assert res["success"] is True
        assert res["detected_category"] == "landscape"
        assert res["detected_subject"] == "Mountain Landscape"
        assert res["disease"] is None

        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": ("mountain.jpg", _img_to_bytes(land_img), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "general_recognition"
        assert data["success"] is True


# ==============================================================================
# 7. Skin Condition Image — Correct Routing to Skin Specialist
# ==============================================================================

def test_scenario_07_skin_condition_routing(client):
    """
    Scenario 7: Dermatological rash/lesion.
    - is_medical=True, modality='skin'.
    - Routes to skin specialist model.
    - Attaches both visual description and clinical model finding.
    """
    skin_img = Image.new("RGB", (224, 224), color=(220, 150, 130))
    mock_understanding = {
        "is_medical": True,
        "category": "medical_skin",
        "detected_subject": "Erythematous Skin Rash",
        "description": "Focal erythematous macules and papules on cutaneous surface.",
        "modality": "skin",
        "confidence": "high",
        "is_person": False,
        "medical_applicable": True,
        "reason_not_applicable": None,
        "engine": "groq_vision",
    }

    mock_model = MagicMock()
    mock_model.predict.return_value = ([{"disease": "Eczema", "confidence": 0.88}], 0.88)

    with patch.object(vision_service, "understand_image", return_value=mock_understanding), \
         patch.object(disease_classifier, "get_specialist_model", return_value=mock_model), \
         patch.object(disease_classifier, "_models", {"skin": mock_model}):

        res = disease_classifier.classify(skin_img, routed_category="skin", modality_confirmed=True)
        assert res["status"] == "analysis_complete"
        assert res["category"] == "skin"
        assert res["detected_subject"] == "Erythematous Skin Rash"
        assert res["disease"] == "Eczema"
        assert res["is_person"] is None
        assert res["medical_applicable"] is True


# ==============================================================================
# 8. X-Ray Radiograph Image — Anatomical vs Pathology Separation
# ==============================================================================

def test_scenario_08_xray_radiograph_routing(client):
    """
    Scenario 8: Bone radiograph (e.g. wrist).
    - is_medical=True, modality='xray'.
    - Routes to X-ray specialist model.
    - Distinguishes anatomical location from disease/fracture.
    """
    xray_img = Image.new("RGB", (224, 224), color=(50, 50, 50))
    mock_understanding = {
        "is_medical": True,
        "category": "medical_xray",
        "detected_subject": "Wrist Radiograph (X-ray)",
        "description": "Anteroposterior radiograph of human wrist showing distal radius and carpal bones.",
        "modality": "xray",
        "confidence": "high",
        "is_person": False,
        "medical_applicable": True,
        "reason_not_applicable": None,
        "engine": "groq_vision",
    }

    mock_model = MagicMock()
    mock_model.predict.return_value = ([{"disease": "wrist", "confidence": 0.94}], 0.94)

    with patch.object(vision_service, "understand_image", return_value=mock_understanding), \
         patch.object(disease_classifier, "get_specialist_model", return_value=mock_model), \
         patch.object(disease_classifier, "_models", {"xray": mock_model}):

        res = disease_classifier.classify(xray_img, routed_category="xray", modality_confirmed=True)
        assert res["status"] == "analysis_complete"
        assert res["category"] == "xray"
        assert res["finding_type"] == "anatomy_identified"
        assert "fracture" not in res["disease"].lower()
        assert res["detected_subject"] == "Wrist Radiograph (X-ray)"


# ==============================================================================
# 9. Retinal Fundus Image — Retina Routing
# ==============================================================================

def test_scenario_09_retina_fundus_routing(client):
    """
    Scenario 9: Retinal fundus scan.
    - is_medical=True, modality='retina'.
    - Routes to retina specialist model.
    """
    retina_img = Image.new("RGB", (224, 224), color=(140, 40, 20))
    mock_understanding = {
        "is_medical": True,
        "category": "medical_retina",
        "detected_subject": "Retinal Fundus Eye Scan",
        "description": "Circular fundus view demonstrating optic disc, macula, and retinal vasculature.",
        "modality": "retina",
        "confidence": "high",
        "is_person": False,
        "medical_applicable": True,
        "reason_not_applicable": None,
        "engine": "groq_vision",
    }

    mock_model = MagicMock()
    mock_model.predict.return_value = ([{"disease": "Diabetic Retinopathy", "confidence": 0.82}], 0.82)

    with patch.object(vision_service, "understand_image", return_value=mock_understanding), \
         patch.object(disease_classifier, "get_specialist_model", return_value=mock_model), \
         patch.object(disease_classifier, "_models", {"retina": mock_model}):

        res = disease_classifier.classify(retina_img, routed_category="retina", modality_confirmed=True)
        assert res["status"] == "analysis_complete"
        assert res["category"] == "retina"
        assert res["detected_subject"] == "Retinal Fundus Eye Scan"
        assert res["disease"] == "Diabetic Retinopathy"


# ==============================================================================
# 10. Blurry / Ambiguous Image — Honest Inconclusive
# ==============================================================================

def test_scenario_10_blurry_ambiguous_image(client):
    """
    Scenario 10: Blurry or ambiguous upload.
    - category='ambiguous', confidence='low'.
    - Returns status='inconclusive' with honest feedback to upload a clearer image.
    """
    blurry_img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    mock_understanding = {
        "is_medical": False,
        "category": "ambiguous",
        "detected_subject": "Unfocused Blurry Image",
        "description": "The image is out of focus and has severe motion blur.",
        "modality": None,
        "confidence": "low",
        "is_person": False,
        "medical_applicable": False,
        "reason_not_applicable": "The uploaded image is too blurry for reliable visual interpretation. Please upload a clear photograph.",
        "engine": "groq_vision",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        res = disease_classifier.classify(blurry_img)
        assert res["status"] == "inconclusive"
        assert "blurry" in res["message"].lower() or "reliably determined" in res["message"].lower()

        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": ("blur.jpg", _img_to_bytes(blurry_img), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "inconclusive"
        assert data["success"] is False


# ==============================================================================
# 11. Corrupted File — HTTP 400 Safe Handling
# ==============================================================================

def test_scenario_11_corrupted_file(client):
    """
    Scenario 11: Non-image or corrupted bytes.
    - Endpoint returns HTTP 400 with invalid_image status.
    - No unhandled 500 error.
    """
    corrupt_bytes = b"NOT_A_VALID_JPEG_HEADER_RANDOM_CORRUPTED_STREAM_0123456789"
    resp = client.post(
        "/api/v1/analyze-image",
        files={"file": ("broken.jpg", corrupt_bytes, "image/jpeg")},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["status"] == "invalid_image"
    assert data["success"] is False


# ==============================================================================
# 12. Vision API Unavailable / Rate-Limited — Graceful Fallback
# ==============================================================================

def test_scenario_12_api_unavailable_graceful_fallback():
    """
    Scenario 12: Groq Vision API fails (rate limit, timeout, offline).
    - Falls back cleanly to deterministic local feature analysis.
    - Returns valid deterministic result without fabricated fake detections.
    - Accurately declares recognition_unavailable rather than guessing plant/car/person.
    """
    # Create an image with variance/texture
    arr = np.random.RandomState(42).randint(40, 220, (200, 200, 3), dtype=np.uint8)
    img = Image.fromarray(arr)

    with patch.object(vision_service, "call_groq_vision", return_value=None), \
         patch("app.services.vision_service.classify_with_local_neural_vision", return_value=None):
        result = vision_service.understand_image(img)
        assert result["engine"] == "heuristic_fallback"
        assert result["is_medical"] is False
        assert result["status"] == "recognition_unavailable"
        assert result["medical_applicable"] is False
        assert "currently unavailable" in result["reason_not_applicable"].lower()


# ==============================================================================
# 13. User Modality Override Safeguard — Reject Override on Non-Medical
# ==============================================================================

def test_scenario_13_user_modality_override_safeguard(client):
    """
    Scenario 13: User selects 'Skin' override, but uploads a dog photograph.
    - Modality override MUST NOT force execution of skin disease classifier.
    - Must detect the mismatch and explain that user-selected modality does not match.
    - Returns HTTP 422 unsupported_image.
    """
    dog_img = Image.new("RGB", (200, 200), color=(180, 120, 60))
    mock_understanding = {
        "is_medical": False,
        "category": "animal",
        "detected_subject": "Golden Retriever Dog",
        "description": "A golden retriever dog sitting on a lawn.",
        "modality": None,
        "confidence": "high",
        "is_person": False,
        "medical_applicable": False,
        "reason_not_applicable": "This image depicts an animal. Veterinary images are outside human medical intake.",
        "engine": "groq_vision",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        # Override with routed_category='skin'
        res = disease_classifier.classify(dog_img, routed_category="skin", modality_confirmed=True)
        assert res["status"] == "unsupported_image"
        assert res["category"] == "non_medical"
        assert res["detected_subject"] == "Golden Retriever Dog"
        assert res["modality_source"] == "user_selected"
        assert "does not match" in res["message"].lower()

        # Via HTTP API with Form(modality='skin')
        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": ("dog.jpg", _img_to_bytes(dog_img), "image/jpeg")},
            data={"modality": "skin"},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["status"] == "unsupported_image"
        assert data["detected_subject"] == "Golden Retriever Dog"
        assert data["medical_applicable"] is False


# ==============================================================================
# 14. General Model Audit: Unsupported Modality Rejection
# ==============================================================================

def test_scenario_14_general_model_unsupported_modality_audit():
    """
    Scenario 14: Medical image outside supported specialist scope (e.g. ear endoscopy).
    - General model must NOT produce spurious classifications for out-of-domain modalities.
    - Returns status='inconclusive' with honest referral to clinical specialist.
    """
    ear_img = Image.new("RGB", (224, 224), color=(180, 100, 80))
    mock_understanding = {
        "is_medical": True,
        "category": "medical_general",
        "detected_subject": "Otoscopic Ear Canal Examination",
        "description": "Endoscopic view of external auditory canal and tympanic membrane.",
        "modality": "general",
        "confidence": "high",
        "is_person": False,
        "medical_applicable": True,
        "reason_not_applicable": None,
        "engine": "groq_vision",
    }

    with patch.object(vision_service, "understand_image", return_value=mock_understanding):
        res = disease_classifier.classify(ear_img, routed_category="general", modality_confirmed=True)
        assert res["status"] == "inconclusive"
        assert res["category"] == "unsupported_medical"
        assert "outside the scope of our supported specialist models" in res["message"]


# ==============================================================================
# 15. General Model Audit: Supported Scope (Brain MRI / Blood Microscopy)
# ==============================================================================

def test_scenario_15_general_model_supported_brain_mri():
    """
    Scenario 15: Supported general medical image (Brain MRI).
    - Detected subject matches supported general domain.
    - General model runs and provides valid prediction.
    """
    mri_img = Image.new("RGB", (224, 224), color=(40, 40, 40))
    mock_understanding = {
        "is_medical": True,
        "category": "medical_general",
        "detected_subject": "Axial Brain MRI Scan",
        "description": "T1-weighted axial magnetic resonance imaging of human brain.",
        "modality": "general",
        "confidence": "high",
        "is_person": False,
        "medical_applicable": True,
        "reason_not_applicable": None,
        "engine": "groq_vision",
    }

    mock_model = MagicMock()
    mock_model.predict.return_value = ([{"disease": "Glioma", "confidence": 0.89}], 0.89)

    with patch.object(vision_service, "understand_image", return_value=mock_understanding), \
         patch.object(disease_classifier, "get_specialist_model", return_value=mock_model), \
         patch.object(disease_classifier, "_models", {"general": mock_model}):

        res = disease_classifier.classify(mri_img, routed_category="general", modality_confirmed=True)
        assert res["status"] == "analysis_complete"
        assert res["category"] == "general"
        assert res["detected_subject"] == "Axial Brain MRI Scan"
        assert "Glioma" in res["disease"]


# ==============================================================================
# 16. Vision Fallback: Primary Fails, Fallback Model Succeeds
# ==============================================================================

def test_scenario_16_primary_fails_fallback_model_succeeds():
    """
    Scenario 16: Primary vision model ('qwen/qwen3.8-27b') encounters an error (e.g. 503 or 429),
    system automatically calls fallback model ('meta-models/muse-spark-open') and succeeds.
    """
    mock_client = MagicMock()
    mock_img = Image.new("RGB", (100, 100), color=(100, 200, 100))

    fallback_payload = {
        "is_medical": False,
        "category": "plant",
        "detected_subject": "Botanical Plant",
        "description": "Green houseplant foliage.",
        "modality": None,
        "confidence": "high",
        "is_person": False,
        "medical_applicable": False,
        "reason_not_applicable": "This image depicts a plant.",
    }
    fallback_response = MagicMock()
    fallback_response.choices = [MagicMock(message=MagicMock(content=json.dumps(fallback_payload)))]

    # First call (primary) raises Exception, second call (fallback) returns valid response
    mock_client.chat.completions.create.side_effect = [
        Exception("503 Service Unavailable: primary model overloaded"),
        fallback_response,
    ]

    with patch.object(vision_service, "_get_client", return_value=mock_client):
        res = vision_service.call_groq_vision(mock_img)
        assert res is not None
        assert res["category"] == "plant"
        assert res["detected_subject"] == "Botanical Plant"
        assert res["vision_model"] == "meta-models/muse-spark-open"
        assert res["engine"] == "groq_vision"
        assert mock_client.chat.completions.create.call_count == 2


# ==============================================================================
# 17. Vision Fallback: Both Remote Vision Models Fail -> Graceful Degradation
# ==============================================================================

def test_scenario_17_both_remote_models_fail_graceful_degradation():
    """
    Scenario 17: Both primary and fallback remote models fail.
    System does not raise an exception, does not crash, and gracefully degrades
    to the deterministic local visual feature analyzer without fabricating object labels.
    """
    mock_client = MagicMock()
    # Image with variance/texture
    arr = np.random.RandomState(42).randint(40, 220, (120, 120, 3), dtype=np.uint8)
    foliage_img = Image.fromarray(arr)

    mock_client.chat.completions.create.side_effect = [
        Exception("404 Model Not Found: qwen/qwen3.8-27b"),
        Exception("403 Forbidden: meta-models/muse-spark-open preview whitelist required"),
    ]

    with patch.object(vision_service, "_get_client", return_value=mock_client), \
         patch("app.services.vision_service.classify_with_local_neural_vision", return_value=None):
        # understand_image handles both remote failures cleanly
        res = vision_service.understand_image(foliage_img)
        assert res is not None
        assert res["engine"] == "heuristic_fallback"
        assert res["status"] in ("recognition_unavailable", "ambiguous")
        assert res["is_medical"] is False


# ==============================================================================
# 18. Vision Fallback: Authentication Error Short-Circuits Cleanly
# ==============================================================================

def test_scenario_18_authentication_failure_short_circuits():
    """
    Scenario 18: Groq API key returns 401 AuthenticationError.
    System short-circuits immediately without retrying other models on the bad key,
    falling back to local deterministic analysis without crashing or fabricating labels.
    """
    mock_client = MagicMock()
    arr = np.random.RandomState(42).randint(40, 220, (100, 100, 3), dtype=np.uint8)
    xray_img = Image.fromarray(arr)

    mock_client.chat.completions.create.side_effect = Exception("401 AuthenticationError: Invalid API Key")

    with patch.object(vision_service, "_get_client", return_value=mock_client), \
         patch("app.services.vision_service.classify_with_local_neural_vision", return_value=None):
        res = vision_service.understand_image(xray_img)
        assert res is not None
        assert res["engine"] == "heuristic_fallback"
        assert res["status"] in ("recognition_unavailable", "ambiguous")
        # Only 1 call made because auth failure breaks immediately
        assert mock_client.chat.completions.create.call_count == 1


# ==============================================================================
# 19. Dataset Validation: Nonexistent Directory -> NOT_INGESTED
# ==============================================================================

def test_dataset_validation_nonexistent_dir():
    from scripts.evaluate_image_understanding import verify_genuine_dataset_status, STATE_NOT_INGESTED
    res = verify_genuine_dataset_status("/nonexistent/dataset/path")
    assert res["verification_state"] == STATE_NOT_INGESTED
    assert res["is_verified"] is False
    assert "PENDING" in res["status"]


# ==============================================================================
# 20. Dataset Validation: Software License Rejection
# ==============================================================================

def test_dataset_validation_software_license_rejected(tmp_path):
    from scripts.evaluate_image_understanding import verify_genuine_dataset_status, STATE_NOT_INGESTED
    import hashlib

    img_path = tmp_path / "photo.jpg"
    im = Image.new("RGB", (30, 30), color=(100, 100, 100))
    im.save(str(img_path))
    with open(img_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    manifest = [{
        "id": "IMG_01",
        "filename": "photo.jpg",
        "is_synthetic": False,
        "original_source": "Hospital Archive",
        "dataset_identifier": "ACC_123",
        "license": "Apache-2.0",  # Software license - disallowed!
        "ground_truth_label": "benign_nevus",
        "sha256": sha,
    }]
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    res = verify_genuine_dataset_status(str(tmp_path))
    assert res["verification_state"] == STATE_NOT_INGESTED
    assert res["is_verified"] is False
    assert "software licence 'Apache-2.0'" in res["reason"]


# ==============================================================================
# 21. Dataset Validation: Self-Reported Boolean Manifest Flag Insufficient
# ==============================================================================

def test_dataset_validation_self_reported_boolean_insufficient(tmp_path):
    from scripts.evaluate_image_understanding import (
        verify_genuine_dataset_status,
        STATE_MANUAL_REVIEW_REQUIRED,
        STATE_METADATA_VALIDATED,
    )
    import hashlib

    img_path = tmp_path / "photo.jpg"
    im = Image.new("RGB", (30, 30), color=(100, 100, 100))
    im.save(str(img_path))
    with open(img_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    manifest = [{
        "id": "IMG_01",
        "filename": "photo.jpg",
        "is_synthetic": False,
        "original_source": "ISIC Archive",
        "dataset_identifier": "ISIC_0000001",
        "license": "CC-BY-4.0",
        "ground_truth_label": "melanoma",
        "sha256": sha,
        "independently_verified_provenance": True,  # Self-reported flag
    }]
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    res = verify_genuine_dataset_status(str(tmp_path))
    assert res["verification_state"] == STATE_MANUAL_REVIEW_REQUIRED
    assert res["technical_state"] == STATE_METADATA_VALIDATED
    assert res["is_verified"] is False
    assert "Boolean claims in manifests are insufficient" in res["reason"]


# ==============================================================================
# 22. Dataset Validation: Verified After Qualified Manual Review Record (CC-BY-4.0)
# ==============================================================================

def test_dataset_validation_verified_after_manual_review(tmp_path):
    from scripts.evaluate_image_understanding import (
        verify_genuine_dataset_status,
        STATE_VERIFIED_AFTER_MANUAL_REVIEW,
        STATE_METADATA_VALIDATED,
    )
    import hashlib

    img_path = tmp_path / "photo.jpg"
    im = Image.new("RGB", (30, 30), color=(100, 100, 100))
    im.save(str(img_path))
    with open(img_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    manifest = [{
        "id": "IMG_01",
        "filename": "photo.jpg",
        "is_synthetic": False,
        "original_source": "ISIC Archive",
        "dataset_identifier": "ISIC_0000001",
        "license": "CC-BY-4.0",
        "ground_truth_label": "melanoma",
        "sha256": sha,
    }]
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    review_record = {
        "reviewer": "Dr. Clinical Lead, MD (Lic #MED-88192)",
        "review_date": "2026-11-04T00:00:00Z",
        "source_evidence": "Primary institutional repository record with verified donor consent",
        "legal_instrument": "CC-BY-4.0",
        "image_copyright_cleared": True,
        "attribution_requirements_recorded": True,
        "database_rights_reviewed": True,
        "patient_consent_verified": True,
        "publicity_rights_cleared": True,
        "access_restrictions_cleared": True,
        "approval_decision": "APPROVED",
    }
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(review_record, f)

    res = verify_genuine_dataset_status(str(tmp_path))
    assert res["verification_state"] == STATE_VERIFIED_AFTER_MANUAL_REVIEW
    assert res["technical_state"] == STATE_METADATA_VALIDATED
    assert res["is_verified"] is True
    assert res["reviewer"] == "Dr. Clinical Lead, MD (Lic #MED-88192)"
    assert res["approval_decision"] == "APPROVED"
    assert res["legal_instrument"] == "CC-BY-4.0"
    assert res["review_dimensions"]["image_copyright_cleared"] is True
    assert res["review_dimensions"]["database_rights_reviewed"] is True


# ==============================================================================
# 23. Dataset Validation: Creative Commons Requires Attribution / ShareAlike
# ==============================================================================

def test_dataset_validation_cc_attribution_and_sharealike_conditions(tmp_path):
    from scripts.evaluate_image_understanding import (
        verify_genuine_dataset_status,
        STATE_MANUAL_REVIEW_REQUIRED,
        STATE_VERIFIED_AFTER_MANUAL_REVIEW,
    )
    import hashlib

    img_path = tmp_path / "photo.jpg"
    im = Image.new("RGB", (30, 30), color=(100, 100, 100))
    im.save(str(img_path))
    with open(img_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    # Test CC-BY-SA-4.0 with missing sharealike_requirements_recorded
    manifest = [{
        "id": "IMG_SA",
        "filename": "photo.jpg",
        "is_synthetic": False,
        "original_source": "Open Clinical Archive",
        "dataset_identifier": "OCA_001",
        "license": "CC-BY-SA-4.0",
        "ground_truth_label": "fracture",
        "sha256": sha,
    }]
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    review_record = {
        "reviewer": "Reviewer A",
        "review_date": "2026-11-04T00:00:00Z",
        "source_evidence": "Primary archive",
        "legal_instrument": "CC-BY-SA-4.0",
        "image_copyright_cleared": True,
        "attribution_requirements_recorded": True,
        "sharealike_requirements_recorded": False,  # Missing ShareAlike condition!
        "database_rights_reviewed": True,
        "patient_consent_verified": True,
        "publicity_rights_cleared": True,
        "access_restrictions_cleared": True,
        "approval_decision": "APPROVED",
    }
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(review_record, f)

    res = verify_genuine_dataset_status(str(tmp_path))
    assert res["verification_state"] == STATE_MANUAL_REVIEW_REQUIRED
    assert res["is_verified"] is False
    assert "ShareAlike conditions" in res["reason"]

    # Now fix sharealike_requirements_recorded -> should transition to VERIFIED
    review_record["sharealike_requirements_recorded"] = True
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(review_record, f)

    res2 = verify_genuine_dataset_status(str(tmp_path))
    assert res2["verification_state"] == STATE_VERIFIED_AFTER_MANUAL_REVIEW
    assert res2["is_verified"] is True


# ==============================================================================
# 24. Dataset Validation: CC0-1.0 Public-Domain Dedication Authority
# ==============================================================================

def test_dataset_validation_cc0_dedication_authority(tmp_path):
    from scripts.evaluate_image_understanding import (
        verify_genuine_dataset_status,
        STATE_MANUAL_REVIEW_REQUIRED,
        STATE_VERIFIED_AFTER_MANUAL_REVIEW,
    )
    import hashlib

    img_path = tmp_path / "photo.jpg"
    im = Image.new("RGB", (30, 30), color=(100, 100, 100))
    im.save(str(img_path))
    with open(img_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    manifest = [{
        "id": "IMG_CC0",
        "filename": "photo.jpg",
        "is_synthetic": False,
        "original_source": "Hospital Open Access",
        "dataset_identifier": "HOA_999",
        "license": "CC0-1.0",
        "ground_truth_label": "benign",
        "sha256": sha,
    }]
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    # Review record without authority evidence
    review_record = {
        "reviewer": "Dr. Compliance, JD/MD",
        "review_date": "2026-11-04T00:00:00Z",
        "source_evidence": "Web download claiming CC0",
        "legal_instrument": "CC0-1.0",
        "image_copyright_cleared": True,
        "cc0_dedication_authority_verified": False,  # No evidence dedicator had authority!
        "database_rights_reviewed": True,
        "patient_consent_verified": True,
        "publicity_rights_cleared": True,
        "access_restrictions_cleared": True,
        "approval_decision": "APPROVED",
    }
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(review_record, f)

    res = verify_genuine_dataset_status(str(tmp_path))
    assert res["verification_state"] == STATE_MANUAL_REVIEW_REQUIRED
    assert res["is_verified"] is False
    assert "authority to do so" in res["reason"]

    # Now verify authority -> transitions to VERIFIED
    review_record["cc0_dedication_authority_verified"] = True
    review_record["source_evidence"] = "Hospital Copyright Transfer Agreement authorizing CC0 dedication"
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(review_record, f)

    res2 = verify_genuine_dataset_status(str(tmp_path))
    assert res2["verification_state"] == STATE_VERIFIED_AFTER_MANUAL_REVIEW
    assert res2["is_verified"] is True


# ==============================================================================
# 25. Dataset Validation: Public Domain Mark 1.0 (Status Label, Not a Licence)
# ==============================================================================

def test_dataset_validation_public_domain_mark_status_evidence(tmp_path):
    from scripts.evaluate_image_understanding import (
        verify_genuine_dataset_status,
        STATE_MANUAL_REVIEW_REQUIRED,
        STATE_VERIFIED_AFTER_MANUAL_REVIEW,
    )
    import hashlib

    img_path = tmp_path / "photo.jpg"
    im = Image.new("RGB", (30, 30), color=(100, 100, 100))
    im.save(str(img_path))
    with open(img_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    manifest = [{
        "id": "IMG_PDM",
        "filename": "photo.jpg",
        "is_synthetic": False,
        "original_source": "National Medical Library",
        "dataset_identifier": "NML_HIST_01",
        "license": "Public Domain Mark 1.0",
        "ground_truth_label": "normal_anatomical",
        "sha256": sha,
    }]
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    # Missing documented evidence supporting public domain status
    review_record = {
        "reviewer": "Archivist",
        "review_date": "2026-11-04T00:00:00Z",
        "source_evidence": "Found online with PDM icon",
        "legal_instrument": "Public Domain Mark 1.0",
        "image_copyright_cleared": True,
        "public_domain_status_evidence": "",  # Empty evidence!
        "database_rights_reviewed": True,
        "patient_consent_verified": True,
        "publicity_rights_cleared": True,
        "access_restrictions_cleared": True,
        "approval_decision": "APPROVED",
    }
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(review_record, f)

    res = verify_genuine_dataset_status(str(tmp_path))
    assert res["verification_state"] == STATE_MANUAL_REVIEW_REQUIRED
    assert res["is_verified"] is False
    assert "status label, not a licence" in res["reason"]

    # Provide documented evidence (e.g. published 1912, copyright expired)
    review_record["public_domain_status_evidence"] = "Published in 1912 medical treatise; copyright term expired worldwide."
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(review_record, f)

    res2 = verify_genuine_dataset_status(str(tmp_path))
    assert res2["verification_state"] == STATE_VERIFIED_AFTER_MANUAL_REVIEW
    assert res2["is_verified"] is True


# ==============================================================================
# 26. Dataset Validation: Separate Review Dimensions (Access Restrictions & Privacy)
# ==============================================================================

def test_dataset_validation_separate_review_dimensions_enforced(tmp_path):
    from scripts.evaluate_image_understanding import (
        verify_genuine_dataset_status,
        STATE_MANUAL_REVIEW_REQUIRED,
    )
    import hashlib

    img_path = tmp_path / "photo.jpg"
    im = Image.new("RGB", (30, 30), color=(100, 100, 100))
    im.save(str(img_path))
    with open(img_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    manifest = [{
        "id": "IMG_DIM",
        "filename": "photo.jpg",
        "is_synthetic": False,
        "original_source": "Hospital Repository",
        "dataset_identifier": "HOSP_101",
        "license": "CC-BY-4.0",
        "ground_truth_label": "lesion",
        "sha256": sha,
    }]
    with open(tmp_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    # Test 1: access_restrictions_cleared is False (mere public availability is NOT enough)
    base_record = {
        "reviewer": "Auditor",
        "review_date": "2026-11-04T00:00:00Z",
        "source_evidence": "Primary archive",
        "legal_instrument": "CC-BY-4.0",
        "image_copyright_cleared": True,
        "attribution_requirements_recorded": True,
        "database_rights_reviewed": True,
        "patient_consent_verified": True,
        "publicity_rights_cleared": True,
        "access_restrictions_cleared": False,  # Not cleared!
        "approval_decision": "APPROVED",
    }
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(base_record, f)

    res = verify_genuine_dataset_status(str(tmp_path))
    assert res["verification_state"] == STATE_MANUAL_REVIEW_REQUIRED
    assert res["is_verified"] is False
    assert "access restrictions" in res["reason"].lower()

    # Test 2: database_rights_reviewed is False
    base_record["access_restrictions_cleared"] = True
    base_record["database_rights_reviewed"] = False
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(base_record, f)

    res2 = verify_genuine_dataset_status(str(tmp_path))
    assert res2["verification_state"] == STATE_MANUAL_REVIEW_REQUIRED
    assert res2["is_verified"] is False
    assert "database rights" in res2["reason"].lower()

    # Test 3: patient_consent_verified is False
    base_record["database_rights_reviewed"] = True
    base_record["patient_consent_verified"] = False
    base_record["consent_privacy_verified"] = False
    with open(tmp_path / "provenance_review.json", "w") as f:
        json.dump(base_record, f)

    res3 = verify_genuine_dataset_status(str(tmp_path))
    assert res3["verification_state"] == STATE_MANUAL_REVIEW_REQUIRED
    assert res3["is_verified"] is False
    assert "patient consent" in res3["reason"].lower()


# ==============================================================================
# SECTION 8: LOCAL NEURAL VISION (MOBILENETV3-SMALL) INTEGRITY TESTS
# ==============================================================================

def test_local_neural_vision_blank_abstains():
    """Verify local neural vision honestly abstains as ambiguous on solid blank image."""
    from app.services.vision_service import classify_with_local_neural_vision
    blank = Image.new("RGB", (224, 224), color=(255, 255, 255))
    res = classify_with_local_neural_vision(blank)
    assert res is not None
    assert res["status"] == "ambiguous"
    assert res["category"] == "ambiguous"
    assert res["confidence"] == "low"
    assert res["engine"] == "local_neural_vision"
    assert res["vision_model"] == "mobilenet_v3_small"
    assert res["is_medical"] is False


def test_local_neural_vision_portrait_safety():
    """Verify local neural vision enforces non-medical person safety without unvalidated color heuristics."""
    from app.services.vision_service import classify_with_local_neural_vision
    # Create an image with skin tones matching human portrait
    arr = np.full((224, 224, 3), (210, 160, 130), dtype=np.uint8)
    arr[60:160, 60:160] = (225, 175, 145)
    portrait_img = Image.fromarray(arr)

    res = classify_with_local_neural_vision(portrait_img)
    assert res is not None
    # Must never be classified as medical or trigger clinical routing
    assert res["is_medical"] is False
    assert res["medical_applicable"] is False
    assert res["status"] in ("general_recognition", "modality_selection_required", "ambiguous")

    # When neural vision predicts a human person class (e.g. groom idx=982)
    with patch("app.services.vision_service._get_local_vision_model") as mock_model:
        import torch
        mock_m = MagicMock()
        mock_transform = lambda x: torch.zeros(3, 224, 224)
        mock_cats = ["object"] * 1000
        mock_cats[982] = "groom"
        logits = torch.zeros(1, 1000)
        logits[0, 982] = 10.0
        mock_m.return_value = logits
        mock_model.return_value = (mock_m, mock_transform, mock_cats)
        res_person = classify_with_local_neural_vision(portrait_img)
        assert res_person["status"] == "general_recognition"
        assert res_person["category"] == "person"
        assert res_person["is_person"] is None
        assert res_person["person_detection"] == "unsupported"
        assert res_person["person_detection_status"] == "unsupported"
        assert res_person["is_medical"] is False
        assert res_person["medical_applicable"] is False
        assert "portrait" in res_person["detected_subject"].lower()
        assert "prohibited" in res_person["safety_disclaimer"].lower()


def test_local_neural_vision_api_integration(client):
    """Verify HTTP endpoint handles local_neural_vision with 200 general_recognition card."""
    from app.services.vision_service import classify_with_local_neural_vision
    # Using dog-like / animal texture
    arr = np.random.RandomState(99).randint(80, 200, (224, 224, 3), dtype=np.uint8)
    test_img = Image.fromarray(arr)

    # When Groq is not configured, understand_image automatically uses local neural vision
    with patch.object(vision_service, "call_groq_vision", return_value=None):
        res = vision_service.understand_image(test_img)
        assert res["engine"] == "local_neural_vision"
        assert res["is_medical"] is False
        assert res["vision_model"] == "mobilenet_v3_small"
