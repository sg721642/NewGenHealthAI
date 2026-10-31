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
| `SESSION_SECRET` | Yes | Starlette session cookie signing — must be stable across restarts |
| `CHAT_DB_PATH` | Optional | Override SQLite path (default: `backend/storage/chat_db/susham_health.db`) |

**Never commit secret values. Configure through Hugging Face Spaces → Settings → Repository secrets.**

## Database Migration & Safety Runbook

Phase 1B provides `backend/app/db/migrations.py`:
1. **SQLite Online Backup API**: On application startup, if an existing SQLite database exists, it is backed up using SQLite's Online Backup API (`src.backup(dst)`). This guarantees point-in-time consistency even with active WAL mode concurrency, avoiding torn pages.
2. **Integrity Validation**: All backups and restores are validated with `PRAGMA integrity_check` before proceeding.
3. **Schema Version Tracking**: Table `schema_versions (version, applied_at, description)` records migration milestones. Subsequent starts skip applied migrations idempotently.
4. **Conservative Legacy Ownership Reconstruction**:
   - Only sessions where 100% of messages belong to a single valid user in `users` are migrated to `conversations`.
   - Any sessions with mixed NULL + identified users, conflicting users, NULL-only messages, or unknown users are strictly quarantined (`is_quarantined=1, user_id=0`).
   - Original message rows and their user IDs are never modified or backfilled during quarantine.
   - Quarantined sessions are inaccessible via normal application endpoints.
5. **Recovery Procedure**:
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
