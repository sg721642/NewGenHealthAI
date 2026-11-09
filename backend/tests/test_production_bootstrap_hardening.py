"""
NewGenHealthAI — tests/test_production_bootstrap_hardening.py
Verification of production-bootstrap hardening and fail-closed security invariants:
1. Production startup strictly rejects a missing or short SESSION_SECRET_KEY (< 32 characters)
2. Production startup succeeds with a valid session secret (>= 32 characters)
3. Secure session cookies (https_only=True) are active under ENVIRONMENT=production
4. Clinical specialist inference remains unconditionally disabled in production
5. Everyday MobileNetV3 image recognition continues functioning normally
6. Backend health endpoint returns HTTP 200 OK
7. Local development workflows remain possible by explicitly overriding ENVIRONMENT=development
"""

import os
import subprocess
import sys
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.models.message import User
from app.core.dependencies import get_current_user

# Path to python interpreter in the current virtual environment
PYTHON_EXE = sys.executable

EVERYDAY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "fixtures", "genuine_everyday_images")
)
SYNTHETIC_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_images")
)


def test_production_startup_rejects_missing_session_secret():
    """
    Under ENVIRONMENT=production, if SESSION_SECRET_KEY is absent or empty,
    FastAPI startup must fail immediately with a RuntimeError.
    """
    cmd = [
        PYTHON_EXE,
        "-c",
        (
            "import os; "
            "os.environ['ENVIRONMENT'] = 'production'; "
            "os.environ['SESSION_SECRET_KEY'] = ''; "
            "os.environ['SESSION_SECRET'] = ''; "
            "from app.main import app"
        ),
    ]
    env = dict(os.environ)
    env["ENVIRONMENT"] = "production"
    env["SESSION_SECRET_KEY"] = ""
    env["SESSION_SECRET"] = ""

    proc = subprocess.run(
        cmd,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "SESSION_SECRET_KEY must be configured with at least 32 characters in production." in proc.stderr


def test_production_startup_rejects_short_session_secret():
    """
    Under ENVIRONMENT=production, if SESSION_SECRET_KEY is shorter than 32 characters,
    FastAPI startup must fail immediately with a RuntimeError.
    """
    cmd = [
        PYTHON_EXE,
        "-c",
        "import os; os.environ['ENVIRONMENT'] = 'production'; os.environ['SESSION_SECRET_KEY'] = 'short_key_under_32_chars'; from app.main import app",
    ]
    env = dict(os.environ)
    env["ENVIRONMENT"] = "production"
    env["SESSION_SECRET_KEY"] = "short_key_under_32_chars"

    proc = subprocess.run(
        cmd,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "SESSION_SECRET_KEY must be configured with at least 32 characters in production." in proc.stderr


def test_production_startup_succeeds_with_valid_session_secret():
    """
    Under ENVIRONMENT=production, if SESSION_SECRET_KEY is at least 32 characters,
    FastAPI startup must succeed without throwing RuntimeError.
    """
    cmd = [
        PYTHON_EXE,
        "-c",
        "import os; os.environ['ENVIRONMENT'] = 'production'; os.environ['SESSION_SECRET_KEY'] = 'production_test_secret_key_minimum_32_chars!'; from app.main import app; print('BOOT_SUCCESS')",
    ]
    env = dict(os.environ)
    env["ENVIRONMENT"] = "production"
    env["SESSION_SECRET_KEY"] = "production_test_secret_key_minimum_32_chars!"

    proc = subprocess.run(
        cmd,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "BOOT_SUCCESS" in proc.stdout


def test_production_secure_session_cookies_enabled():
    """
    Under ENVIRONMENT=production, Starlette SessionMiddleware must have https_only=True
    to ensure session cookies are only transmitted over TLS.
    """
    cmd = [
        PYTHON_EXE,
        "-c",
        (
            "import os; "
            "os.environ['ENVIRONMENT'] = 'production'; "
            "os.environ['SESSION_SECRET_KEY'] = 'production_test_secret_key_minimum_32_chars!'; "
            "from app.main import app; "
            "from starlette.middleware.sessions import SessionMiddleware; "
            "session_mw = [m for m in app.user_middleware if m.cls is SessionMiddleware]; "
            "assert len(session_mw) == 1, 'SessionMiddleware not found'; "
            "assert session_mw[0].kwargs.get('https_only') is True, 'https_only must be True in production'; "
            "print('COOKIE_SECURE_VERIFIED')"
        ),
    ]
    env = dict(os.environ)
    env["ENVIRONMENT"] = "production"
    env["SESSION_SECRET_KEY"] = "production_test_secret_key_minimum_32_chars!"

    proc = subprocess.run(
        cmd,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "COOKIE_SECURE_VERIFIED" in proc.stdout


def test_production_clinical_specialist_inference_unconditionally_disabled():
    """
    Under ENVIRONMENT=production:
    Even if ENABLE_CLINICAL_SPECIALIST_MODELS=true or CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL=true
    is set, the clinical specialist gate must fail closed and return False.
    """
    cmd = [
        PYTHON_EXE,
        "-c",
        (
            "import os; "
            "os.environ['ENVIRONMENT'] = 'production'; "
            "os.environ['ENABLE_CLINICAL_SPECIALIST_MODELS'] = 'true'; "
            "os.environ['CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL'] = 'true'; "
            "from app.core.config import is_clinical_specialist_enabled; "
            "assert is_clinical_specialist_enabled() is False, 'Clinical specialist gate must be False in production'; "
            "print('GATE_FAIL_CLOSED_VERIFIED')"
        ),
    ]
    env = dict(os.environ)
    env["ENVIRONMENT"] = "production"
    env["ENABLE_CLINICAL_SPECIALIST_MODELS"] = "true"
    env["CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL"] = "true"

    proc = subprocess.run(
        cmd,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "GATE_FAIL_CLOSED_VERIFIED" in proc.stdout


def test_production_health_endpoint_and_mobilenet_recognition():
    """
    Under ENVIRONMENT=production with a valid session secret:
    - GET /api/v1/health returns HTTP 200 with status 'healthy'
    - Everyday image recognition using MobileNetV3 continues to function normally
    - Specialist analysis request fails closed with 'clinical_analysis_disabled'
    """
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "SESSION_SECRET_KEY": "production_test_secret_key_minimum_32_chars!",
            "OFFLINE_MODE": "true",
        },
    ):
        from app.main import app

        auth_user = User(id=999, username="prod_evaluator", hashed_password="pw")
        setattr(auth_user, "user_id", 999)
        app.dependency_overrides[get_current_user] = lambda: auth_user

        try:
            with TestClient(app) as client:
                # 1. Verify health endpoint
                health_resp = client.get("/api/v1/health")
                assert health_resp.status_code == 200
                assert health_resp.json().get("status") == "healthy"

                # 2. Verify everyday MobileNetV3 recognition works
                sunflower_path = os.path.join(EVERYDAY_DIR, "sunflower.jpg")
                with open(sunflower_path, "rb") as f:
                    img_bytes = f.read()

                img_resp = client.post(
                    "/api/v1/analyze-image",
                    data={"modality": "auto"},
                    files={"file": ("sunflower.jpg", img_bytes, "image/jpeg")},
                )
                assert img_resp.status_code == 200
                img_data = img_resp.json()
                assert img_data["status"] == "general_recognition"
                assert img_data["success"] is True
                assert img_data["medical_applicable"] is False
                assert img_data.get("detected_category") == "plant"

                # 3. Verify clinical specialist request is disabled in production
                skin_test_path = os.path.join(SYNTHETIC_DIR, "medical_skin_lesion.jpg")
                with open(skin_test_path, "rb") as f:
                    skin_bytes = f.read()

                clin_resp = client.post(
                    "/api/v1/analyze-image",
                    data={"modality": "skin"},
                    files={"file": ("medical_skin_lesion.jpg", skin_bytes, "image/jpeg")},
                )
                assert clin_resp.status_code == 200
                clin_data = clin_resp.json()
                assert clin_data["status"] == "clinical_analysis_disabled"
                assert clin_data["clinical_governance_status"] == "NOT_CLINICALLY_VALIDATED"
                assert clin_data["medical_applicable"] is False
        finally:
            app.dependency_overrides.pop(get_current_user, None)


def test_development_override_preserves_local_workflows():
    """
    Explicitly overriding ENVIRONMENT=development:
    - Allows local development workflows without requiring a 32-character session secret
    - Allows deliberate opt-in to research models via ENABLE_CLINICAL_SPECIALIST_MODELS=true
    """
    cmd = [
        PYTHON_EXE,
        "-c",
        (
            "import os; "
            "os.environ['ENVIRONMENT'] = 'development'; "
            "os.environ['SESSION_SECRET_KEY'] = 'dev_key'; "
            "os.environ['ENABLE_CLINICAL_SPECIALIST_MODELS'] = 'true'; "
            "from app.main import app; "
            "from app.core.config import is_clinical_specialist_enabled; "
            "assert is_clinical_specialist_enabled() is True, 'Research mode opt-in must work in development'; "
            "print('DEV_OVERRIDE_VERIFIED')"
        ),
    ]
    env = dict(os.environ)
    env["ENVIRONMENT"] = "development"
    env["SESSION_SECRET_KEY"] = "dev_key"
    env["ENABLE_CLINICAL_SPECIALIST_MODELS"] = "true"

    proc = subprocess.run(
        cmd,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "DEV_OVERRIDE_VERIFIED" in proc.stdout
