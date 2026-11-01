# NewGenHealthAI — Audit Findings (A01–A18)

Commit audited: `1605ec87683e735857ad3c0353fa0ce8feceffbe`
Last updated: Phase 7B (Controlled Staging Preparation, CI Hardening, and Zero-Budget Readiness)

| ID | Priority | File(s) | Finding Summary | Status | Fix Phase |
|---|---|---|---|---|---|
| A01 | P0 | `dependencies.py`, `session.py`, `chat.py`, `database_service.py`, `voice.py` | Missing/invalid auth returned None. Anonymous list/read/delete paths allowed arbitrary data access. Fixed via `get_current_user` (401 on missing/invalid), query-param tokens eliminated completely, and strict owner-enforced database queries. Verified end-to-end in Phase 6 multi-user test suite (`test_phase6_multiuser_e2e.py`). | 🟢 Fixed | Phase 1A / Phase 1B / Phase 6 |
| A02 | P0 | `message.py`, `chat_service.py`, `session.py`, `chat.py`, `migrations.py`, `auth.py`, `App.jsx`, `requestManager.js` | `conversation_states` keyed by client-supplied session ID without ownership check. Fixed with `Conversation` entity, server-generated session IDs, memory keyed by `f"{user_id}:{session_id}"`, strict rejection of arbitrary/unknown client IDs, and safe quarantine migration. In Phase 1D: `ConversationLockManager` serializes concurrent turns per conversation with ref-counted cleanup; generational `_versions` and deletion tombstoning discard in-flight generations on clear/delete (returning 409 Conflict); frontend `AbortController` and session/user refs suppress stale in-flight responses across chat switching/logout; `BoundedRateLimiter` preserves active account lockouts under capacity flooding. In Phase 6: Centralized `RequestLifecycleManager` tracks `authGeneration`, `currentUserId`, and category abort controllers, eliminating stale out-of-order responses and multi-user context leakage. | 🟢 Fixed | Phase 1A / Phase 1B / Phase 1C.1 / Phase 1D / Phase 6 |
| A03 | P0 | `disease_classifier.py`, `image_api.py`, `App.jsx` | `GARBAGE_CLASSES` split into `DATASET_ARTIFACT_CLASSES` and `VALID_NEGATIVE_CLASSES`. Legitimate negative/normal classes preserved as top findings without disease promotion (normal=0.96/pneumonia=0.04 returns normal reference finding). X-ray anatomy classes (wrist=0.95) interpreted as anatomical locations (`finding_type='anatomy_identified'`) without diagnosing fractures or manufacturing abnormalities. Artifact top predictions return `status='inconclusive'`. | 🟢 Fixed | Phase 2A |
| A04 | P0 | `disease_classifier.py`, `image_api.py`, `App.jsx` | Strict hard modality lock enforced: executes ONLY the matching specialist model (`skin`, `xray`, `retina`, `general`). Missing specialist model returns `status='model_unavailable'` (HTTP 503); eliminates all fallback to general or running all models. Non-medical images return `status='unsupported_image'` (HTTP 422). CLIP failure or ambiguity returns `status='inconclusive'` (HTTP 200). Eliminated false confidence calibration (returns raw uncalibrated score with prototype disclaimers). | 🟢 Fixed | Phase 2A |
| A05 | P1 | `langgraph_workflow.py`, `core/state.py`, `core/urgent_care.py`, `agents/*.py`, `chat_service.py` | Bounded acyclic fallback DAG implemented with single-visit budget per provider per turn (`retriever` -> `llm_agent` -> `wikipedia` -> `tavily` -> `executor`). Infinite routing cycle terminated. Clean service-unavailable exhaustion handling with `is_failed_generation` and DB non-persistence. Pure offline emergency gate intercepts acute red flags before triage. Phase 2B.1: Added wall-clock consultation deadline (`CONSULTATION_TIMEOUT_SECONDS=90s`) with native `asyncio.wait_for`, guaranteed lock release on timeout/cancellation, `exhaustion_reason` flag preventing secondary post-exhaustion LLM calls, and unified result-state taxonomy. Phase 3A (Correction A): Wrapped synchronous fallback invocation in `asyncio.to_thread` within `asyncio.wait_for`, guaranteeing that slow synchronous provider runs cannot bypass the consultation deadline or block lock release. | 🟢 Fixed | Phase 2B / Phase 2B.1 / Phase 3A |
| A06 | P1 | `models/message.py`, `auth.py`, `database_service.py`, `main.py`, `migrations.py` | Argon2id hashing with unique per-password random salts. Safe PBKDF2 migration rehash via optimistic concurrency. 256-bit entropy tokens stored as SHA-256 hashes (`token_hash`) with expiration (`expires_at`) and immediate revocation. Starlette key persistent via `SESSION_SECRET_KEY`. Phase 1C.1: SEC-01 trusted proxy validation (`TRUSTED_PROXIES`), SEC-02 bounded in-memory rate limiting with per-account lockouts, MIG-01 atomic staging migration with pre-cutover validation and rollback, and MIG-02 fail-closed quarantine for missing users table. Phase 6: Verified immediate token revocation on logout rejects subsequent requests with 401 Unauthorized. | 🟢 Fixed | Phase 1C / Phase 1C.1 / Phase 6 |
| A07 | P1 | `main.py`, `image_preprocess.py`, `image_api.py`, `audio_preprocess.py`, `voice_capacity.py`, `voice.py`, `core/config.py`, `App.jsx` | Wildcard CORS with credentials (`allow_origins=["*"]`, `allow_credentials=True`) fixed in Phase 1C. Phase 3A: Complete image upload security and resource protection: chunked reading (64KB), max upload size enforcement (`MAX_IMAGE_UPLOAD_BYTES=5MB`), magic byte signature verification (JPEG, PNG, WebP only), Pillow decompression bomb protection (`MAX_IMAGE_PIXELS=16MP`, `MAX_IMAGE_DIMENSION=4096px`), EXIF orientation transposition and complete metadata stripping to clean raster buffers; bounded process-local inference semaphore (`MAX_CONCURRENT_INFERENCE=2`, queue timeout 5.0s -> 503 `model_unavailable`) and per-user limit (max 1 active -> 429). Phase 3B: Complete voice upload validation and capacity protection: chunked reading (64KB chunks), upload size boundaries (`MIN_AUDIO_UPLOAD_BYTES=500B`, `MAX_AUDIO_UPLOAD_BYTES=10MB`), audio container magic byte validation (WAV, WebM, OGG, MP3, M4A, FLAC), WAV duration probing (`MAX_AUDIO_DURATION_SECONDS=300s`), secure tempfile isolation (`0o700` dir, `0o600` file) with deterministic `finally:` cleanup, and process-local `VoiceCapacityManager` (`MAX_CONCURRENT_STT=3`, `MAX_CONCURRENT_TTS=5`, queue wait 5.0s -> 503, per-user limit 1 active -> 429, auto-releasing permits). Phase 4: Made `VoiceCapacityManager` cancellation-safe. Phase 6: Added client-side image size (>5MB) and MIME type pre-validation in frontend, Object URL tracking and revocation, file input reset, and recording session cancellation token (`voiceSessionTokenRef`) releasing late media tracks. | 🟢 Fixed | Phase 1A / Phase 1C / Phase 3A / Phase 3B / Phase 4 / Phase 6 |
| A08 | P1 | `voice.py`, `audio_preprocess.py`, `voice_capacity.py`, `App.jsx`, `triage_agent.py`, `wikipedia.py`, `tavily.py`, `executor.py`, `MessageComposer.jsx`, `MessageBubble.jsx` | TTS text sent as GET query parameter (URL-logged). STT logs transcript excerpts. Raw exception strings returned to clients. Fixed in Phase 1B/1C: TTS converted to POST with JSON body and Bearer token; frontend revokes Blob URLs; STT transcript logging removed (character count only); error responses sanitized. Phase 2B.1: External search privacy protection in Wikipedia and Tavily using strict generic medical term allowlist (`_MEDICAL_TERM_ALLOWLIST`); raw question retry fallback removed; non-medical queries declined for external search to prevent personal symptom leaks; question text redacted from triage logs (character count only); exception logging across agents redacted to `type(e).__name__` only. Phase 3B: Non-blocking `AsyncGroq(timeout=15s)` with overall request deadline `STT_OVERALL_DEADLINE_SECONDS=30s` via `asyncio.wait_for`; bounded fallback (`whisper-large-v3-turbo` -> `whisper-large-v3`) with fail-fast on 400/401 and zero synthetic transcripts (returning 503/504); hardened POST `/voice/tts` (`2..2000` chars, markdown stripping, language-keyed voice allowlists, `Cache-Control: no-store, no-cache`, and client disconnect handling); full sensitive voice log redaction (no filenames, transcripts, spoken text, audio payloads, or raw exception strings); frontend `AbortController` for STT and TTS across unmount, consultation switch, and logout. Phase 4: Bounded TTS streaming resources (`TTS_STREAM_TIMEOUT_SECONDS=30.0s`, `MAX_TTS_STREAM_BYTES=5MB`). Phase 6: Complete removal of client-side sensitive logging (queries, transcripts, audio payloads, error bodies) from `console.*` methods. | 🟢 Fixed | Phase 1B / Phase 1C / Phase 2B.1 / Phase 3B / Phase 4 / Phase 6 |
| A09 | P1 | `disease_classifier.py`, `image_ai_service.py`, `image_api.py`, `conftest.py` | Models initialized at import time; classifier constructor downloaded weights. Phase 1A added lazy ML imports for test isolation. Phase 3A: Completely eliminated runtime `torch.__version__ = "2.6.1"` hack, loading PyTorch checkpoints with `weights_only=True` without spoofing. Implemented lazy on-demand model loading with double-checked locking stampede protection (`_model_load_locks`). Explicit lifecycle tracking (`unloaded`, `loading`, `ready`, `unavailable`, `failed`). Guarded HF and CLIP downloads behind `ALLOW_MODEL_DOWNLOADS` (defaults to false). Removed module-level BLIP imports and downloads from `image_ai_service.py`, disabling BLIP by default (`ENABLE_BLIP_CAPTIONING=false`) with safe generic non-medical fallback captions. Sanitized public diagnostics endpoint (`base_dir` and filesystem paths removed). | 🟢 Fixed | Phase 1A / Phase 3A |
| A10 | P1 | `App.jsx`, `requestManager.js` | Callbacks capture stale `authHeaders`. Login state trusted from localStorage without server validation. New-chat session ID discarded. Fixed in Phase 1A/1B/1C: session ID captured, authHeaders in dependencies, mount-time token validation against `/api/v1/auth/me`, logout state wipe. Phase 6: Centralized `RequestLifecycleManager` validates auth generation and active user ref for every fetch response, strictly preventing out-of-order race conditions from mutating state. | 🟢 Fixed | Phase 1A / Phase 1B / Phase 1C / Phase 6 |
| A11 | P1 | `session.py`, `chat_service.py`, `App.jsx` | `/clear` resets memory only; old messages remain in SQLite. Delete history does not clear memory. Memory does not hydrate from saved messages after restart. Fixed in Phase 1A (Clear resets both DB and memory; Delete removes both). Fixed in Phase 1D: `_get_or_restore_state` automatically rehydrates conversation memory from SQLite history after backend restarts or LRU cache evictions (bounded to `MAX_RESTORE_TURNS=20`, excluding failed assistant generations). Phase 6: `/clear` explicitly supplies `X-Session-ID` header, backend validates ownership authoritatively, and client-side misleading messages on 404 responses are eliminated. | 🟢 Fixed | Phase 1A / Phase 1D / Phase 6 |
| A12 | P1 | `frontend/public/index.html`, `frontend/index.html`, `frontend/package.json`, `frontend/Dockerfile`, `Dockerfile`, `backend/Dockerfile` | Obsolete duplicate `frontend/public/index.html` (with MediGenius branding and missing script) deleted. Added medical AI `favicon.svg`. Canonical `frontend/index.html` updated with NewGenHealthAI branding and meta description. Added `build:standalone` to `package.json`. Updated `frontend/Dockerfile` to use standalone build and copy `/app/dist` to Nginx html. Root `Dockerfile` multi-stage build updated to build standalone into `dist` and copy into `/app/backend/app/static`, non-root user `user` (UID 1000), directory ownership, and `/api/v1/health` healthchecks. Hardened `backend/Dockerfile` with non-root user and healthcheck. | 🟢 Fixed | Phase 4 |
| A13 | P1 | `backend/pyproject.toml`, `requirements.txt`, `backend/requirements.txt`, `README.md` | Reconciled dependency manifests: renamed backend pyproject to `newgenhealthai-backend`, updated maintainer to `Satyam Gupta <sg721642@gmail.com>`, removed unused `tensorflow==2.15.0`, and aligned all dependencies with canonical `requirements.txt`. Reconciled root `README.md` with accurate architecture diagrams, endpoints, verified run instructions, and authentic contributor credits. | 🟢 Fixed | Phase 4 |
| A14 | P1 | `run.py`, `run_medai.bat` | Hardened multi-platform launcher: completely eliminated runtime `torch.__version__ = "2.6.1"` monkeypatch, resolved all paths dynamically relative to `__file__`, eliminated `shell=True` subprocess execution, added graceful child process termination on SIGINT/SIGTERM to prevent orphaned background workers, and implemented automated `/api/v1/health` readiness polling. Cleaned `run_medai.bat` branding and removed hardcoded models directory blocker. | 🟢 Fixed | Phase 4 |
| A15 | P2 | `eslint.config.js`, `setupTests.js`, `tailwind.config.js`, `vite.config.js`, `App.test.jsx`, `App.jsx` | ESLint lacked test/Node globals. `global` undefined in test setup. CommonJS `require` in ESM tailwind. `process` undefined in vite.config. Phase 1B resolved all React Hook ESLint warnings (0 errors, 0 warnings). Phase 6 verified 0 ESLint errors and 0 warnings across all modern components. | 🟢 Fixed | Phase 0 / Phase 1B / Phase 6 |
| A16 | P2 | `package.json`, `logging_config.py`, `voice.py`, `App.jsx`, `test_logging.py`, `.env.example`, `README.md`, `docs/*.pdf` | Legacy names (`dr-susham-health-ai`, `susham_health`, `Dr. Susham Biswas`) eliminated from source code. Static password salt moved to external `LEGACY_PBKDF2_SALT`. Default DB path `susham_health.db` deliberately documented and preserved for backward database compatibility. Replaced `.env.example` with comprehensive 113-line configuration reference across 8 structured sections. Root `README.md` reconciled with authentic contributors (Satyam Gupta, Khagesh Ranjan, Sudipto Ghosh, Ajitesh Baghel, Yuvraj Singh). Tracked project PDFs inspected and confirmed clean of legacy branding. | 🟢 Fixed | Phase 0 / Phase 1C / Phase 4 |
| A17 | P1 | `triage_agent.py`, `llm_agent.py`, `executor.py`, `chat_service.py`, `core/urgent_care.py`, `image_api.py` | Prompts de-escalated to automated educational intake assistant. Physician/doctor impersonation, clinical exam claims, and prescription/dosage guidance eliminated. Triage round 3 transitions to educational summary with explicit diagnostic uncertainty instead of forcing diagnosis. Strict non-persistence of failed generations. Phase 2B.1: Added India 112 emergency routing and 24/7 crisis hotlines; safe default fallback for unlisted countries without inferring country from symptoms; conservative emergency language ("may be experiencing"); explicitly acknowledged heuristic screening does not detect 100% of emergencies; hardened provenance citation URLs to HTTPS-only with markdown escaping. Phase 3A: Corrected Indian crisis services in `urgent_care.py` to verified accurate entries (Tele-MANAS 24/7 at 14416, Vandrevala Foundation 24/7 at +91 9999 666 555, iCALL with verified non-24/7 hours Mon-Sat 10:00 AM - 8:00 PM IST, 112 for danger). Hardened `get_medical_info` in `image_api.py` to present model detections as prototype findings rather than confirmed clinical diagnoses, with automatic non-disease guidance for anatomy-only and normal reference findings and strict prohibition on drug dosages. | 🟢 Fixed | Phase 2B / Phase 2B.1 / Phase 3A |
| A18 | P1 | `.github/workflows/docker-ci.yml`, `pytest.ini`, `backend/scripts/verify_clip_routing.py` | CI logs dumped registration responses containing cleartext session bearer tokens. Container health polling loop completed normally without failing on timeout. Pytest root discovery collected standalone scripts as test fixtures. Fixed in Phase 7B: completely redacted bearer tokens in CI logs, asserted HTTP status codes and token length, enforced explicit `exit 1` on container health polling timeout, configured root `pytest.ini` (`testpaths = backend/tests`), and moved manual routing test to `backend/scripts/verify_clip_routing.py`. | 🟢 Fixed | Phase 7B |

## Section 11 Follow-up Verifications & Technical Clarifications

### A. Consultation Timeout Behavior (`asyncio.to_thread` vs Worker Sockets)
Phase 3A implemented `asyncio.to_thread` wrapped in `asyncio.wait_for(..., timeout=CONSULTATION_TIMEOUT_SECONDS)` for the synchronous fallback workflow. When the timeout expires, the ASGI event loop raises `asyncio.TimeoutError`, releases the conversation lock in `_LockContext.__aexit__`, and returns HTTP 504 Gateway Timeout to the client immediately.
**Technical Limitation**: In standard CPython, terminating a thread executing blocking I/O (such as a synchronous socket read inside a C library) cannot be done forcibly without terminating the process. Therefore, while the event loop and user request are completely protected from indefinite blocking, the background worker thread may continue waiting for socket timeout or OS TCP teardown before terminating.

### B. Model Loading Clarification (Lazy Weights vs Framework Imports)
Phase 3A established lazy model loading for specialist classifiers via `get_specialist_model()`, loading `.pth` weight checkpoints strictly on demand with stampede locks.
**Distinction**: This lazy loading applies to the model instances and checkpoint files. The top-level PyTorch framework imports (`import torch`) in `disease_classifier.py` execute when the Python module is first imported. In test and headless CI environments where PyTorch or torchvision are absent or heavy, mock objects or guarded imports in `conftest.py` ensure test isolation.

### C. Async Integration Test Coverage Gap
Phase 1D implemented generational versioning (`_versions`) and deletion tombstoning (`_deleted_sessions`) to detect when a conversation is cleared or deleted while an LLM inference request is in flight.
**Test Gap**: Existing automated tests simulate this behavior by injecting delays into the workflow node or mocked runner. A full end-to-end asynchronous test involving live streaming against a real external LLM provider under active network packet transmission remains an open integration verification gap until staging deployment.

## Section 12 Phase 6 Verification & Regression Closures

### 1. Request Isolation & Centralized Lifecycle
- Introduced `RequestLifecycleManager` in `frontend/src/utils/requestManager.js`.
- Protects 5 request categories (`chat`, `image`, `sessions`, `history`, `auth`) with dedicated `AbortController` instances.
- Tracks monotonic `authGeneration` and `currentUserId`. Whenever a user logs out or switches accounts, pending requests are aborted and subsequent completion callbacks fail the `.isValid()` check, guaranteeing zero state cross-talk.

### 2. Immediate Safe Logout
- On user logout, auth state (`auth_token`, `auth_user`) in `localStorage` is removed immediately, `authGeneration` is incremented, and UI flips to unauthenticated `AuthPage` instantly.
- Server-side revocation (`POST /api/v1/auth/logout`) executes in the background without blocking the UI transition.

### 3. Patient Privacy & Zero Console Leaks
- Client console output (`console.log`, `console.warn`, `console.error`) across `App.jsx`, `MessageComposer.jsx`, and `MessageBubble.jsx` was stripped of sensitive payload data (symptom descriptions, medical queries, diagnoses, transcripts, error responses).
- Verified via Vitest integration tests asserting zero occurrences of synthetic medical phrases in console spies.

### 4. Medical Image Upload Client Validation
- Added client-side size check (rejects files > 5MB with an informative toast before making any network call).
- Added client-side MIME check (JPEG, PNG, WebP only).
- Tracked and revoked all Object URLs via `createdObjectURLsRef` across clear, delete, logout, unmount, or image replacement.
- File input value is reset after selection to allow uploading the same image file consecutively.

### 5. Voice Recording Cancellation Safety
- Added `voiceSessionTokenRef` to isolate recording sessions.
- Cancelling recording prevents `mediaRecorder.onstop` from initiating a transcription request.
- Late-resolving `getUserMedia` streams are tracked and their tracks stopped immediately if user cancelled before the promise resolved.

### 6. WCAG 2.1 AA Accessibility Hardening
- `ConfirmationModal`: Implemented Tab / Shift+Tab keyboard focus trap and restoration of previous active element focus upon close.
- `AuthPage`: Added WAI-ARIA roving arrow-key navigation for login/register tabs with `role="tabpanel"`.
- `Sidebar.jsx`: Removed nested interactive control violation (`role="button"` div containing `<button>`), providing a dedicated `.session-select-btn` sibling button.

### 7. Real Browser QA (Playwright Chromium)
- Automated browser testing across 5 viewports (1440×900, 1280×800, 768×1024, 390×844, 320×700).
- 9 real PNG screenshots captured in `docs/screenshots/`.
- Zero horizontal overflow (`scrollWidth <= clientWidth`) verified across all viewports.
- Zero browser console errors and unhandled exceptions detected.

### 8. End-to-End Multi-User Security Suite
- Created `backend/tests/test_phase6_multiuser_e2e.py` (8 automated tests).
- Verified User A vs User B consultation isolation, cross-account access denial, 404 fail-closed behavior, immediate token revocation on logout, and concurrent multi-user execution.

## Section 13 Phase 7A Container Verification, Storage Persistence & Full-Stack Acceptance

### 1. Deterministic Container Dependencies & Strict Reproducibility
- Resolved `torchvision` unpinned gap by pinning `torchvision==0.24.1` canonically alongside `torch==2.9.1` across `backend/pyproject.toml`, `backend/requirements.txt`, and `requirements.txt`.
- Eliminated non-deterministic `|| npm install` fallback in `Dockerfile` and `frontend/Dockerfile`, enforcing strict `npm ci`.
- Added missing runtime media and graphics packages (`ffmpeg`, `libgl1`, `libglib2.0-0`) to Stage 2 Python runtime in Dockerfile.
- Created `.github/workflows/docker-ci.yml` to build, run, and test the unified container with non-root UID 1000 in an automated Ubuntu runner.

### 2. Full-Stack Browser QA vs Mock Visual QA Boundary
- **Mock Visual QA (`frontend/scripts/browser_qa.cjs`)**: Retained as a fast, client-side CSS/DOM layout test running against lightweight node mock endpoints across 5 viewports (9 screenshots).
- **Real Full-Stack Acceptance QA (`frontend/scripts/fullstack_browser_qa.cjs`)**: Spawns real FastAPI backend with an isolated SQLite DB (`/tmp/test_fullstack_phase7a.db`) and unified built React frontend. Exercises authentic registration, login token generation, message dispatch, real SQLite DB query, session switching with SQLite rehydration, conversation clearing, logout token revocation (401), cross-account denial (404), and unconfigured STT/vision graceful 503 degradation across 5 viewports (5 screenshots).

### 3. Database Persistence & Ephemeral Storage Boundary
- `backend/tests/test_phase7a_persistence.py` confirmed 100% data survival across complete database engine termination and reconnection.
- Verified and documented that containers without a mounted persistent volume (e.g. Hugging Face Spaces `/data` volume) will lose state upon container recreation/restart.

## Section 14 Phase 7B CI Hardening, Zero-Budget Protocol & Release Preparation

### 1. CI Log Sanitization & Bearer Token Redaction (A18)
- In `.github/workflows/docker-ci.yml`, the user registration response was previously dumped to stdout via `echo "Registration response: $REG_RES"`, exposing the session token in GitHub Actions runner logs.
- Remediated by removing stdout echoing of `$REG_RES`, parsing the token silently, verifying its length without displaying the value (`echo "Synthetic user registered successfully; bearer token acquired (redacted, length: ${#TOKEN})"`), and verifying authenticated endpoints via HTTP response codes (`SESS_STATUS=200`).

### 2. Readiness Polling Failure Enforcement (A18)
- In `.github/workflows/docker-ci.yml`, the healthcheck polling loop (30 attempts with 2s sleep) completed with exit code 0 even if all attempts failed.
- Hardened with explicit flag check: if `READY != 1` after 30 attempts (60s), the step exits immediately with code 1 (`exit 1`), preventing silent timeout bypass.

### 3. Pytest Discovery & CLI Tool Isolation
- Running pytest from root previously collected `backend/test_clip_routing.py` because its name matched `test_*.py` and lacked pytest fixtures.
- Configured root `pytest.ini` with `testpaths = backend/tests` and relocated `backend/test_clip_routing.py` to `backend/scripts/verify_clip_routing.py`. Verified clean test collection and 310/310 passing tests.

### 4. Zero-Budget Protocol & Isolation Boundary (Budget: Strictly ₹0)
- Enforced strict project governance: 0 paid subscriptions, 0 paid hardware upgrades, 0 paid persistent storage tiers, and 0 external Hugging Face Space creations.
- Existing production Space (`https://huggingface.co/spaces/sg721642/NewGenHealthAI`) remains 100% unmodified and untouched.
- Clarified Hugging Face Spaces pricing model: while CPU Basic compute incurs no hourly charge ($0/hr), creating a new Space with the Docker SDK generally requires a paid account plan (such as HF PRO at $9/mo) or payment card verification; creating a new private Docker staging Space cannot be characterized as guaranteed free ($0).
- Zero-cost verification and presentation workflows are executed via local deployment (`python run.py`) or free public GitHub Actions runners (`ubuntu-latest`).

### 5. GitHub Actions Runner Node Runtime Modernization
- GitHub Actions runners announced deprecation of Node.js 20 runtime for actions (`actions/checkout@v4`, `actions/setup-node@v4`).
- Modernized `.github/workflows/docker-ci.yml` by updating to `actions/checkout@v7` and `actions/setup-node@v7`, which execute on the Node 24 action runtime while preserving the Node.js 20 build target for frontend compilation, eliminating runner deprecation warnings.

### 6. Production Space Baseline & Ephemeral Storage Risk Analysis
- Recorded authoritative production baseline commit `dadb57ad4088a280c2aab9b3781ff42a4a30df25` on `https://huggingface.co/spaces/sg721642/NewGenHealthAI`.
- Analyzed container lifecycle risks on Hugging Face Spaces: without a mounted persistent volume, any container rebuild permanently deletes the ephemeral SQLite database (`/app/backend/storage/chat_db/susham_health.db`).
- Documented that public persistent-user deployment must be marked BLOCKED until persistent block storage or an external relational database (e.g., PostgreSQL) is attached.
- Authored step-by-step reversible deployment procedure with atomic rollback command (`git push -f huggingface dadb57ad4088a280c2aab9b3781ff42a4a30df25:main`).
- Reconfirmed that zero pushes to external spaces were performed under the strict ₹0 budget constraint.

## A16 Preservation Notes

The following legacy identifiers were intentionally preserved for database compatibility:
- `backend/app/core/config.py`: Default DB path `susham_health.db` — rename with database file migration
- Note: Static password salt was completely removed from source code in Phase 1C and moved to external migration-only configuration (`LEGACY_PBKDF2_SALT`)

## Legend

- 🔴 Open — Not yet remediated
- 🟡 Partial — Partially addressed; remaining work documented
- 🟢 Fixed — Remediation committed and verified
