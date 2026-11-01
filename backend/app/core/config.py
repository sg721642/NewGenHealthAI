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
CHAT_DB_PATH = os.getenv("CHAT_DB_PATH", os.path.join(_BACKEND_DIR, "storage", "chat_db", "susham_health.db"))
VECTOR_STORE_DIR = os.getenv("VECTOR_STORE_DIR", os.path.join(_BACKEND_DIR, "storage", "vector_store"))
PDF_PATH = os.getenv("PDF_PATH", os.path.join(_BACKEND_DIR, "data", "medical_book.pdf"))

# ── API Keys ───────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

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
MAX_TTS_INPUT_CHARS: int = int(os.getenv("MAX_TTS_INPUT_CHARS", "2000"))


