# NewGenHealthAI — Deployment Runbook

> **Status**: Phase 0 baseline. No production deployment performed yet.
> Runbook is authoritative for the Docker + Hugging Face Spaces path.

## Architecture

```
GitHub (sg721642/NewGenHealthAI)
  └─► Hugging Face Spaces (sg721642/NewGenHealthAI) [Docker SDK, port 7860]
        ├─ Dockerfile (root) — multi-stage: Node build → Python runtime
        └─ backend/app/static/ — Vite production build mounted into FastAPI static files
```

## Required Environment Variables (Secrets)

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Yes | LLM (Groq) and STT (Whisper) |
| `TAVILY_API_KEY` | Optional | Tavily web search tool |
| `SESSION_SECRET` | Yes | Starlette session cookie signing — must be stable across restarts |
| `CHAT_DB_PATH` | Optional | Override SQLite path (default: `backend/storage/chat_db/susham_health.db`) |

**Never commit secret values. Configure through Hugging Face Spaces → Settings → Repository secrets.**

## Database Persistence

> **Warning**: Hugging Face free-tier Spaces use ephemeral storage. The SQLite database
> at `backend/storage/chat_db/` is lost on Space rebuild unless a persistent volume is configured.
> This must be resolved before any production user data is relied upon.

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

## Docker Build (local, when Docker is available)

```bash
docker build -t newgenhealthai:dev .
docker run --rm -p 7860:7860 \
  --env-file .env \
  -v $(pwd)/backend/storage:/app/backend/storage \
  newgenhealthai:dev
```

## Deployment to Hugging Face Spaces

The Space is configured to use the GitHub repository directly.
Pushing to the main branch (or configuring a sync) triggers a Space rebuild.

**Phase 0 constraint**: Do NOT push to `main` or trigger a production deployment.
All work is on branch `fix/healthai-audit-premium-ui`.

## Rollback Procedure

1. Identify last known-good commit SHA from `docs/IMPLEMENTATION_STATUS.md`
2. On Hugging Face Spaces UI → Factory Reboot or restore previous revision if available
3. For database rollback: restore from backup copy (must be created before any migration)
4. Verify: login, create conversation, send message, retrieve history

## Pre-deployment Verification Gates (Not Yet Run)

- [ ] Auth isolation: cross-user session access blocked (A01/A02)
- [ ] Wildcard CORS removed (A07)
- [ ] Frontend build clean with lint passing (A15)
- [ ] Backend tests passing with full ML deps
- [ ] TTS uses POST body not GET param (A08)
- [ ] Legacy names cleaned (A16)
- [ ] HF Space secrets configured
- [ ] DB persistence confirmed or limitation documented to users

## Known Limitations (Phase 0)

- Docker not installed locally — Dockerfile not locally built/tested
- HF Space running status not independently verified (requires browser login)
- ML model weights not downloaded — inference untested offline
- Backend test suite blocked by ML dependency chain
