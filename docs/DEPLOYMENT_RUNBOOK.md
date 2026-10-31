# NewGenHealthAI — Deployment Runbook

> **Status**: Phase 1A (Authentication & Conversation Isolation Security).
> Runbook is authoritative for the Docker + Hugging Face Spaces deployment path.

## Architecture

```
GitHub (sg721642/NewGenHealthAI)
  └─► Hugging Face Spaces (sg721642/NewGenHealthAI) [Docker SDK, port 7860]
        ├─ Dockerfile (root) — multi-stage: Node build → Python runtime
        ├─ backend/app/static/ — Vite production build mounted into FastAPI static files
        └─ SQLite DB + Migrations — automatic backup & versioned migration on startup
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

Phase 1A introduces `backend/app/db/migrations.py`:
1. **Automatic Backup**: On application startup, if an existing SQLite database exists, it is automatically backed up to `<db_path>.backup_<YYYYMMDD_HHMMSS>`.
2. **Schema Migration**: Ensures the `conversations` table exists with ownership indexes.
3. **Legacy Data Mapping**:
   - Distinct legacy `session_id` records in `messages` that unambiguously belong to a single valid user are assigned to that user in `conversations`.
   - Conflicting or anonymous legacy records are quarantined (`is_quarantined=1, user_id=0`) so they are never leaked across users.
4. **Manual Recovery Command**:
   ```python
   from app.db.migrations import restore_database
   restore_database("backend/storage/chat_db/susham_health.db.backup_<timestamp>", "backend/storage/chat_db/susham_health.db")
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
3. For database rollback: restore from automatic backup file using `restore_database`
4. Verify: login, create conversation, send message, retrieve history

## Pre-deployment Verification Gates

- [x] Auth isolation: cross-user session access blocked (A01/A02 verified with 30 backend tests)
- [x] Frontend build clean with lint passing (0 errors, 5 warnings, 4/4 tests pass)
- [x] Backend test suite unblocked: offline testing working (30/30 tests pass)
- [ ] Wildcard CORS removed (A07 — scheduled for Phase 4)
- [ ] TTS uses POST body not GET param (A08 — scheduled for Phase 4)
- [ ] Password salt migration (A06 — scheduled for Phase 2)
- [ ] HF Space running status verified with live credentials
