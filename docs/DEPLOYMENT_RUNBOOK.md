# NewGenHealthAI — Deployment Runbook

> **Status**: Phase 1C.1 (Authentication Hardening and Database Migration Risks Remediation).
> Runbook is authoritative for the Docker + Hugging Face Spaces deployment path.

## Architecture

```
GitHub (sg721642/NewGenHealthAI)
  └─► Hugging Face Spaces (sg721642/NewGenHealthAI) [Docker SDK, port 7860]
        ├─ Dockerfile (root) — multi-stage: Node build → Python runtime
        ├─ backend/app/static/ — Vite production build mounted into FastAPI static files
        └─ SQLite DB + Migrations — SQLite Online Backup API & atomic transactional migration on startup
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
| `TRUSTED_PROXIES` | Optional | Comma-separated list of trusted reverse proxy IPs and CIDR networks (default: `127.0.0.1,::1`). Set to include reverse proxy CIDRs (e.g. `10.0.0.0/8,172.16.0.0/12`) on Hugging Face Spaces or cloud proxies. |
| `CHAT_DB_PATH` | Optional | Override SQLite path (default: `backend/storage/chat_db/susham_health.db`) |

**Never commit secret values. Configure through Hugging Face Spaces → Settings → Repository secrets.**

## Reverse Proxy & Rate Limiting Architecture (SEC-01, SEC-02)

1. **Trusted Proxy Validation (SEC-01)**:
   - Direct connecting client peer (`req.client.host`) is validated against configured `TRUSTED_PROXIES`.
   - If peer is untrusted, all `X-Forwarded-For` headers are treated as spoofed and ignored; the direct peer IP is enforced.
   - If peer is in `TRUSTED_PROXIES`, the proxy chain is traversed from right to left, skipping trusted proxy hops to locate the authentic client IP.
   - Malformed IP inputs are rejected safely without system errors.

2. **Bounded Sliding-Window Rate Limiter (SEC-02)**:
   - Memory-safe bounded sliding window (`BoundedRateLimiter`) with maximum capacity of 10,000 keys and automatic TTL pruning.
   - `/auth/register`: Rate-limited to 5 attempts per 60 seconds per client IP (returns HTTP 429).
   - `/auth/login`: Protected by dual rate limiting:
     - 10 failed attempts per 60 seconds per client IP.
     - 5 failed attempts per 120 seconds per target username (per-account lockout across distributed IPs).
     - Successful authentication clears both IP and username failure counters immediately.
   - **Multi-Worker Note**: The built-in rate limiter is process-local (single-instance). For distributed multi-worker deployments (e.g., Uvicorn with multiple workers or replicated container clusters), rate limiting should be backed by an external distributed store like Redis.

## Database Migration & Safety Runbook (MIG-01, MIG-02, OPS-01)

Phase 1C.1 runs `backend/app/db/migrations.py` (Current Schema Version: 2):
1. **Pre-check & Runaway Backup Prevention**: The migration runner checks `schema_versions` first. If the schema is already at or above `CURRENT_SCHEMA_VERSION` (2), migration and backup creation are skipped entirely.
2. **SQLite Online Backup API**: If a schema migration is required and a database exists, a point-in-time snapshot is created using SQLite's Online Backup API (`src.backup(dst)`). This guarantees consistency even with active WAL mode concurrency.
3. **Backup Preservation Discipline (OPS-01)**: No blanket file deletion commands (`rm -f *.backup_*`) are ever run against `backend/storage/chat_db/`. All test suites use isolated `tmp_path` environments.
4. **Integrity Validation**: All backups and restores are validated with `PRAGMA integrity_check` before proceeding.
5. **Schema Version 1 Tracking & Fail-Closed Quarantine (MIG-02)**:
   - `conversations` table ensures explicit conversation ownership.
   - If `users` table is missing or user does not exist in `users`, sessions fail closed into quarantine (`is_quarantined=1, user_id=0`). Original message records are preserved intact without modification or backfilling.
6. **Atomic Transactional Migration (MIG-01)**:
   - Upgrades `user_sessions` to schema v2 via an isolated staging table (`_user_sessions_staging_<uuid>`).
   - Validates row counts (staging count == distinct valid legacy tokens), SHA-256 hash formatting (64 hex characters), and table schema within a single transactional boundary (`engine.begin()`).
   - If validation fails, transaction rolls back automatically without dropping or modifying legacy `user_sessions`.
   - On successful validation, table cutover and schema version 2 tracking commit atomically.
7. **Recovery Procedure**:
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
- [x] Conservative legacy ownership reconstruction (no NULL backfill) verified (A02, MIG-02)
- [x] Untrusted reverse proxy headers ignored, trusted proxy CIDR traversal enforced (SEC-01)
- [x] Bounded in-memory sliding-window rate limiting on register and login with per-account lockouts (SEC-02)
- [x] Atomic transactional staging migrations with pre-cutover validation and rollback (MIG-01)
- [x] Complete backend test suite inventory verified (124 passed, 1 skipped)
- [x] Frontend build clean with lint passing (0 errors, 0 warnings, 4/4 tests pass)
- [ ] HF Space running status verified with live credentials (post-deployment)

