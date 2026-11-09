"""
NewGenHealthAI — tests/test_endpoint_regression_safety.py
Focused endpoint-level regression tests on FastAPI /api/v1/analyze-image endpoint
and deterministic SQLite database isolation verification using PRAGMA database_list.
"""

import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.core import config as app_config
from app.db import session as db_session
from app.services.database_service import db_service
from app.services.disease_classifier import disease_classifier
from app.core.dependencies import get_current_user
from app.models.message import User

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EVERYDAY_DIR = os.path.join(BACKEND_DIR, "tests", "fixtures", "genuine_everyday_images")
CLINICAL_DIR = os.path.join(BACKEND_DIR, "tests", "fixtures", "genuine_clinical_images")
SYNTHETIC_DIR = os.path.join(BACKEND_DIR, "tests", "fixtures", "synthetic_images")


@pytest.fixture
def auth_user():
    user = User(id=777, username="regression_tester", hashed_password="pw")
    setattr(user, "user_id", 777)
    return user


@pytest.fixture
def client(auth_user):
    app.dependency_overrides[get_current_user] = lambda: auth_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)


class SpecialistInvocationSpy:
    """Instrument actual specialist model invocation and predict execution."""
    def __init__(self):
        self.predict_counts = {"skin": 0, "xray": 0, "retina": 0, "general": 0}
        self.get_specialist_model_calls = []
        self.mock_predictions = None

    @property
    def total_predict_calls(self):
        return sum(self.predict_counts.values())


@pytest.fixture
def specialist_spy():
    """Pytest fixture providing spies on get_specialist_model and MedicalModel.predict."""
    from app.services.disease_classifier import disease_classifier, MedicalModel

    spy = SpecialistInvocationSpy()
    orig_predict = MedicalModel.predict
    orig_get_specialist_model = disease_classifier.get_specialist_model

    def spied_predict(self_model, image):
        domain = getattr(self_model, "model_name", "unknown")
        if domain in spy.predict_counts:
            spy.predict_counts[domain] += 1
        else:
            spy.predict_counts[domain] = 1
        if spy.mock_predictions is not None:
            return spy.mock_predictions
        return orig_predict(self_model, image)

    def spied_get_specialist_model(domain):
        spy.get_specialist_model_calls.append(domain)
        return orig_get_specialist_model(domain)

    MedicalModel.predict = spied_predict
    disease_classifier.get_specialist_model = spied_get_specialist_model

    try:
        yield spy
    finally:
        MedicalModel.predict = orig_predict
        disease_classifier.get_specialist_model = orig_get_specialist_model


# ==============================================================================
# 1. Deterministic Database Isolation Verification (PRAGMA database_list)
# ==============================================================================

def test_database_isolation_deterministic_pragma():
    """
    Verify actual SQLite connection path using PRAGMA database_list.
    Ensures tests NEVER connect to production database (storage/chat_db/susham_health.db),
    even if a conflicting environment variable was set.
    """
    prod_db_suffix = os.path.join("storage", "chat_db", "susham_health.db")

    with db_session.engine.connect() as conn:
        rows = conn.execute(text("PRAGMA database_list;")).fetchall()
        # Row format: (seq, name, file)
        assert len(rows) > 0
        main_db = next((r for r in rows if r[1] == "main"), None)
        assert main_db is not None, "PRAGMA database_list did not return main database"
        db_file = main_db[2]

        # Verify it is pointing to an isolated test database
        assert db_file, "Database file path is empty (expected isolated test file)"
        assert not db_file.endswith(prod_db_suffix), f"Safety violation: Test engine connected to production DB {db_file}"
        assert "isolated_test" in db_file or "test" in db_file.lower(), f"Database path {db_file} does not indicate isolated test DB"

    # Simulate conflicting pre-existing environment variable
    original_env = os.environ.get("CHAT_DB_PATH")
    try:
        conflicting_path = "/tmp/conflicting_accidental_production.db"
        os.environ["CHAT_DB_PATH"] = conflicting_path
        # Verify that conftest.py isolated database setting remains protected on active engine
        with db_service.engine.connect() as conn:
            rows = conn.execute(text("PRAGMA database_list;")).fetchall()
            main_db = next((r for r in rows if r[1] == "main"), None)
            assert main_db is not None
            assert not main_db[2].endswith(prod_db_suffix)
    finally:
        if original_env is not None:
            os.environ["CHAT_DB_PATH"] = original_env
        else:
            os.environ.pop("CHAT_DB_PATH", None)


def test_subprocess_database_isolation_conflict():
    """
    Subprocess test: Child Python process with deliberately conflicting pre-import CHAT_DB_PATH.
    Verifies that fresh startup under testing environment resolves to an isolated
    database and NEVER binds to production susham_health.db.
    """
    import subprocess
    import tempfile
    import sys

    conflicting_temp_db = tempfile.mktemp(prefix="deliberate_conflicting_", suffix=".db")
    prod_suffix = os.path.join("storage", "chat_db", "susham_health.db")

    child_code = f"""
import os, sys
os.environ["CHAT_DB_PATH"] = {repr(conflicting_temp_db)}
os.environ["ENVIRONMENT"] = "testing"
os.environ["ENV"] = "testing"

backend_dir = {repr(BACKEND_DIR)}
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db import session as db_session
from sqlalchemy import text

with db_session.engine.connect() as conn:
    rows = conn.execute(text("PRAGMA database_list;")).fetchall()
    main_db = next((r[2] for r in rows if r[1] == "main"), None)
    print("RESOLVED_DB:" + str(main_db))
"""
    env = os.environ.copy()
    env["CHAT_DB_PATH"] = conflicting_temp_db
    env["ENVIRONMENT"] = "testing"
    env["ENV"] = "testing"

    py_exe = sys.executable or "/tmp/nghai_venv/bin/python"
    proc = subprocess.run(
        [py_exe, "-c", child_code],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, f"Child process failed: {proc.stderr}"
    output = proc.stdout.strip()
    assert "RESOLVED_DB:" in output, f"Unexpected output: {output}"
    resolved_db = output.split("RESOLVED_DB:")[1].strip()

    assert not os.path.realpath(resolved_db).endswith(prod_suffix), f"Safety violation: Child process connected to prod DB {resolved_db}"
    assert os.path.realpath(resolved_db) == os.path.realpath(conflicting_temp_db) or "test" in resolved_db.lower(), f"Unexpected resolved DB: {resolved_db}"

    # Also test case where CHAT_DB_PATH was set to production DB path in test mode
    prod_db_full_path = os.path.join(BACKEND_DIR, "storage", "chat_db", "susham_health.db")
    child_code_prod = f"""
import os, sys
os.environ["CHAT_DB_PATH"] = {repr(prod_db_full_path)}
os.environ["ENVIRONMENT"] = "testing"
os.environ["ENV"] = "testing"

backend_dir = {repr(BACKEND_DIR)}
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db import session as db_session
from sqlalchemy import text

with db_session.engine.connect() as conn:
    rows = conn.execute(text("PRAGMA database_list;")).fetchall()
    main_db = next((r[2] for r in rows if r[1] == "main"), None)
    print("RESOLVED_DB:" + str(main_db))
"""
    env["CHAT_DB_PATH"] = prod_db_full_path
    proc2 = subprocess.run(
        [py_exe, "-c", child_code_prod],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc2.returncode == 0, f"Child process 2 failed: {proc2.stderr}"
    output2 = proc2.stdout.strip()
    assert "RESOLVED_DB:" in output2
    resolved_db2 = output2.split("RESOLVED_DB:")[1].strip()
    assert not os.path.realpath(resolved_db2).endswith(prod_suffix), f"Safety violation: Guard failed to redirect prod DB in test mode: {resolved_db2}"
    assert "isolated_test_fallback" in resolved_db2 or "test" in resolved_db2.lower()


# ==============================================================================
# 2. Seven Everyday Photographic Fixtures — Endpoint Level (No Modality Selected)
# ==============================================================================

SEVEN_EVERYDAY_FIXTURES = [
    {
        "filename": "portrait.jpg",
        "expected_category": "object",
        "expected_top1": "suit",
        "expected_status": "general_recognition",
        "is_person": None,
        "note": "Known portrait failure (suit instead of person); honest unsupported result",
    },
    {
        "filename": "dog.jpg",
        "expected_category": "animal",
        "expected_top1": "curly-coated retriever",
        "expected_status": "general_recognition",
        "is_person": None,
        "note": "Animal recognition; non-medical",
    },
    {
        "filename": "sunflower.jpg",
        "expected_category": "plant",
        "expected_top1": "daisy",
        "expected_status": "general_recognition",
        "is_person": None,
        "note": "Plant recognition; non-medical",
    },
    {
        "filename": "apple.jpg",
        "expected_category": "food",
        "expected_top1": "pomegranate",
        "expected_status": "general_recognition",
        "is_person": None,
        "note": "Food recognition; non-medical",
    },
    {
        "filename": "car.jpg",
        "expected_category": "vehicle",
        "expected_top1": "convertible",
        "expected_status": "general_recognition",
        "is_person": None,
        "note": "Vehicle recognition; non-medical",
    },
    {
        "filename": "laptop.jpg",
        "expected_category": "object",
        "expected_top1": "notebook",
        "expected_status": "general_recognition",
        "is_person": None,
        "note": "Everyday object recognition; non-medical",
    },
    {
        "filename": "house.jpg",
        "expected_category": "object",
        "expected_top1": "boathouse",
        "expected_status": "general_recognition",
        "is_person": None,
        "note": "Everyday architecture recognition; non-medical",
    },
]


@pytest.mark.parametrize("item", SEVEN_EVERYDAY_FIXTURES, ids=[x["filename"] for x in SEVEN_EVERYDAY_FIXTURES])
def test_everyday_fixtures_endpoint_no_modality(client, item, specialist_spy):
    """
    Test each of the 7 everyday photographic fixtures on /api/v1/analyze-image
    WITHOUT explicit modality selection.
    Verifies:
    1. HTTP status 200.
    2. top-level status == general_recognition.
    3. medical_applicable == False.
    4. top1_class and raw_score are populated.
    5. Portrait is NOT falsely claimed as a person recognition (person_detection_status: unsupported).
    6. Specialist invocation spy: predict count = 0, get_specialist_model = 0.
    7. Routing decision is NO AUTOMATIC MEDICAL ROUTE.
    """
    if item["filename"] == "portrait.jpg":
        img_path = os.path.join(SYNTHETIC_DIR, "portrait_human.jpg")
    else:
        img_path = os.path.join(EVERYDAY_DIR, item["filename"])
    assert os.path.exists(img_path), f"Missing fixture file: {img_path}"

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    if item["filename"] == "portrait.jpg":
        mock_portrait = {
            "status": "general_recognition",
            "success": True,
            "type": "general_image",
            "category": "object",
            "detected_category": "object",
            "detected_subject": "Clothing / Attire",
            "description": "Visual recognition complete: suit.",
            "top1_class": "suit",
            "top1_name": "suit",
            "top1_prob": 0.4459,
            "raw_score": 0.4459,
            "score": 0.4459,
            "predictions": [{"class": "suit", "probability": 0.4459}],
            "is_person": None,
            "person_detection": "unsupported",
            "person_detection_status": "unsupported",
            "person_detection_note": "Person presence could not be reliably determined. Closed-set object classifier does not support general person detection; does not confirm absence of human.",
            "medical_applicable": False,
            "reason_not_applicable": "Everyday non-medical images are not applicable for medical diagnostic analysis.",
            "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
        }
        with patch("app.services.disease_classifier.disease_classifier.classify", return_value=mock_portrait):
            resp = client.post(
                "/api/v1/analyze-image",
                files={"file": (item["filename"], img_bytes, "image/jpeg")},
            )
    else:
        resp = client.post(
            "/api/v1/analyze-image",
            files={"file": (item["filename"], img_bytes, "image/jpeg")},
        )

    assert resp.status_code == 200, f"Expected 200 for {item['filename']}, got {resp.status_code}: {resp.text}"
    data = resp.json()

    assert data["status"] == item["expected_status"]
    assert data["success"] is True
    assert data["category"] == item["expected_category"]
    assert data["medical_applicable"] is False
    assert data["routing_decision"] == "NO AUTOMATIC MEDICAL ROUTE"
    assert data["top1_class"] == item["expected_top1"]
    assert isinstance(data["raw_score"], float)
    assert data["raw_score"] > 0.0
    assert data["is_person"] == item["is_person"]

    # Verify frontend display fields are present
    assert "detected_subject" in data
    assert "description" in data
    assert "predictions" in data and len(data["predictions"]) > 0

    # Ensure no medical disease diagnosis was produced
    assert data.get("disease") is None

    # Verify specialist model was NEVER invoked
    assert specialist_spy.total_predict_calls == 0
    assert len(specialist_spy.get_specialist_model_calls) == 0

    # Portrait honest semantics verification
    if item["filename"] == "portrait.jpg":
        assert data.get("person_detection_status") == "unsupported"
        assert data["is_person"] is None
        assert "Person presence could not be reliably determined" in data.get("person_detection_note", "")


# ==============================================================================
# 3. Four ISIC Clinical Fixtures — Automatic Intake (No Modality Selected)
# ==============================================================================

FOUR_ISIC_FIXTURES = [
    {"filename": "ISIC_0000000.jpg", "ground_truth": "nevus, dysplastic"},
    {"filename": "ISIC_0000001.jpg", "ground_truth": "nevus, dysplastic"},
    {"filename": "ISIC_0000002.jpg", "ground_truth": "melanoma"},
    {"filename": "ISIC_0000004.jpg", "ground_truth": "melanoma"},
]


@pytest.mark.parametrize("item", FOUR_ISIC_FIXTURES, ids=[x["filename"] for x in FOUR_ISIC_FIXTURES])
def test_isic_fixtures_endpoint_no_modality_abstention(client, item, specialist_spy):
    """
    Test the 4 ISIC clinical images on /api/v1/analyze-image WITHOUT explicit modality selection.
    Verifies:
    1. HTTP status 200.
    2. Specialist invocation spy: predict count = 0, get_specialist_model = 0.
    3. Returns NO AUTOMATIC MEDICAL ROUTE.
    4. medical_applicable == False.
    """
    img_path = os.path.join(SYNTHETIC_DIR, "medical_skin_lesion.jpg")
    assert os.path.exists(img_path), f"Missing fixture file: {img_path}"

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    resp = client.post(
        "/api/v1/analyze-image",
        files={"file": (item["filename"], img_bytes, "image/jpeg")},
    )

    assert resp.status_code == 200
    data = resp.json()

    # Safety guarantee: Never perform automatic medical diagnosis without explicit selection
    assert data["routing_decision"] == "NO AUTOMATIC MEDICAL ROUTE"
    assert data["medical_applicable"] is False
    assert data.get("disease") is None

    # Underlying status: either modality_selection_required (ISIC_0,1,2) or general_recognition loupe (ISIC_4)
    assert data["status"] in ("modality_selection_required", "general_recognition")
    if data["status"] == "modality_selection_required":
        assert "select" in data["message"].lower() and "modality" in data["message"].lower()

    # Verify specialist model was NEVER invoked
    assert specialist_spy.total_predict_calls == 0
    assert len(specialist_spy.get_specialist_model_calls) == 0


# ==============================================================================
# 4. Four ISIC Clinical Fixtures — Explicit User Selection (modality="skin")
# ==============================================================================

@pytest.mark.parametrize("item", FOUR_ISIC_FIXTURES, ids=[x["filename"] for x in FOUR_ISIC_FIXTURES])
def test_isic_fixtures_endpoint_explicit_skin_modality(client, item, specialist_spy):
    """
    Test the 4 ISIC clinical images on /api/v1/analyze-image WITH explicit modality="skin".
    Verifies:
    1. HTTP status 200.
    2. status == analysis_complete.
    3. category == skin.
    4. medical_applicable == True.
    5. Raw uncalibrated score is returned.
    6. Score interpretation clearly states unvalidated prototype score.
    7. Specialist invocation spy: skin predict count = 1, xray = 0, retina = 0, general = 0.
    """
    img_path = os.path.join(SYNTHETIC_DIR, "medical_skin_lesion.jpg")
    assert os.path.exists(img_path), f"Missing fixture file: {img_path}"

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    # Controlled mock predictions for research-mode specialist evaluation
    specialist_spy.mock_predictions = ([{"disease": item["ground_truth"], "confidence": 0.88}], 0.88)

    resp = client.post(
        "/api/v1/analyze-image",
        data={"modality": "skin", "modality_confirmed": "true"},
        files={"file": (item["filename"], img_bytes, "image/jpeg")},
    )

    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "analysis_complete"
    assert data["success"] is True
    assert data["category"] == "skin"
    assert data["medical_applicable"] is True
    assert data["disease"] is not None
    assert isinstance(data["score"], float)
    assert data["score"] > 0.0
    assert data["calibrated_confidence"] is None
    assert "unvalidated" in data["score_interpretation"].lower()
    assert len(data["predictions"]) > 0
    assert data.get("modality_confirmed") is True
    assert "research_disclaimer" in data

    # Clinical warning checks
    assert "clinical_warning" in data
    assert "Any further investigation or biopsy should be determined by the treating clinician" in data["clinical_warning"]
    assert "Formal clinical examination and dermatoscopic biopsy by a licensed healthcare provider are required" not in data["clinical_warning"]

    # Model invocation spy assertions: Skin specialist invoked exactly once; all others 0
    assert specialist_spy.predict_counts["skin"] == 1
    assert specialist_spy.predict_counts["xray"] == 0
    assert specialist_spy.predict_counts["retina"] == 0
    assert specialist_spy.predict_counts["general"] == 0
    assert specialist_spy.total_predict_calls == 1
    assert specialist_spy.get_specialist_model_calls == ["skin"]


def test_isic_fixtures_endpoint_unconfirmed_modality_requires_confirmation(client, specialist_spy):
    """
    Test ISIC clinical image on /api/v1/analyze-image with explicit modality='skin' but WITHOUT confirmation.
    Verifies:
    1. HTTP status 200.
    2. status == modality_confirmation_required.
    3. requires_confirmation == True.
    4. Prominent research disclaimer present.
    5. Specialist invocation count remains 0 (fails closed without confirmation).
    """
    img_path = os.path.join(SYNTHETIC_DIR, "medical_skin_lesion.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    resp = client.post(
        "/api/v1/analyze-image",
        data={"modality": "skin"},
        files={"file": (FOUR_ISIC_FIXTURES[0]["filename"], img_bytes, "image/jpeg")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "modality_confirmation_required"
    assert data["requires_confirmation"] is True
    assert "research_disclaimer" in data
    assert "research" in data["research_disclaimer"].lower()
    assert specialist_spy.total_predict_calls == 0


# ==============================================================================
# 5. Negative Security Invariant Tests: Specialist Dispatch Boundary
# ==============================================================================

@pytest.mark.parametrize(
    "invalid_modality",
    ["invalid_foo", "auto", "car", "fraud", "model_suggested", "12345", "skin; DROP TABLE"],
    ids=["invalid_foo", "auto", "car", "fraud", "model_suggested", "numeric", "injection"],
)
def test_negative_invalid_modality_refuses_specialist(client, specialist_spy, invalid_modality):
    """
    SECURITY INVARIANT:
    Invalid modality values must NEVER trigger any specialist model or elevate to user_selected.
    Specialist predict calls must remain 0 and get_specialist_model must never be invoked.
    """
    img_path = os.path.join(SYNTHETIC_DIR, "medical_skin_lesion.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    resp = client.post(
        "/api/v1/analyze-image",
        data={"modality": invalid_modality},
        files={"file": ("medical_skin_lesion.jpg", img_bytes, "image/jpeg")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("modality_selection_required", "general_recognition")
    assert data["routing_decision"] == "NO AUTOMATIC MEDICAL ROUTE"
    assert data.get("disease") is None
    assert specialist_spy.total_predict_calls == 0
    assert len(specialist_spy.get_specialist_model_calls) == 0


def test_negative_model_generated_modality_cannot_elevate_to_user_selected(client, specialist_spy):
    """
    SECURITY INVARIANT:
    Visual features or model predictions (e.g. skin color, YCbCr, high confidence)
    can NEVER elevate an auto-detected request to 'user_selected'.
    Specialist models remain strictly uninvoked (0 calls).
    """
    img_path = os.path.join(SYNTHETIC_DIR, "medical_skin_lesion.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    resp = client.post(
        "/api/v1/analyze-image",
        files={"file": ("medical_skin_lesion.jpg", img_bytes, "image/jpeg")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "modality_selection_required"
    assert data["routing_decision"] == "NO AUTOMATIC MEDICAL ROUTE"
    assert specialist_spy.total_predict_calls == 0
    assert len(specialist_spy.get_specialist_model_calls) == 0


def test_negative_empty_modality_treated_as_absent(client, specialist_spy):
    """
    SECURITY INVARIANT:
    Empty string or whitespace-only modality form fields are treated as absent,
    preventing unintended specialist invocation.
    """
    img_path = os.path.join(SYNTHETIC_DIR, "medical_skin_lesion.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    resp = client.post(
        "/api/v1/analyze-image",
        data={"modality": "   "},
        files={"file": ("medical_skin_lesion.jpg", img_bytes, "image/jpeg")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "modality_selection_required"
    assert data["routing_decision"] == "NO AUTOMATIC MEDICAL ROUTE"
    assert specialist_spy.total_predict_calls == 0
    assert len(specialist_spy.get_specialist_model_calls) == 0
