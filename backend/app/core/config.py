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
