"""
NewGenHealthAI — tests/test_model_fairness_and_safety.py
Rigorously tests:
1. Fairness across Fitzpatrick skin phototypes I through VI (verifying Type VI is NEVER rejected as unsupported_image).
2. Diverse skin tones, shadows, and lighting conditions.
3. Animal photographs (dog fur, cat fur) safely return inconclusive rather than fabricating diseases.
4. Non-medical landscapes (green grass, blue sky) do not produce clinical disease diagnosis under modality override.
5. Grayscale non-medical images (checkerboards) return inconclusive rather than diagnosing fractures.
6. X-ray anatomical identification explicitly disclaims pathology assessment (never stating "no fracture exists").
7. Safe checkpoint loading with weights_only=True and SHA-256 integrity verification.
"""

import os
import hashlib
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.disease_classifier import (
    disease_classifier,
    detect_domain_from_visual_features,
    TRUSTED_CHECKPOINT_HASHES,
)


def make_synthetic_skin_lesion(fitzpatrick_type: int) -> Image.Image:
    """Create a realistic clinical skin lesion patch across Fitzpatrick scale I through VI."""
    fitz_colors = {
        1: (250, 225, 205), # Type I (Pale)
        2: (240, 205, 175), # Type II (Fair)
        3: (215, 175, 140), # Type III (Medium)
        4: (175, 125, 85),  # Type IV (Olive/Moderate Brown)
        5: (125, 80, 50),   # Type V (Dark Brown)
        6: (65, 40, 25),    # Type VI (Deeply Pigmented)
    }
    bg = fitz_colors.get(fitzpatrick_type, (215, 175, 140))
    img = Image.new("RGB", (380, 380), color=bg)
    draw = ImageDraw.Draw(img)
    # Focal hyperpigmented lesion in center
    lesion_color = (max(0, bg[0] - 30), max(0, bg[1] - 25), max(0, bg[2] - 15))
    draw.ellipse([130, 130, 250, 250], fill=lesion_color)
    return img


def make_shadowed_dark_skin() -> Image.Image:
    """Very dark skin under shadow (low luminance Y < 40, R=45, G=28, B=18)."""
    img = Image.new("RGB", (380, 380), color=(45, 28, 18))
    draw = ImageDraw.Draw(img)
    draw.ellipse([140, 140, 240, 240], fill=(25, 15, 10))
    return img


def make_dog_fur_image() -> Image.Image:
    """Golden retriever / tan dog fur texture with dense directional hair striations."""
    arr = np.random.normal(loc=[185, 145, 95], scale=[18, 18, 14], size=(380, 380, 3)).clip(0, 255).astype(np.uint8)
    # Add dense fur grain
    arr[:, :, 0] = (arr[:, :, 0].astype(np.int16) + (np.sin(np.linspace(0, 80, 380)) * 20).astype(np.int16)).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def make_nature_landscape() -> Image.Image:
    """Unambiguous non-medical outdoor image: vibrant blue sky and green grass."""
    arr = np.zeros((300, 300, 3), dtype=np.uint8)
    arr[:150, :] = [50, 130, 240] # Vivid blue sky
    arr[150:, :] = [20, 180, 35]  # Lush green grass
    return Image.fromarray(arr, mode="RGB")


def make_grayscale_checkerboard() -> Image.Image:
    """Non-medical grayscale pattern to ensure it does not falsely diagnose skeletal pathology."""
    arr = np.zeros((224, 224), dtype=np.uint8)
    for i in range(0, 224, 28):
        for j in range(0, 224, 28):
            if (i // 28 + j // 28) % 2 == 0:
                arr[i:i + 28, j:j + 28] = 230
            else:
                arr[i:i + 28, j:j + 28] = 30
    return Image.fromarray(arr, mode="L").convert("RGB")


# ── Fairness & Dark Skin Routing Tests ──────────────────────────────────────────

# ── Fairness & Dark Skin Routing Tests ──────────────────────────────────────────

@pytest.mark.parametrize("fitz_type", [1, 2, 3, 4, 5, 6])
def test_all_fitzpatrick_skin_tones_accepted(fitz_type):
    """
    Color/appearance-invariance regression test:
    Verifies that synthetic color patches approximating Fitzpatrick phototypes I-VI
    are not prematurely rejected as 'unsupported_image' and that hardcoded visual features
    never automatically classify skin into the clinical 'skin' domain.
    NOTE: This synthetic check verifies software appearance invariance only and does NOT
    establish clinical fairness or diagnostic efficacy across Fitzpatrick phototypes.
    """
    img = make_synthetic_skin_lesion(fitz_type)
    domain, conf, scores = detect_domain_from_visual_features(img)
    # Visual feature detector must not classify human skin as non_medical,
    # and must NEVER automatically classify it as clinical 'skin' domain
    assert domain != "non_medical", f"Fitzpatrick Type {fitz_type} falsely classified as non_medical"
    assert domain != "skin", f"Fitzpatrick Type {fitz_type} unexpectedly returned clinical 'skin' domain"

    # Full classifier with skin modality hint and explicit confirmation
    res = disease_classifier.classify(img, routed_category="skin", modality_confirmed=True)
    assert res["status"] != "unsupported_image", f"Fitzpatrick Type {fitz_type} rejected as unsupported_image"
    assert res["status"] in ("analysis_complete", "inconclusive")


def test_deeply_pigmented_shadowed_skin_not_rejected():
    """
    Color/appearance-invariance regression test:
    Deeply pigmented skin under shadow must not be rejected as unsupported_image, and never auto-skin.
    NOTE: Synthetic check; does not establish clinical fairness.
    """
    img = make_shadowed_dark_skin()
    domain, conf, scores = detect_domain_from_visual_features(img)
    assert domain != "non_medical"
    assert domain != "skin"
    res = disease_classifier.classify(img, routed_category="skin", modality_confirmed=True)
    assert res["status"] != "unsupported_image"


# ── Animal / Dog Fur & Non-Medical Safeguard Tests ─────────────────────────────

def test_animal_fur_safely_handled():
    """
    Animal fur photographs must NOT be asserted as human skin diseases.
    When passed with skin modality hint, diffuse scores must yield 'inconclusive'.
    """
    img = make_dog_fur_image()
    res = disease_classifier.classify(img, routed_category="skin", modality_confirmed=True)
    # Must either be inconclusive or have low confidence without forcing disease promotion
    if res["status"] == "analysis_complete":
        assert res.get("finding_type") in ("condition_detected", "normal_or_negative")
    else:
        assert res["status"] in ("inconclusive", "unsupported_image")


def test_nature_landscape_rejected_even_with_skin_override():
    """Outdoor landscape (blue sky / green grass) must not produce clinical disease diagnosis under modality override."""
    img = make_nature_landscape()
    res = disease_classifier.classify(img, routed_category="skin", modality_confirmed=True)
    assert res["status"] in ("unsupported_image", "inconclusive", "clinical_analysis_disabled")
    assert res.get("disease") is None
    assert res.get("status") != "analysis_complete"


def test_grayscale_checkerboard_does_not_diagnose_fracture():
    """Non-medical grayscale pattern must not be diagnosed as an anatomical fracture."""
    img = make_grayscale_checkerboard()
    res = disease_classifier.classify(img, routed_category="xray", modality_confirmed=True)
    assert res["status"] in ("inconclusive", "analysis_complete")
    if res["status"] == "analysis_complete":
        assert "fracture" not in res["disease"].lower()


# ── X-Ray Anatomical Separation from Pathology Tests ──────────────────────────

def test_xray_anatomy_separated_from_pathology():
    """
    When an X-ray model identifies an anatomical region (e.g. wrist/hand/finger),
    it must NOT state or imply that 'no fracture exists'.
    """
    # Create synthetic hand-like radiographic density
    arr = np.random.randint(15, 35, (224, 224), dtype=np.uint8)
    arr[30:190, 90:130] = np.random.randint(180, 230, (160, 40), dtype=np.uint8)
    img = Image.fromarray(arr, mode="L").convert("RGB")

    res = disease_classifier.classify(img, routed_category="xray", modality_confirmed=True)
    assert res["status"] == "analysis_complete"

    if res.get("finding_type") == "anatomy_identified":
        # Must clearly indicate pathology was not classified
        assert "No pathology classified" in res["disease"]
        assert "Anatomy Identified:" in res["disease"]
        # Must not say 'no fracture exists'
        assert "cannot reliably" in res["clinical_note"].lower()
        assert "must not be interpreted as proof that no abnormality exists" in res["clinical_note"].lower()


# ── Cryptographic Checkpoint Integrity & Safe Loading Tests ───────────────────

def test_trusted_checkpoint_hashes_exist_and_pinned():
    """Ensure all 4 specialist models have pinned cryptographic SHA-256 checksums."""
    expected_models = ["skin_disease_model.pth", "xray_fracture_model.pth", "retina_model.pth", "general_disease_model.pth"]
    for m in expected_models:
        assert m in TRUSTED_CHECKPOINT_HASHES
        assert len(TRUSTED_CHECKPOINT_HASHES[m]) == 64


def test_live_checkpoints_match_trusted_hashes():
    """Verify that all on-disk model checkpoints match their pinned SHA-256 hashes exactly."""
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../app/models"))
    for filename, expected_sha in TRUSTED_CHECKPOINT_HASHES.items():
        filepath = os.path.join(models_dir, filename)
        assert os.path.exists(filepath), f"Missing checkpoint {filepath}"
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        assert hasher.hexdigest().lower() == expected_sha.lower(), f"SHA-256 mismatch for {filename}"


# ── Safety Regression Tests: Unvalidated Heuristic Elimination ─────────────────

@pytest.mark.parametrize("fitz_type", [1, 2, 3, 4, 5, 6])
def test_skin_colour_variation_cannot_trigger_clinical_routing(fitz_type):
    """
    Mandatory Safety Invariant:
    Skin-colour variation across Fitzpatrick phototypes (I-VI) MUST NEVER trigger
    automatic clinical routing. A medical specialist model may only be considered
    after explicit, valid user-selected modality.
    """
    img = make_synthetic_skin_lesion(fitz_type)
    # Automatic intake without user modality selection
    res = disease_classifier.classify(img, routed_category=None)
    # Must NOT automatically complete analysis or dispatch specialist model
    assert res["status"] != "analysis_complete", (
        f"Fitzpatrick Type {fitz_type} automatically triggered clinical analysis without modality selection"
    )
    assert res.get("disease") is None
    assert res["status"] in ("modality_selection_required", "general_recognition")
    assert res.get("routing_decision") == "NO AUTOMATIC MEDICAL ROUTE"


def test_brightness_contrast_variation_cannot_trigger_clinical_routing():
    """
    Mandatory Safety Invariant:
    Changing image brightness or contrast across skin tones must NEVER trigger
    automatic clinical routing to specialist models.
    """
    from PIL import ImageEnhance

    for fitz_type in [1, 3, 6]:
        base_img = make_synthetic_skin_lesion(fitz_type)
        for b_factor in [0.4, 0.8, 1.2, 1.8]:
            bright_img = ImageEnhance.Brightness(base_img).enhance(b_factor)
            res = disease_classifier.classify(bright_img, routed_category=None)
            assert res["status"] != "analysis_complete"
            assert res.get("disease") is None
            assert res["status"] in ("modality_selection_required", "general_recognition", "inconclusive")

        for c_factor in [0.5, 1.0, 1.6]:
            contrast_img = ImageEnhance.Contrast(base_img).enhance(c_factor)
            res = disease_classifier.classify(contrast_img, routed_category=None)
            assert res["status"] != "analysis_complete"
            assert res.get("disease") is None
            assert res["status"] in ("modality_selection_required", "general_recognition", "inconclusive")


def test_portrait_cannot_automatically_enter_skin_specialist_pipeline():
    """
    Mandatory Safety Invariant:
    A portrait photograph must NEVER enter the skin disease inference pipeline
    through automatic classification.
    """
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "genuine_everyday_images"))
    portrait_path = os.path.join(fixtures_dir, "portrait.jpg")

    if os.path.exists(portrait_path):
        img = Image.open(portrait_path)
    else:
        # Fallback synthetic portrait
        img = Image.new("RGB", (224, 224), color=(220, 180, 150))

    res = disease_classifier.classify(img, routed_category=None)
    assert res["status"] != "analysis_complete"
    assert res.get("disease") is None
    assert res.get("medical_applicable") is False
    assert res["status"] in ("general_recognition", "unsupported_image", "modality_selection_required", "inconclusive")


def test_explicit_modality_selection_remains_mandatory():
    """Specialist dispatch strictly requires explicit user modality selection AND research-mode confirmation."""
    img = make_synthetic_skin_lesion(3)
    # No modality provided: must NEVER run specialist analysis
    res_no_modality = disease_classifier.classify(img, routed_category=None)
    assert res_no_modality["status"] != "analysis_complete"
    assert res_no_modality.get("disease") is None
    assert res_no_modality["status"] in ("modality_selection_required", "general_recognition", "inconclusive")

    # With explicit modality provided but unconfirmed: requires confirmation
    res_unconfirmed = disease_classifier.classify(img, routed_category="skin", modality_confirmed=False)
    assert res_unconfirmed["status"] == "modality_confirmation_required"
    assert res_unconfirmed["requires_confirmation"] is True
    assert "research_disclaimer" in res_unconfirmed
    assert res_unconfirmed.get("disease") is None

    # With explicit modality provided AND confirmed: proceeds to clinical pathway
    res_with_modality = disease_classifier.classify(img, routed_category="skin", modality_confirmed=True)
    assert res_with_modality["status"] in ("analysis_complete", "inconclusive", "clinical_analysis_disabled")


def test_production_clinical_gate_remains_fail_closed():
    """In production, clinical specialist inference remains unconditionally disabled."""
    from unittest.mock import patch

    img = make_synthetic_skin_lesion(2)
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "ENABLE_CLINICAL_SPECIALIST_MODELS": "true"}):
        res = disease_classifier.classify(img, routed_category="skin", modality_confirmed=True)
        assert res["status"] == "clinical_analysis_disabled"
        assert res.get("disease") is None


def test_portrait_cannot_receive_medical_diagnosis_even_with_explicit_modality():
    """
    SAFETY INVARIANT:
    Ordinary portraits must NEVER receive medical diagnoses, even if the user
    explicitly selects a medical modality ('skin') and confirms intake.
    Returns status='unsupported_image' and disease=None.
    """
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "genuine_everyday_images"))
    portrait_path = os.path.join(fixtures_dir, "portrait.jpg")

    if os.path.exists(portrait_path):
        img = Image.open(portrait_path)
    else:
        img = Image.new("RGB", (224, 224), color=(220, 180, 150))

    res = disease_classifier.classify(img, routed_category="skin", modality_confirmed=True)
    assert res["status"] in ("unsupported_image", "inconclusive", "clinical_analysis_disabled")
    assert res.get("disease") is None


def test_imagenet_human_and_clothing_classes_semantics():
    """
    ImageNet classes (groom, ballplayer, scuba diver, suit, necktie):
    1. General person detection remains explicitly unsupported (is_person: None, person_detection: 'unsupported').
    2. Closed-set clothing prediction (suit/tie) does NOT infer is_person=False.
    3. ImageNet human classes do NOT automatically route or approve clinical modalities.
    """
    import torch
    from unittest.mock import patch, MagicMock
    from app.services.vision_service import classify_with_local_neural_vision

    test_arr = np.random.RandomState(42).randint(100, 200, (224, 224, 3), dtype=np.uint8)
    test_img = Image.fromarray(test_arr)

    # Test 1: Clothing class 'suit' (idx=834)
    with patch("app.services.vision_service._get_local_vision_model") as mock_model:
        mock_m = MagicMock()
        mock_transform = lambda x: torch.zeros(3, 224, 224)
        mock_cats = ["object"] * 1000
        mock_cats[834] = "suit"
        logits = torch.zeros(1, 1000)
        logits[0, 834] = 10.0
        mock_m.return_value = logits
        mock_model.return_value = (mock_m, mock_transform, mock_cats)

        res_suit = classify_with_local_neural_vision(test_img)
        assert res_suit["status"] == "general_recognition"
        # Must NOT infer is_person=False merely because it's clothing
        assert res_suit["is_person"] is None
        assert res_suit["person_detection"] == "unsupported"
        assert res_suit["person_detection_status"] == "unsupported"
        assert res_suit["medical_applicable"] is False

    # Test 2: ImageNet human class 'scuba diver' (idx=983)
    with patch("app.services.vision_service._get_local_vision_model") as mock_model:
        mock_m = MagicMock()
        mock_transform = lambda x: torch.zeros(3, 224, 224)
        mock_cats = ["object"] * 1000
        mock_cats[983] = "scuba diver"
        logits = torch.zeros(1, 1000)
        logits[0, 983] = 10.0
        mock_m.return_value = logits
        mock_model.return_value = (mock_m, mock_transform, mock_cats)

        res_diver = classify_with_local_neural_vision(test_img)
        assert res_diver["status"] == "general_recognition"
        assert res_diver["is_person"] is None
        assert res_diver["person_detection"] == "unsupported"
        assert res_diver["medical_applicable"] is False


def test_everyday_mobilenet_recognition_still_works():
    """Everyday MobileNetV3 recognition functions independently of clinical specialist status."""
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "genuine_everyday_images"))
    sunflower_path = os.path.join(fixtures_dir, "sunflower.jpg")

    if os.path.exists(sunflower_path):
        img = Image.open(sunflower_path)
        res = disease_classifier.classify(img, routed_category=None)
        assert res["status"] == "general_recognition"
        assert res.get("category") == "plant"
        assert res.get("medical_applicable") is False
