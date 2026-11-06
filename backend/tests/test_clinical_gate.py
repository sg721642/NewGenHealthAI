"""
NewGenHealthAI — tests/test_clinical_gate.py
Verification of the production clinical-inference feature gate (Phase 4A):
- Disabled by default in production: explicit modality selection returns 'clinical_analysis_disabled'
- Zero specialist models loaded or invoked when gate is closed
- General everyday image recognition remains fully operational
- When explicitly enabled in local research mode, specialist inference functions normally
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import is_clinical_specialist_enabled

from app.core.dependencies import get_current_user
from app.models.message import User

CLINICAL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "genuine_clinical_images"))
EVERYDAY_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "genuine_everyday_images"))


@pytest.fixture
def auth_user():
    user = User(id=777, username="clinical_tester", hashed_password="pw")
    setattr(user, "user_id", 777)
    return user


@pytest.fixture
def client(auth_user):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)


def test_clinical_gate_disabled_blocks_specialist_inference(client):
    """
    When ENABLE_CLINICAL_SPECIALIST_MODELS is false:
    - Explicit modality='skin' request is rejected with status 'clinical_analysis_disabled'
    - Zero specialist models are invoked
    - Response clearly indicates unvalidated specialist models are disabled in production
    """
    img_path = os.path.join(CLINICAL_DIR, "ISIC_0000000.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    with patch.dict(os.environ, {"ENABLE_CLINICAL_SPECIALIST_MODELS": "false"}):
        with patch("app.services.disease_classifier.MedicalModel.predict") as mock_predict:
            resp = client.post(
                "/api/v1/analyze-image",
                data={"modality": "skin"},
                files={"file": ("ISIC_0000000.jpg", img_bytes, "image/jpeg")},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "clinical_analysis_disabled"
            assert data["success"] is False
            assert data["medical_applicable"] is False
            assert "disabled in this release" in data["message"].lower()
            assert data["clinical_governance_status"] == "NOT_CLINICALLY_VALIDATED"
            mock_predict.assert_not_called()


def test_clinical_gate_disabled_preserves_everyday_general_recognition(client):
    """
    When ENABLE_CLINICAL_SPECIALIST_MODELS is false:
    - Everyday non-medical recognition (sunflower, car, apple) remains 100% functional
    - Ordinary photo recognition does NOT use clinical specialist models
    """
    img_path = os.path.join(EVERYDAY_DIR, "sunflower.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    with patch.dict(os.environ, {"ENABLE_CLINICAL_SPECIALIST_MODELS": "false"}):
        resp = client.post(
            "/api/v1/analyze-image",
            data={"modality": "auto"},
            files={"file": ("sunflower.jpg", img_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "general_recognition"
        assert data["success"] is True
        assert data["medical_applicable"] is False
        assert data["detected_category"] == "plant"


def test_clinical_gate_enabled_in_research_mode_permits_specialist(client):
    """
    When ENABLE_CLINICAL_SPECIALIST_MODELS is true:
    - Explicit modality='skin' runs the prototype specialist model
    - Returns analysis_complete with uncalibrated score and disclaimer
    """
    img_path = os.path.join(CLINICAL_DIR, "ISIC_0000000.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    with patch.dict(os.environ, {"ENABLE_CLINICAL_SPECIALIST_MODELS": "true"}):
        resp = client.post(
            "/api/v1/analyze-image",
            data={"modality": "skin", "modality_confirmed": "true"},
            files={"file": ("ISIC_0000000.jpg", img_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "analysis_complete"
        assert data["success"] is True
        assert data["category"] == "skin"
        assert data["medical_applicable"] is True
        assert "unvalidated" in data["score_interpretation"].lower()
        assert "clinical_warning" in data


def test_clinical_gate_string_parsing():
    """Verify boolean string parsing for ENABLE_CLINICAL_SPECIALIST_MODELS in non-prod."""
    for false_val in ["false", "FALSE", "0", "no", "NO", ""]:
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "ENABLE_CLINICAL_SPECIALIST_MODELS": false_val}):
            assert is_clinical_specialist_enabled() is False

    for true_val in ["true", "TRUE", "1", "yes", "YES"]:
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "ENABLE_CLINICAL_SPECIALIST_MODELS": true_val}):
            assert is_clinical_specialist_enabled() is True


def test_production_rejects_research_override_when_unapproved():
    """
    In production (ENVIRONMENT=production), research-mode flags
    (ENABLE_CLINICAL_SPECIALIST_MODELS=true) must be strictly REJECTED.
    """
    for research_flag in ["true", "1", "yes", "TRUE"]:
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "ENABLE_CLINICAL_SPECIALIST_MODELS": research_flag,
            "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": "",
        }):
            assert is_clinical_specialist_enabled() is False


def test_production_governance_approval_fail_closed(tmp_path):
    """
    In production, specialist models require explicit CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL
    AND a documented authorized clinical approval record with clinical validation.
    Naked flags, missing, empty, or unvalidated records must fail closed (False).
    """
    # 1. Absent or empty fails closed
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
        assert is_clinical_specialist_enabled() is False

    # 2. Naked truthy governance flags WITHOUT authorized record fail closed
    for approved in ["true", "TRUE", "1", "yes", "YES"]:
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": approved,
        }):
            assert is_clinical_specialist_enabled() is False

    # 3. Unvalidated / not approved clinical record fails closed
    unvalidated_record = tmp_path / "unvalidated_governance.json"
    unvalidated_record.write_text(json.dumps({
        "approval_decision": "NOT_APPROVED",
        "clinical_validation_status": "NOT_CLINICALLY_VALIDATED",
        "authorized_signoff": ""
    }))
    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": "true",
        "CLINICAL_GOVERNANCE_RECORD_PATH": str(unvalidated_record),
    }):
        assert is_clinical_specialist_enabled() is False

    # 4. Syntactically valid, approval-shaped JSON record with all flags true MUST STILL FAIL CLOSED
    approval_shaped_record = tmp_path / "approval_shaped_record.json"
    approval_shaped_record.write_text(json.dumps({
        "approval_decision": "APPROVED",
        "clinical_validation_status": "CLINICALLY_VALIDATED",
        "authorized_signoff": "unverified_signer_placeholder"
    }))
    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "ENABLE_CLINICAL_SPECIALIST_MODELS": "true",
        "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": "true",
        "CLINICAL_GOVERNANCE_RECORD_PATH": str(approval_shaped_record),
    }):
        # In current release, production clinical specialist inference is unconditionally disabled
        assert is_clinical_specialist_enabled() is False


def test_development_defaults_to_false_when_absent():
    """
    In development (ENVIRONMENT=development), absent or malformed variables default to False.
    Specialist models may only be activated by deliberate research flag.
    """
    # Absent
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
        assert is_clinical_specialist_enabled() is False

    # Malformed
    for malformed in ["foo", "disabled", "0", "false", "no"]:
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "ENABLE_CLINICAL_SPECIALIST_MODELS": malformed,
        }):
            assert is_clinical_specialist_enabled() is False

    # Deliberately enabled
    with patch.dict(os.environ, {
        "ENVIRONMENT": "development",
        "ENABLE_CLINICAL_SPECIALIST_MODELS": "true",
    }):
        assert is_clinical_specialist_enabled() is True


def test_production_endpoint_rejects_research_override(client):
    """
    Live HTTP endpoint /api/v1/analyze-image under ENVIRONMENT=production
    rejects research override ENABLE_CLINICAL_SPECIALIST_MODELS=true with
    status 'clinical_analysis_disabled'.
    """
    img_path = os.path.join(CLINICAL_DIR, "ISIC_0000000.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "ENABLE_CLINICAL_SPECIALIST_MODELS": "true",
        "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": "",
    }):
        resp = client.post(
            "/api/v1/analyze-image",
            data={"modality": "skin"},
            files={"file": ("ISIC_0000000.jpg", img_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "clinical_analysis_disabled"
        assert data["success"] is False
        assert data["clinical_governance_status"] == "NOT_CLINICALLY_VALIDATED"


def test_absent_environment_fails_closed():
    """
    An absent or empty ENVIRONMENT/ENV must FAIL CLOSED.
    Even if ENABLE_CLINICAL_SPECIALIST_MODELS=true is passed, an unconfigured
    environment must NEVER activate specialist models.
    """
    for empty_env in ["", "  "]:
        with patch.dict(os.environ, {
            "ENVIRONMENT": empty_env,
            "ENV": empty_env,
            "ENABLE_CLINICAL_SPECIALIST_MODELS": "true",
        }):
            assert is_clinical_specialist_enabled() is False

    # Completely cleared environment variables
    with patch.dict(os.environ, {"ENABLE_CLINICAL_SPECIALIST_MODELS": "true"}, clear=True):
        assert is_clinical_specialist_enabled() is False


def test_unknown_environment_fails_closed():
    """
    Unrecognized environments (staging, preview, qa, cluster, invalid) must FAIL CLOSED.
    Local research mode requires an explicitly recognized non-production environment.
    """
    for unknown in ["staging", "qa", "preview", "cluster", "production-us-east", "foo", "unknown"]:
        with patch.dict(os.environ, {
            "ENVIRONMENT": unknown,
            "ENABLE_CLINICAL_SPECIALIST_MODELS": "true",
        }):
            assert is_clinical_specialist_enabled() is False


def test_prod_alias_governance_approval_boundary(tmp_path):
    """
    Verify ENVIRONMENT='prod' enforces identical boundary as 'production':
    - Research override is rejected
    - Naked governance approval flag fails closed
    - Documented authorized clinical signoff is strictly required
    """
    # 1. Research override rejected
    with patch.dict(os.environ, {
        "ENVIRONMENT": "prod",
        "ENABLE_CLINICAL_SPECIALIST_MODELS": "true",
        "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": "",
    }):
        assert is_clinical_specialist_enabled() is False

    # 2. Naked governance approval fails closed
    for approved in ["true", "TRUE", "1", "yes", "YES"]:
        with patch.dict(os.environ, {
            "ENVIRONMENT": "prod",
            "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": approved,
        }):
            assert is_clinical_specialist_enabled() is False

    # 3. Approval-shaped record with all flags true in 'prod' MUST STILL FAIL CLOSED
    prod_approval_record = tmp_path / "prod_approval_record.json"
    prod_approval_record.write_text(json.dumps({
        "approval_decision": "APPROVED",
        "clinical_validation_status": "CLINICALLY_VALIDATED",
        "authorized_signoff": "unverified_signer_placeholder"
    }))
    with patch.dict(os.environ, {
        "ENVIRONMENT": "prod",
        "ENABLE_CLINICAL_SPECIALIST_MODELS": "true",
        "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": "true",
        "CLINICAL_GOVERNANCE_RECORD_PATH": str(prod_approval_record),
    }):
        assert is_clinical_specialist_enabled() is False


def test_adversarial_production_gate_full_bypass_attempt(client, tmp_path):
    """
    Adversarial test: Even when ALL possible bypass flags are active
    (ENABLE_CLINICAL_SPECIALIST_MODELS=true, CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL=true,
    valid-looking approved JSON record) in both 'production' and 'prod':
    1. Specialist clinical inference remains unconditionally disabled.
    2. Zero specialist checkpoints are loaded or invoked.
    3. Explicit modality selection ('skin', 'xray', 'retina') cannot bypass the gate.
    4. Ordinary non-medical MobileNet recognition continues working seamlessly.
    """
    approval_record = tmp_path / "adversarial_approval.json"
    approval_record.write_text(json.dumps({
        "approval_decision": "APPROVED",
        "clinical_validation_status": "CLINICALLY_VALIDATED",
        "authorized_signoff": "adversarial_tester"
    }))

    img_path = os.path.join(CLINICAL_DIR, "ISIC_0000000.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    for prod_env in ["production", "prod"]:
        with patch.dict(os.environ, {
            "ENVIRONMENT": prod_env,
            "ENABLE_CLINICAL_SPECIALIST_MODELS": "true",
            "CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL": "true",
            "CLINICAL_GOVERNANCE_RECORD_PATH": str(approval_record),
        }):
            assert is_clinical_specialist_enabled() is False

            # Explicit modality='skin' on genuine clinical fixture cannot bypass production gate
            with patch("app.services.disease_classifier.MedicalModel.predict") as mock_predict, \
                 patch("app.services.disease_classifier.MedicalModel.load") as mock_load:
                resp = client.post(
                    "/api/v1/analyze-image",
                    data={"modality": "skin"},
                    files={"file": ("ISIC_0000000.jpg", img_bytes, "image/jpeg")},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "clinical_analysis_disabled"
                assert data["success"] is False
                assert data["medical_applicable"] is False
                assert data["clinical_governance_status"] == "NOT_CLINICALLY_VALIDATED"
                assert "disabled in this release" in data["message"].lower()
                mock_predict.assert_not_called()
                mock_load.assert_not_called()

            # Verify ordinary non-medical recognition continues working under the same production env
            sunflower_path = os.path.join(EVERYDAY_DIR, "sunflower.jpg")
            with open(sunflower_path, "rb") as sf:
                sf_bytes = sf.read()
            resp_everyday = client.post(
                "/api/v1/analyze-image",
                data={"modality": "auto"},
                files={"file": ("sunflower.jpg", sf_bytes, "image/jpeg")},
            )
            assert resp_everyday.status_code == 200
            data_ev = resp_everyday.json()
            assert data_ev["status"] == "general_recognition"
            assert data_ev["success"] is True
            assert data_ev["medical_applicable"] is False
