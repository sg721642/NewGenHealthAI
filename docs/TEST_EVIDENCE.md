# NewGenHealthAI — Test Evidence

## Environment

| Tool | Version |
|---|---|
| OS | macOS Darwin 27.0.0 arm64 |
| Python | 3.13.9 (Anaconda) |
| Node | v26.4.0 |
| npm | 11.17.0 |
| Git | 2.55.0 |
| Docker | Not installed |

## Phase 0 — Baseline Checks (2026-11-01)

### Frontend: `npm --prefix frontend ci`

```
Exit code: 0
Result: 21 vulnerabilities (2 low, 4 moderate, 12 high, 3 critical)
Note: npm audit warnings present; no install failure
```

### Frontend: `npm --prefix frontend run lint`

```
Exit code: 1

Errors (8):
  App.test.jsx:8:5    error  'global' is not defined  (no-undef)
  App.test.jsx:58:44  error  'options' is defined but never used  (no-unused-vars)
  setupTests.js:4-7   error  'global' is not defined x4  (no-undef)
  tailwind.config.js:28:15  error  'require' is not defined  (no-undef)
  vite.config.js:8:13  error  'process' is not defined  (no-undef)

Warnings (6):
  App.jsx:2285/2304/2321/2347/2359/2504  warning  React Hook missing dependency 'authHeaders'  (react-hooks/exhaustive-deps)

Root cause (A15): ESLint config only sets browser globals; test files need vitest/node globals;
tailwind.config uses CommonJS require in ESM; vite.config uses process.env without Node globals.
```

### Frontend: `npm --prefix frontend test`

```
Exit code: 1
Test files: 1
Tests: 4 failed, 0 passed

Error: TypeError: Cannot read properties of undefined (reading 'setItem')
  at App.test.jsx:19 (localStorage.setItem)

Root cause: Vitest happy-dom environment does not expose localStorage unless
--localstorage-file flag is provided (ExperimentalWarning shown). Test setup
at setupTests.js references 'global' which is also undefined (A15 interaction).
```

### Frontend: `npm --prefix frontend run build`

```
Exit code: 0
Output: backend/app/static/index.html  0.68 kB
        backend/app/static/assets/index-CB66vf3N.css  18.46 kB
        backend/app/static/assets/index-tBC-CYgL.js  392.80 kB
Result: ✅ Production build succeeds
```

### Backend: `python -m pytest backend/tests/`

```
Exit code: N/A (import error before any test ran)
Error: ModuleNotFoundError: No module named 'langgraph'

The full backend test suite requires:
  langgraph, torch, torchvision, transformers, chromadb,
  sentence-transformers, groq, edge-tts, langid, tavily-python

These are large ML dependencies not installed in the lightweight venv.
Lightweight subset test (test_database.py, test_logging.py) also blocked
because conftest.py imports app.main which triggers the ML import chain.

Status: 🚫 BLOCKED — Documented as concrete capability gap, not a pass.
```

### GitHub Remote Access

```
Command: git ls-remote https://github.com/sg721642/NewGenHealthAI.git HEAD
Exit code: 0
Output: 1605ec87683e735857ad3c0353fa0ce8feceffbe  HEAD
Status: ✅ Read access confirmed
```

### Push Access

```
Push test performed via actual Phase 0 commit (see IMPLEMENTATION_STATUS.md).
Status: ✅ Confirmed on branch fix/healthai-audit-premium-ui
```

## Phase 0 — Architecture Findings

### Backend API Structure
- FastAPI app at `backend/app/main.py`
- Routes: `/api/v1/auth`, `/api/v1/chat`, `/api/v1/sessions`, `/api/v1/history`, `/api/v1/voice`, `/api/v1/health`, `/api/v1/image`
- LangGraph workflow with triage → planner → llm_agent → retriever/tools → explanation nodes
- SQLite via SQLAlchemy at `backend/storage/chat_db/susham_health.db` (legacy name)
- PBKDF2 password hashing with fixed salt (A06)
- Session tokens: plain UUID, stored in DB, no expiry (A06)

### Frontend Structure
- React 19 + Vite 7 + DaisyUI 5 + Tailwind 4
- Single-file app: `frontend/src/App.jsx` (~2600 lines)
- Auth via localStorage (`auth_token`, `auth_user`)
- API calls use `fetch()` with stale `authHeaders` captured in callbacks (A10)
- Legacy name `Dr. Susham Biswas` visible in mentor panel (A16)

### Key Security Issues (Baseline)
- A01: No authentication guard on session list/read/delete endpoints
- A02: Conversation ownership not enforced — any session_id works
- A06: Fixed PBKDF2 salt — all users share same salt
- A07: Wildcard CORS with credentials (`allow_origins=["*"]`, `allow_credentials=True`)
- A08: TTS text sent as GET query parameter (URL-logged)
