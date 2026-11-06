"""
NewGenHealthAI — core/config.py
Environment variables and path constants.
"""

import os

from typing import List, Optional
from dotenv import load_dotenv

# Load .env from backend directory or root directory
load_dotenv()
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
load_dotenv(os.path.join(_BACKEND_DIR, "..", ".env"))

# ── Paths ──────────────────────────────────────────────────────────────────────
# Ensure logs and storage are inside backend directory
LOG_DIR = os.getenv("LOG_DIR", os.path.join(_BACKEND_DIR, "logs"))
_prod_db_path = os.path.join(_BACKEND_DIR, "storage", "chat_db", "susham_health.db")
_raw_chat_db_path = os.getenv("CHAT_DB_PATH")
_is_testing_env = (
    os.getenv("ENVIRONMENT", "").lower() in ("testing", "test")
    or os.getenv("ENV", "").lower() in ("testing", "test")
    or "PYTEST_CURRENT_TEST" in os.environ
)

if _is_testing_env and _raw_chat_db_path and os.path.abspath(_raw_chat_db_path) == os.path.abspath(_prod_db_path):
    import tempfile
    CHAT_DB_PATH = os.path.join(tempfile.gettempdir(), "isolated_test_fallback.db")
else:
    CHAT_DB_PATH = _raw_chat_db_path if _raw_chat_db_path else _prod_db_path

VECTOR_STORE_DIR = os.getenv("VECTOR_STORE_DIR", os.path.join(_BACKEND_DIR, "storage", "vector_store"))
PDF_PATH = os.getenv("PDF_PATH", os.path.join(_BACKEND_DIR, "data", "medical_book.pdf"))

# ── API Keys & Model Selection ───────────────────────────────────────────────
def is_offline_mode() -> bool:
    """Authoritative check for whether offline execution mode is active."""
    raw = os.getenv("OFFLINE_MODE")
    if raw is None:
        return False
    return raw.strip().lower() in ("true", "1", "yes")


OFFLINE_MODE: bool = is_offline_mode()


RECOGNIZED_PRODUCTION_ENVIRONMENTS = ("production", "prod")
RECOGNIZED_NON_PRODUCTION_ENVIRONMENTS = ("development", "dev", "local", "testing", "test")


def verify_clinical_governance_authorization() -> bool:
    """
    Rigorously verifies whether formal clinical governance prerequisites are met for production.

    For the CURRENT production release:
    - Diagnostic specialist models are unvalidated research prototypes ('NOT_CLINICALLY_VALIDATED').
    - Prospective clinical validation, multi-reader multi-case (MRMC) clinical trials, and formal
      institutional ethics clearances have NOT been completed.
    - No cryptographic signer authentication or clinical registry validation exists in this software;
      an arbitrary JSON record or environment variable string cannot verify authentic clinical authorization.
    - Therefore, this release gate UNCONDITIONALLY FAILS CLOSED (False).
    - CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL=true, ENABLE_CLINICAL_SPECIALIST_MODELS=true,
      or any JSON record containing 'APPROVED' or signoff fields MUST NOT enable production
      clinical specialist inference.
    """
    return False


def is_clinical_specialist_enabled() -> bool:
    """
    Authoritative production-safe feature gate for unvalidated specialist predictions.

    Boundary Rules:
    1. Production Environments ('production', 'prod'):
       - Strictly REJECT all overrides: ENABLE_CLINICAL_SPECIALIST_MODELS=true,
         CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL=true, and approval-shaped JSON records.
       - Production clinical specialist inference is unconditionally disabled (fails closed: False).
       - Zero specialist models may be loaded or invoked in production.

    2. Explicitly Recognized Non-Production Environments ('development', 'dev', 'local', 'testing', 'test'):
       - Deliberate opt-in permitted for research/testing via ENABLE_CLINICAL_SPECIALIST_MODELS=true
         (or alias ALLOW_UNVALIDATED_CLINICAL_MODELS=true).
       - In 'development'/'local', defaults to False when unconfigured.
       - Missing or malformed values fail closed (False).
       - In 'testing'/'test' under automated test harness (PYTEST_CURRENT_TEST),
         defaults to True only when unconfigured to preserve baseline test compatibility.

    3. Absent, Empty, or Unrecognized Environments:
       - An absent, empty, or unknown environment (e.g. 'staging', 'qa', 'cluster')
         must NEVER activate local research-mode specialist inference.
       - Fails closed (False) unconditionally.
    """
    env_raw = os.getenv("ENVIRONMENT")
    if env_raw is None:
        env_raw = os.getenv("ENV")

    # Absent or empty environment must FAIL CLOSED
    if not env_raw or not env_raw.strip():
        return False

    env = env_raw.strip().lower()

    # 1. PRODUCTION ENVIRONMENT GATE
    if env in RECOGNIZED_PRODUCTION_ENVIRONMENTS:
        # In the current production release, clinical specialist inference is unconditionally disabled.
        # Fails closed (False) unconditionally regardless of runtime flags or configuration files.
        return verify_clinical_governance_authorization()

    # 2. EXPLICITLY RECOGNIZED NON-PRODUCTION ENVIRONMENTS
    if env in RECOGNIZED_NON_PRODUCTION_ENVIRONMENTS:
        raw_research = os.getenv("ENABLE_CLINICAL_SPECIALIST_MODELS")
        if raw_research is None:
            raw_research = os.getenv("ALLOW_UNVALIDATED_CLINICAL_MODELS")

        if raw_research is not None:
            return raw_research.strip().lower() in ("true", "1", "yes")

        # When variable is absent:
        if env in ("testing", "test") and os.getenv("PYTEST_CURRENT_TEST"):
            return True

        return False

    # 3. UNRECOGNIZED / UNKNOWN ENVIRONMENTS FAIL CLOSED
    return False


ENABLE_CLINICAL_SPECIALIST_MODELS: bool = is_clinical_specialist_enabled()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Official Groq active chat & reasoning model configuration
# (Note: llama-3.3-70b-versatile and llama-3.1-8b-instant are deprecated for developer tier)
GROQ_CHAT_MODEL: str = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b").strip()
GROQ_TRIAGE_MODEL: str = os.getenv("GROQ_TRIAGE_MODEL", GROQ_CHAT_MODEL).strip()
_raw_fallback_models = os.getenv("GROQ_FALLBACK_MODELS", "openai/gpt-oss-20b,qwen/qwen3.8-27b").strip()
GROQ_FALLBACK_MODELS: List[str] = [m.strip() for m in _raw_fallback_models.split(",") if m.strip()]

# Official Groq multimodal vision model configuration (Qwen 3.8 27B multimodal)
GROQ_VISION_MODEL: str = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b").strip()
_raw_vision_fallback_models = os.getenv("GROQ_VISION_FALLBACK_MODELS", "meta-models/muse-spark-open").strip()
GROQ_VISION_FALLBACK_MODELS: List[str] = [m.strip() for m in _raw_vision_fallback_models.split(",") if m.strip()]
VISION_REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("VISION_REQUEST_TIMEOUT_SECONDS", "12.0"))

# ── Localization & Crisis Guidance ───────────────────────────────────────────
DEFAULT_CRISIS_LOCALE: str = os.getenv("DEFAULT_CRISIS_LOCALE", "IN").strip().upper()

# ── Security & Session Configuration ───────────────────────────────────────────
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

_raw_legacy_salt = os.getenv("LEGACY_PBKDF2_SALT", "").strip()
LEGACY_PBKDF2_SALT: Optional[bytes] = _raw_legacy_salt.encode("utf-8") if _raw_legacy_salt else None

SESSION_SECRET_KEY: Optional[str] = os.getenv("SESSION_SECRET_KEY") or os.getenv("SESSION_SECRET")
SESSION_EXPIRE_HOURS: int = int(os.getenv("SESSION_EXPIRE_HOURS", "24"))

_raw_cors = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
)
ALLOWED_ORIGINS: List[str] = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()]

# ── Reverse Proxy & Rate Limiting Configuration ──────────────────────────────
_raw_trusted_proxies = os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1").strip()
TRUSTED_PROXIES: List[str] = [p.strip() for p in _raw_trusted_proxies.split(",") if p.strip()]

RATE_LIMIT_LOGIN_PER_IP: int = int(os.getenv("RATE_LIMIT_LOGIN_PER_IP", "10"))
RATE_LIMIT_LOGIN_PER_USER: int = int(os.getenv("RATE_LIMIT_LOGIN_PER_USER", "5"))
RATE_LIMIT_REGISTER_PER_IP: int = int(os.getenv("RATE_LIMIT_REGISTER_PER_IP", "5"))
RATE_LIMIT_WINDOW_SECONDS: float = float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60.0"))

# ── Image Upload & Inference Resource Protection (A07, A09) ───────────────────
# Configurable compressed upload limit (default: 5 MB)
MAX_IMAGE_UPLOAD_BYTES: int = int(os.getenv("MAX_IMAGE_UPLOAD_BYTES", 5 * 1024 * 1024))

# Maximum decoded image dimension and pixel count to prevent decompression bombs (16 MP default)
MAX_IMAGE_DIMENSION: int = int(os.getenv("MAX_IMAGE_DIMENSION", "4096"))
MAX_IMAGE_PIXELS: int = int(os.getenv("MAX_IMAGE_PIXELS", "16000000"))

# Allowed image MIME and formats
ALLOWED_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})
ALLOWED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

# Concurrency & queue capacity for heavyweight model operations
MAX_CONCURRENT_INFERENCE: int = int(os.getenv("MAX_CONCURRENT_INFERENCE", "2"))
INFERENCE_QUEUE_TIMEOUT_SECONDS: float = float(
    os.getenv("INFERENCE_QUEUE_TIMEOUT_SECONDS", "5.0")
)

# Startup / offline safety flags: default false prevents implicit multi-GB downloads
ALLOW_MODEL_DOWNLOADS: bool = os.getenv("ALLOW_MODEL_DOWNLOADS", "false").strip().lower() == "true"
ENABLE_BLIP_CAPTIONING: bool = os.getenv("ENABLE_BLIP_CAPTIONING", "false").strip().lower() == "true"

# ── Voice Processing & Concurrency Resource Protection (A07, A08) ─────────────
# Configurable audio upload limit (default: 10 MB) and minimum speech payload (500 bytes)
MAX_AUDIO_UPLOAD_BYTES: int = int(os.getenv("MAX_AUDIO_UPLOAD_BYTES", 10 * 1024 * 1024))
MIN_AUDIO_UPLOAD_BYTES: int = int(os.getenv("MIN_AUDIO_UPLOAD_BYTES", 500))
MAX_AUDIO_DURATION_SECONDS: float = float(os.getenv("MAX_AUDIO_DURATION_SECONDS", "300.0"))

# Voice capacity management: process-local concurrency semaphores
MAX_CONCURRENT_STT: int = int(os.getenv("MAX_CONCURRENT_STT", "3"))
MAX_CONCURRENT_TTS: int = int(os.getenv("MAX_CONCURRENT_TTS", "5"))
VOICE_QUEUE_TIMEOUT_SECONDS: float = float(os.getenv("VOICE_QUEUE_TIMEOUT_SECONDS", "5.0"))

# Provider deadlines & timeouts
STT_REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("STT_REQUEST_TIMEOUT_SECONDS", "15.0"))
STT_OVERALL_DEADLINE_SECONDS: float = float(os.getenv("STT_OVERALL_DEADLINE_SECONDS", "30.0"))
TTS_REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("TTS_REQUEST_TIMEOUT_SECONDS", "15.0"))
TTS_STREAM_TIMEOUT_SECONDS: float = float(os.getenv("TTS_STREAM_TIMEOUT_SECONDS", "30.0"))
MAX_TTS_INPUT_CHARS: int = int(os.getenv("MAX_TTS_INPUT_CHARS", "2000"))
MAX_TTS_STREAM_BYTES: int = int(os.getenv("MAX_TTS_STREAM_BYTES", 5 * 1024 * 1024))


