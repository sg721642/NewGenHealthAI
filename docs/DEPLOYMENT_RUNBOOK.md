# NewGenHealthAI — Deployment Runbook

> **Status**: Phase 1B (Security and Migration Corrections).
> Runbook is authoritative for the Docker + Hugging Face Spaces deployment path.

## Architecture

```
GitHub (sg721642/NewGenHealthAI)
  └─► Hugging Face Spaces (sg721642/NewGenHealthAI) [Docker SDK, port 7860]
        ├─ Dockerfile (root) — multi-stage: Node build → Python runtime
        ├─ backend/app/static/ — Vite production build mounted into FastAPI static files
        └─ SQLite DB + Migrations — SQLite Online Backup API & versioned migration on startup
```

## Required Environment Variables (Secrets)

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Yes | LLM (Groq) and STT (Whisper) |
| `TAVILY_API_KEY` | Optional | Tavily web search tool |
| `SESSION_SECRET_KEY` / `SESSION_SECRET` | Yes | Starlette session cookie signing (must be at least 32 characters in production) |
| `LEGACY_PBKDF2_SALT` | Optional (Migration) | Migration-only salt for legacy PBKDF2 password upgrades to Argon2id |
| `SESSION_EXPIRE_HOURS` | Optional | Session token validity duration in hours (default: `24`) |
| `ALLOWED_ORIGINS` | Optional | Comma-separated list of allowed CORS origins (default: localhost & 127.0.0.1 ports 5173/8000) |
| `CHAT_DB_PATH` | Optional | Override SQLite path (default: `backend/storage/chat_db/susham_health.db`) |

**Never commit secret values. Configure through Hugging Face Spaces → Settings → Repository secrets.**

## Database Migration & Safety Runbook

Phase 1C runs `backend/app/db/migrations.py` (Current Schema Version: 2):
1. **Pre-check & Runaway Backup Prevention**: The migration runner checks `schema_versions` first. If the schema is already at or above `CURRENT_SCHEMA_VERSION` (2), migration and backup creation are skipped entirely.
2. **SQLite Online Backup API**: If a schema migration is required and a database exists, a point-in-time snapshot is created using SQLite's Online Backup API (`src.backup(dst)`). This guarantees consistency even with active WAL mode concurrency.
3. **Integrity Validation**: All backups and restores are validated with `PRAGMA integrity_check` before proceeding.
4. **Schema Version 1 Tracking**:
   - `conversations` table ensures explicit conversation ownership.
   - Conservative ownership reconstruction: only clean single-owner sessions are mapped to owners; ambiguous/conflicting/null sessions are strictly quarantined (`is_quarantined=1, user_id=0`) without altering original message records.
5. **Schema Version 2 Tracking**:
   - `user_sessions` upgraded to store SHA-256 token hashes (`token_hash VARCHAR(64) PRIMARY KEY`) and explicit expiration (`expires_at`).
   - Legacy raw session tokens are hashed to SHA-256 and given a 24-hour expiration window.
6. **Recovery Procedure**:
   ```python
   from app.db.migrations import restore_database
   restore_database("backend/storage/chat_db/susham_health.db.backup_<timestamp>_<uuid>", "backend/storage/chat_db/susham_health.db")
   ```

## Local Development Quick Start

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (separate terminal)
npm --prefix frontend install
npm --prefix frontend run dev
```

## Rollback Procedure

1. Identify last known-good commit SHA from `docs/IMPLEMENTATION_STATUS.md`
2. On Hugging Face Spaces UI → Factory Reboot or restore previous revision if available
3. For database rollback: restore from verified online backup file using `restore_database`
4. Verify: login, create conversation, send message, retrieve history

## Pre-deployment Verification Gates

- [x] Auth isolation: cross-user session access blocked (A01/A02 verified with 35 backend tests)
- [x] Query token elimination: URL tokens (`?token=...`) rejected across all endpoints (A01)
- [x] TTS converted to authenticated POST body instead of GET query param (A08)
- [x] Frontend audio playback manages and revokes Blob URLs cleanly (A08)
- [x] Arbitrary client-supplied conversation IDs rejected with 404 (A02)
- [x] SQLite Online Backup API and integrity verification implemented (A01, A02)
- [x] Conservative legacy ownership reconstruction (no NULL backfill) verified (A02)
- [x] Frontend build clean with lint passing (0 errors, 0 warnings, 4/4 tests pass)
- [x] Backend test suite unblocked: offline testing working (35/35 tests pass)
- [ ] Wildcard CORS removed (A07 — scheduled for Phase 4)
- [ ] Password salt migration (A06 — scheduled for Phase 2)
- [ ] HF Space running status verified with live credentials
