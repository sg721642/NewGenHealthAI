# NewGenHealthAI — Deployment Runbook

> **Status**: Phase 2B.1 (Final Workflow Reliability, Privacy and Emergency-Safety Corrections).
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
| `CONSULTATION_TIMEOUT_SECONDS` | Optional | Overall per-consultation wall-clock timeout in seconds (default: `90`) |
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

Phase 1D runs `backend/app/db/migrations.py` (Current Schema Version: 2):
1. **Pre-check & Runaway Backup Prevention**: The migration runner checks `schema_versions` first. If the schema is already at or above `CURRENT_SCHEMA_VERSION` (2), migration and backup creation are skipped entirely.
2. **SQLite Online Backup API**: If a schema migration is required and a database exists, a point-in-time snapshot is created using SQLite's Online Backup API (`src.backup(dst)`). This guarantees consistency even with active WAL mode concurrency.
3. **Backup Preservation Discipline (OPS-01)**: No blanket file deletion commands (`rm -f *.backup_*`) are ever run against `backend/storage/chat_db/`. All test suites use isolated `tmp_path` environments.
4. **Integrity Validation**: All backups and restores are validated with `PRAGMA integrity_check` before proceeding.
5. **Step-Wise Independent Atomic Migrations**:
   - Migrations are structured as **step-wise independent atomic transactions**, where each schema version step runs in its own atomic `engine.begin()` transaction with an explicit version marker recorded in `schema_versions`.
   - **Step 1 (Version 1)**: Creates `conversations` table, reconstructs ownership conservatively, and marks version 1. If `users` table is missing or user does not exist, sessions fail closed into quarantine (`is_quarantined=1, user_id=0`) without altering original message records.
   - **Step 2 (Version 2)**: Staged migration for `user_sessions` via temporary table (`_user_sessions_staging_<uuid>`). Validates row counts, SHA-256 hash formatting (64 hex chars), and schema columns before cutover. If validation fails, Step 2 rolls back cleanly without dropping legacy tables.
   - **Recovery & Resumability**: If a failure or process interruption occurs between Step 1 and Step 2, the database remains in a consistent v1 state. Upon next startup, the runner detects `latest_version == 1` and safely resumes execution at Step 2 without re-running Step 1 or corrupting state.
6. **Recovery Procedure**:
   ```python
   from app.db.migrations import restore_database
   restore_database("backend/storage/chat_db/susham_health.db.backup_<timestamp>_<uuid>", "backend/storage/chat_db/susham_health.db")
   ```

## Concurrency & Clinical Memory Architecture (Phase 1D)

1. **Per-Conversation Async Serialization (`ConversationLockManager`)**:
   - Bounded, reference-counted `asyncio.Lock` per `user_id:session_id` pair.
   - Ensures simultaneous turns in the same consultation are processed sequentially in strict chronological order.
   - Different consultations process concurrently without blocking each other.
   - Locks are automatically evicted when reference count reaches 0, preventing unbounded lock memory leaks.
   - Process-Local Note: Designed for single-process ASGI event loops. For horizontal scaling across multiple Uvicorn workers or container replicas, sticky session routing or a distributed coordinator (e.g. Redis Redlock) is required.
2. **Clear & Delete Race Guards**:
   - Generational versioning (`_versions`) and deletion tombstoning (`_deleted_sessions`) detect when a conversation is cleared or deleted while an LLM inference request is in flight.
   - In-flight responses are safely discarded without updating in-memory cache or persisting assistant turns to DB, returning HTTP 409 Conflict.
   - Prevents delayed or stale responses from resurrecting deleted conversations or reintroducing cleared context.
3. **Clinical Memory Rehydration from Persisted History**:
   - Upon server restart or LRU cache eviction (`MAX_CONVERSATION_CACHE = 500`), state is rehydrated from authorized database records.
   - Restores up to `MAX_RESTORE_TURNS = 20` turns in chronological order.
   - Excludes failed or incomplete assistant responses (`"Unable to generate response"`, error messages).
   - Derived clinical triage state starts cleanly initialized without synthesizing unverified historical medical decisions.
4. **Frontend Stale Response & Account Switch Protection**:
   - `AbortController` cleanly cancels in-flight `/chat` network requests when switching sessions, starting new consultations, clearing, deleting, or logging out.
   - Active session ref (`currentSessionIdRef`) and active user ref (`currentUserRef`) guarantee that late network responses cannot cross-contaminate different conversations or subsequent user sessions.
5. **Bounded Rate Limiter Overload Policy**:
   - Under capacity exhaustion (10,000 keys), `BoundedRateLimiter` prunes expired entries first.
   - Active security counters (accounts with failed login lockouts >= threshold) are strictly preserved and never evicted to admit new identifiers.
   - Safe overload shedding fails closed on registration if the capacity is completely saturated with active entries.

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

## Image Classification & Model Provenance Architecture (Phase 2A — A03, A04)

### 1. Hard Modality Locking & Zero-Fallback Policy
- **CLIP Domain Routing**: Zero-shot CLIP evaluates incoming imagery across 5 domain hypotheses (`skin`, `xray`, `retina`, `general`, `non_medical`).
- **Strict Modality Lock**: Executes **only** the single verified specialist model matching the detected domain.
- **Elimination of Fallbacks**: If the specialist model weights are not loaded locally, the system returns `HTTP 503 Service Unavailable` with `status="model_unavailable"`. It strictly **never** falls back to `general` or executes all models.
- **Non-Medical Filtering**: Non-medical images (e.g. landscapes, animals, everyday objects) return `HTTP 422 Unprocessable Entity` with `status="unsupported_image"` and optional BLIP scene description. Medical disease classification models are never invoked on non-medical photos.
- **Ambiguity Guard**: Ambiguous or failing CLIP detections return `HTTP 200 OK` with `status="inconclusive"`.

### 2. Model Provenance & Specification Table

> [!WARNING]
> **Clinical Accuracy Disclaimer**: All models are research prototypes trained on publicly available academic datasets. Model weights are experimental and have **NOT** been clinically validated or approved by regulatory bodies (FDA, CE, EMA). All scores are uncalibrated algorithmic outputs and must not be used for diagnosis, triage, or clinical decision-making.

| Modality | Architecture | Input Size | Classes | Weights File | Class File | Clinical Validation Status |
|---|---|---|---|---|---|---|
| **Skin** | `timm` EfficientNet | 224×224 RGB | 216 classes (dermatological conditions) | `skin_disease_model.pth` | `classes.txt` | ⚠️ Unvalidated Academic Prototype |
| **X-ray** | DenseNet121 | 224×224 RGB | 10 classes (7 anatomy + 2 conditions + 1 normal) | `xray_fracture_model.pth` | `xray_classes.txt` | ⚠️ Unvalidated Academic Prototype |
| **Retina** | EfficientNet-B0 | 224×224 RGB | 47 classes (fundus ocular conditions + healthy eye) | `retina_model.pth` | `retina_classes.txt` | ⚠️ Unvalidated Academic Prototype |
| **General** | ResNet18 | 224×224 RGB | 69 classes (medical modalities & conditions) | `general_disease_model.pth` | `general_classes.txt` | ⚠️ Unvalidated Academic Prototype |

### 3. Normal / Negative & Anatomy Safeguards
- **Negative Finding Preservation**: Valid negative classes (`normal`, `normal cases`, `notumor`, `notinfected`, `uninfected`, `non-covid`, `benign`, `bengin cases`, `healthy eye`) are preserved as top valid findings. Lower-ranked conditions are never promoted ahead of legitimate normal predictions.
- **X-ray Anatomy Distinction**: Body-part predictions (`wrist`, `elbow`, `finger`, `forearm`, `hand`, `humerus`, `shoulder`) are classified as `finding_type="anatomy_identified"`. The system never manufactures "Abnormality Detected" or fractures from anatomical location labels alone.
- **Dataset Artifact Filtering**: Unvalidated dataset artifacts (`preview`, `train`, `val`, `cropped`, etc.) are caught. If ranked top, the system returns `status="inconclusive"` and suppresses lower-ranked condition promotion.

---

## Clinical Intelligence & Emergency Safety Safeguards (A05, A17)

1. **Deterministic Urgent-Risk Emergency Gate**:
   - Executes in pure offline Python regex and keyword heuristics before ordinary intake and tool fallback.
   - 100% available even if Groq LLM, ChromaDB, Wikipedia, and Tavily are completely offline.
   - Evaluates for cardiac (crushing chest pain / radiation), stroke (FAST criteria), severe respiratory distress, anaphylaxis, uncontrolled hemorrhage, and crisis/self-harm.
   - Bypasses triage questioning and immediately returns 911 / 999 / 112 / ED escalation instructions with clear clinical limitation disclaimers.

2. **Bounded DAG Routing & Cycle Termination (A05)**:
   - Bounded provider visit budgets: `attempted_providers` tracks visited nodes; each provider is visited at most once per turn.
   - Linear fallback progression: `retriever` -> `llm_agent` -> `wikipedia` -> `tavily` -> `executor`.
   - Eliminates circular looping between `llm_agent` and `retriever`.
   - Exhaustion handling: when all candidate providers fail or are unavailable, terminates cleanly at `executor` with `source="Service Unavailable"` and `is_failed_generation=True`.

3. **Physician Impersonation & Prescription Prohibition (A17)**:
   - System persona de-escalated across `triage_agent.py`, `llm_agent.py`, and `executor.py` to an automated medical education and informational assistant.
   - Strictly forbids claiming physician status, doctor-led examinations, or definitive diagnostic conclusions.
   - Explicitly prohibits patient-specific prescription recommendations or medication dosage schedules.
   - Triage round 3 transitions to an educational summary with explicit diagnostic uncertainties instead of forcing a diagnosis.

4. **Provenance & Persistence Integrity**:
   - Retrieved document content is sanitized against prompt injections.
   - Citations only formatted when verified provenance metadata (title, URL) is present in retrieved chunks.
   - Failed or service-unavailable responses are flagged with `success=False` and excluded from SQLite database persistence and conversation rehydration.

---

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
- [x] Rate-limiter capacity flooding preserves active lockouts without eviction (SEC-02 / Phase 1D)
- [x] Step-wise independent atomic schema migrations with safe resumption verified (MIG-01 / Phase 1D)
- [x] Bounded per-conversation asyncio locking and clear/delete race guards implemented (Phase 1D / A02)
- [x] Clinical memory rehydration after restart and cache eviction verified (Phase 1D / A02)
- [x] Frontend AbortController and account switch state wipe verified (Phase 1D / A02)
- [x] Strict hard modality locking: missing specialist model returns HTTP 503 `model_unavailable` with zero fallback (A04 / Phase 2A)
- [x] Legitimate normal and negative findings preserved without disease promotion (A03 / Phase 2A)
- [x] X-ray anatomy classes identified as anatomy without fabricating fractures or abnormalities (A03 / Phase 2A)
- [x] Dataset artifacts filtered; top artifact yields `status="inconclusive"` without disease promotion (A03 / Phase 2A)
- [x] False confidence calibration removed; uncalibrated scores with prototype disclaimers displayed (A04 / Phase 2A)
- [x] Bounded LangGraph fallback routing with single-visit provider budgets verified (A05 / Phase 2B)
- [x] Infinite routing cycle between retriever and LLM terminated (A05 / Phase 2B)
- [x] Pure offline emergency gate active for cardiac, stroke, dyspnea, anaphylaxis, bleeding, and crisis (Phase 2B)
- [x] Physician impersonation, doctor claims, and clinical exam assertions eliminated (A17 / Phase 2B)
- [x] Forced diagnoses after round 3 and prescription dosage recommendations eliminated (A17 / Phase 2B)
- [x] Failed generations cleanly handled with service-unavailable response and non-persistence in DB (Phase 2B)
- [x] Complete backend test suite inventory verified (199 passed, 0 skipped, 0 failed)
- [x] Frontend build clean with lint passing (0 errors, 0 warnings, 11/11 tests pass)
- [ ] HF Space running status verified with live credentials (post-deployment)

