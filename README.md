---
title: NewGenHealthAI
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 7860
---
<div align="center">

# 🩺 NewGenHealthAI

### A College Academic Capstone Project & Educational Healthcare AI Demonstration

<br/>

🚀 **Live Demonstration on Hugging Face Spaces**

[https://huggingface.co/spaces/sg721642/NewGenHealthAI](https://huggingface.co/spaces/sg721642/NewGenHealthAI)

[![Hugging Face Spaces](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Spaces-blue)](https://huggingface.co/spaces/sg721642/NewGenHealthAI)
[![Backend Tests](https://img.shields.io/badge/pytest-480%20passed-brightgreen)](https://github.com/sg721642/NewGenHealthAI/actions)
[![Frontend Tests](https://img.shields.io/badge/vitest-36%20passed-brightgreen)](https://github.com/sg721642/NewGenHealthAI/actions)
[![Docker CI](https://img.shields.io/badge/docker%20ci-verified%20green-success)](https://github.com/sg721642/NewGenHealthAI/actions)
[![Academic Demonstration](https://img.shields.io/badge/project-academic%20capstone-orange)](https://github.com/sg721642/NewGenHealthAI)

<br/>

</div>

---

## Academic Project Overview & Problem Statement

**NewGenHealthAI** is a college academic capstone project and educational prototype engineered to explore safe human-AI interaction in clinical health intake and triage support.

### The Problem
Patients and students seeking health information online often encounter generic search engines or unconstrained chatbots that:
1. Hallucinate speculative medical diagnoses.
2. Generate unsafe drug dosage recommendations.
3. Delay emergency care during acute life-threatening events.
4. Leak sensitive personal health data across sessions or through insecure logging.
5. Suffer from concurrency race conditions and context contamination.

### The Academic Solution
NewGenHealthAI addresses these critical engineering challenges through a **safety-first, fail-closed architecture**:
* **Rule-Based Red-Flag Emergency Screening:** Pure offline, zero-dependency screening in `urgent_care.py` performs deterministic pattern matching for acute red flags (cardiac symptoms, stroke signs via FAST criteria, severe respiratory distress, anaphylaxis, massive hemorrhage, acute mental health crisis) and directs users to emergency services without waiting for LLM completion. (Note: rule-based screening does not detect 100% of emergencies and must never replace qualified clinical triage).
* **Bounded Acyclic Clinical Workflow:** A deterministic LangGraph directed acyclic graph (DAG) enforces single-visit provider budgets, preventing infinite query loops and bounding consultation time to a strict 90-second wall-clock deadline.
* **No Physician Impersonation or Forced Diagnosis:** The system operates strictly as an educational assistant. It acknowledges uncertainty, presents educational considerations, cites verified medical sources, and explicitly prohibits prescription recommendations, clinical diagnosis, or drug dosages.
* **Fail-Closed Clinical Specialist Gates:** Unvalidated specialist diagnostic models (skin lesion analysis, bone/chest X-ray classification, retinal fundus screening, general pathology) are disabled by default in production runtime (`ENABLE_CLINICAL_SPECIALIST_MODELS=false`, returning `clinical_analysis_disabled`).
* **Non-Medical Image Recognition:** A lightweight neural classifier (MobileNetV3-Small) identifies non-medical everyday objects (ImageNet-1K) to prevent processing non-relevant imagery through clinical pipelines.
* **Privacy-Hardened Security & Isolation Layer:** Centralized Bearer token authentication, Argon2id password hashing, SHA-256 token hashing, per-conversation turn serialization (`ConversationLockManager`), prompt injection sanitization, and targeted server log sanitization (omitting audio payloads, transcription text, TTS text, and exception tracebacks from application logs, recording character/byte counts and exception types instead).

> [!WARNING]
> **Academic Project & Clinical Safety Disclaimer**
> NewGenHealthAI is developed strictly for **academic demonstration, educational presentation, and engineering research purposes**. It is **NOT** a certified medical device and does **NOT** provide clinical diagnosis, medical treatment, prescription recommendations, or clinical decision-making.
>
> Model observations, intake suggestions, and chat responses are uncalibrated experimental outputs and must **NEVER** replace professional judgment from a licensed healthcare provider.
>
> **In a Medical Emergency:**
> If you or someone around you is experiencing acute symptoms (severe chest pain, sudden numbness/paralysis, difficulty breathing, allergic shock, or severe trauma), immediately call the national emergency services:
> - **India Emergency Number:** **112** (Unified Emergency Response Support System)
> - **Ambulance:** **108**
> - **National Mental Health Crisis Helpline (Tele-MANAS):** **14416** (24/7 Toll-Free)
> - Or proceed immediately to the nearest hospital emergency department.

---

## System Architecture

```
                                       ┌──────────────────────────────────────────┐
                                       │   React 19 + Vite + DaisyUI SPA          │
                                       │   - Editorial Clinical Theme ("Calm")    │
                                       │   - RequestLifecycleManager (Lifecycle)  │
                                       │   - Responsive Drawer & Touch Targets    │
                                       └─────────────────────┬────────────────────┘
                                                             │
                                         Bearer Token Auth / TLS (HTTP & JSON Streaming)
                                                             │
                                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Backend Application (Python 3.12 / 3.13)                                                       │
├──────────────────────────────┬───────────────────────────────┬─────────────────────────────────────────┤
│ Security & Isolation Layer   │ Clinical Intake Workflow      │ Multimodal AI Engines                   │
│ • Centralized Bearer Auth    │ • LangGraph Bounded DAG       │ • Everyday Vision (MobileNetV3-Small)   │
│ • Argon2id Password Hashing  │ • Pure Offline Red-Flag Gate  │   1000-class ImageNet-1K classifier     │
│ • SHA-256 Token Storage      │ • Single-visit node budget    │ • Fail-Closed Specialist Gate           │
│ • Bounded Rate Limiting      │ • 90s Consultation Deadline   │   (Skin, X-ray, Retina, Pathology       │
│ • Trusted Proxy IP Shield    │ • No Physician Impersonation  │   disabled in prod: status 503/disabled)│
│ • Conversation Lock Manager  │ • No Drug Dosages / Diagnosis │ • Image Sanitize: EXIF stripping,       │
│ • Generational Race Guards   │ • Verified HTTPS Provenance   │   16MP bomb limit, magic bytes check    │
├──────────────────────────────┴───────────────────────────────┴─────────────────────────────────────────┤
│ Voice Processing Pipeline                                                                              │
│ • Chunked Upload (500B..10MB) & Container Magic Byte Verification (WAV, WebM, OGG, MP3, M4A, FLAC)     │
│ • Private Temporary Files (0o700 dir / 0o600 file) with Deterministic Cleanup in `finally:` blocks    │
│ • Non-Blocking AsyncGroq (timeout=15s) with Overall Deadline (30s) & Whisper Fallback Progression      │
│ • Process-Local Concurrency Semaphores (STT=3, TTS=5, wait timeout=5.0s, per-user limit=1)             │
│ • Hardened Edge TTS Streaming (2..2000 chars, markdown stripping, language-keyed voice allowlists)     │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Persistence & Ephemeral Container Storage                                                              │
│ • SQLite in WAL Mode with Online Backup API and `PRAGMA integrity_check`                               │
│ • Step-wise Atomic Schema Migrations (v1: conversation ownership/quarantine; v2: SHA-256 sessions)     │
│ • Ephemeral Container Boundary: In standard container platforms (e.g. Hugging Face Spaces), SQLite     │
│   state resets on container restart unless a persistent storage volume is mounted to `backend/storage/`│
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## AI & ML Components

| Component | Technology / Model | Execution Context | Implemented Capability & Operational Boundary |
|---|---|:---:|---|
| **Conversational Triage** | Groq Cloud Chat LLM (`GROQ_CHAT_MODEL`, default `openai/gpt-oss-120b`, fallback `openai/gpt-oss-20b,qwen/qwen3.8-27b`) via LangGraph | Cloud API (Async) | Conducts multi-turn conversational health intake; structures symptom summaries; cites verified sources; strictly bounded to 90s; no drug dosages. |
| **Emergency Red-Flag Gate** | Deterministic Keyword & Pattern Rule-Engine | Pure Local (Offline) | Detects acute emergencies (cardiac, stroke, anaphylaxis, dyspnea, trauma, self-harm); bypasses LLM; issues immediate **112 / 108 / 14416** advisories. |
| **Everyday Object Vision** | MobileNetV3-Small (`mobilenet_v3_small-047dcff4.pth`) | Local CPU (~50ms) | 1,000-class closed-set ImageNet-1K recognition for everyday objects (food, plants, household items); prevents non-medical images from clinical routing. |
| **Specialist Medical Vision** | tf_efficientnet_b4_ns, DenseNet-121, EfficientNet-B0, ResNet-18 | Local CPU (Gated) | **Disabled by default in production** (`ENABLE_CLINICAL_SPECIALIST_MODELS=false`); returns `clinical_analysis_disabled`. Not clinically validated. |
| **Speech-to-Text (STT)** | Groq Whisper (`whisper-large-v3-turbo` → `whisper-large-v3`) | Cloud API (Async) | Transcribes spoken user audio; magic-byte container validation; temporary file isolation; omits transcripts and audio bytes from server logs; fail-closed on errors. |
| **Text-to-Speech (TTS)** | Microsoft Edge TTS (`edge-tts`) | Streaming (Async) | Synthesizes educational responses; strips markdown formatting; enforces 2–2000 character boundaries; neural voice allowlists; anti-caching headers. |

---

## Repository Structure

```text
NewGenHealthAI/
├── .github/
│   └── workflows/
│       └── docker-ci.yml        # CI: Backend Pytest, Frontend Vitest, Docker Smoke Test
├── backend/
│   ├── app/
│   │   ├── agents/              # LangGraph nodes (triage, retriever, wikipedia, tavily, executor)
│   │   ├── api/
│   │   │   ├── v1/              # Version 1 route controllers (auth, chat, health, session, voice)
│   │   │   └── image_api.py     # Image analysis and diagnostics endpoints
│   │   ├── core/                # Configuration, logging, dependencies, urgent care gate
│   │   ├── db/                  # SQLite session factory, migrations, online backup API
│   │   ├── models/              # SQLAlchemy models (User, UserSession, Conversation, Message)
│   │   ├── schemas/             # Pydantic validation schemas
│   │   ├── services/            # DatabaseService, ClinicalEngine, DiseaseClassifier, VisionService
│   │   └── tools/               # Image/audio preprocessing, capacity managers, PDF loader
│   ├── tests/
│   │   ├── fixtures/
│   │   │   ├── synthetic_images/# Git-tracked synthetic image fixtures for reproducible CI
│   │   │   ├── genuine_everyday_images/ # Ignored local everyday evaluation images
│   │   │   └── genuine_clinical_images/ # Ignored local clinical evaluation images
│   │   ├── test_*.py            # 23 comprehensive pytest modules (480 automated tests)
│   │   └── conftest.py          # Pytest fixtures and mock isolation
│   ├── Dockerfile               # Standalone backend container
│   ├── pyproject.toml           # Backend packaging and dependency definitions
│   └── requirements.txt         # Production and testing Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # Modular UI components (ChatTimeline, MessageBubble, Composer, etc.)
│   │   ├── hooks/               # Custom hooks (useIsMobile)
│   │   ├── pages/               # AuthPage, etc.
│   │   ├── utils/               # requestManager, formatters
│   │   ├── App.jsx              # Application state coordinator and lifecycle orchestrator
│   │   ├── App.test.jsx         # 36 Vitest integration and component tests
│   │   └── index.css            # Calm Precision design system tokens and responsive styles
│   ├── Dockerfile               # Standalone frontend container (Nginx SPA)
│   ├── nginx.conf               # Standalone Nginx configuration
│   ├── package.json             # Frontend dependencies and build scripts
│   └── vite.config.js           # Vite configuration (integrated and standalone modes)
├── docs/                        # Engineering documentation, status, and release manifests
├── .dockerignore                # Container exclusion rules
├── .env.example                 # Comprehensive 124-line environment template
├── .gitignore                   # Workspace exclusion rules (protects private data and venvs)
├── Dockerfile                   # Multi-stage unified container definition (Hugging Face Spaces)
├── pytest.ini                   # Pytest configuration
├── run.py                       # Hardened cross-platform local development launcher
└── run_medai.bat                # Windows helper launcher
```

---

## API Endpoints Reference

All application endpoints are versioned under `/api/v1` (with `/api/v1/health` providing readiness monitoring):

| Method | Endpoint | Auth Required | Description |
|---|---|:---:|---|
| `GET` | `/api/v1/health` | No | System health and database connectivity check |
| `POST` | `/api/v1/auth/register` | No | Register new user account (Argon2id password hashing, rate-limited) |
| `POST` | `/api/v1/auth/login` | No | Authenticate user and issue opaque 256-bit Bearer token (rate-limited) |
| `POST` | `/api/v1/auth/logout` | **Yes** | Revoke active session token hash immediately from database |
| `GET` | `/api/v1/auth/me` | **Yes** | Return authenticated user identity and session validity |
| `POST` | `/api/v1/chat` | **Yes** | Dispatch intake message through LangGraph clinical workflow |
| `POST` | `/api/v1/new-chat` | **Yes** | Initialize server-generated authorized consultation ID |
| `POST` | `/api/v1/clear` | **Yes** | Clear message history for specified active consultation |
| `GET` | `/api/v1/sessions` | **Yes** | List consultations owned by the authenticated user |
| `GET` | `/api/v1/history` | **Yes** | Retrieve message history for active consultation |
| `GET` | `/api/v1/session/{session_id}` | **Yes** | Retrieve details and message history for specific consultation |
| `DELETE` | `/api/v1/session/{session_id}` | **Yes** | Delete specific consultation and all associated messages |
| `DELETE` | `/api/v1/sessions` | **Yes** | Delete all consultations owned by the authenticated user |
| `POST` | `/api/v1/analyze-image` | **Yes** | Analyze image (MobileNetV3 everyday classifier or gated specialist) |
| `GET` | `/api/v1/diagnostics` | No | Sanitized runtime diagnostic capabilities (no filesystem/stack leak) |
| `POST` | `/api/v1/voice/stt` | **Yes** | Transcribe user voice audio via Groq Whisper (magic bytes validated) |
| `POST` | `/api/v1/voice/tts` | **Yes** | Synthesize educational response audio via Edge-TTS streaming |

---

## Environment Variables Configuration

Copy `.env.example` to `.env` to configure your environment:

| Variable | Required | Default | Purpose & Constraints |
|---|---|---|---|
| `SESSION_SECRET_KEY` | **Yes** | — | Cryptographic key for session cookie signing (minimum 32 chars in production). |
| `GROQ_API_KEY` | **Yes** | — | Groq API key for conversational intake LLM (default: `openai/gpt-oss-120b`) and Whisper STT. |
| `TAVILY_API_KEY` | Optional | — | Tavily API key for medical web search fallback. |
| `ENVIRONMENT` | Optional | `development` | Runtime environment (`development`, `staging`, `production`). |
| `ALLOWED_ORIGINS` | Optional | `http://localhost:5173,...` | Comma-separated list of allowed CORS origins. |
| `TRUSTED_PROXIES` | Optional | `127.0.0.1,::1` | Reverse proxy IPs/CIDRs for safe client IP resolution. |
| `CONSULTATION_TIMEOUT_SECONDS` | Optional | `90.0` | Maximum wall-clock timeout for LangGraph workflow execution. |
| `MAX_IMAGE_UPLOAD_BYTES` | Optional | `5242880` (5MB) | Maximum allowed image upload size. |
| `MAX_IMAGE_PIXELS` | Optional | `16000000` (16MP)| Pillow decompression bomb safety threshold. |
| `MAX_CONCURRENT_INFERENCE` | Optional | `2` | Process-local vision model concurrency semaphore. |
| `INFERENCE_QUEUE_TIMEOUT_SECONDS`| Optional | `5.0` | Wait queue timeout before returning HTTP 503 `model_unavailable`. |
| `MAX_AUDIO_UPLOAD_BYTES` | Optional | `10485760` (10MB)| Maximum allowed audio upload size (min: 500 bytes). |
| `MAX_CONCURRENT_STT` | Optional | `3` | Process-local STT concurrency semaphore. |
| `MAX_CONCURRENT_TTS` | Optional | `5` | Process-local TTS concurrency semaphore. |
| `VOICE_QUEUE_TIMEOUT_SECONDS` | Optional | `5.0` | Voice wait queue timeout before returning HTTP 503. |
| `MAX_TTS_INPUT_CHARS` | Optional | `2000` | Maximum characters permitted for speech synthesis. |
| `CHAT_DB_PATH` | Optional | `backend/storage/chat_db/susham_health.db` | SQLite database file location. |
| `ENABLE_CLINICAL_SPECIALIST_MODELS` | Optional | `false` | Gate for unvalidated specialist models (false by default). |
| `ALLOW_MODEL_DOWNLOADS` | Optional | `false` | Blocks implicit multi-GB downloads from remote hubs. |
| `OFFLINE_MODE` | Optional | `false` | When true, blocks external LLM network requests. |

---

## Local Development & Setup

### Prerequisites
* **Python**: 3.12 or 3.13
* **Node.js**: 20 LTS or higher
* **npm**: 10 or higher

### Option 1: Integrated Launcher (Recommended)
The project includes a hardened development launcher that initializes dependencies, starts both services, verifies backend readiness, and ensures clean child process cleanup:

```bash
# Clone the repository
git clone https://github.com/sg721642/NewGenHealthAI.git
cd NewGenHealthAI

# Configure environment credentials
cp .env.example .env
# Edit .env with your GROQ_API_KEY and a 32+ char SESSION_SECRET_KEY

# Run launcher (starts FastAPI on port 8000 and Vite on port 5173)
python run.py
```

### Option 2: Running Services Manually

**1. Backend:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**2. Frontend:**
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Containerization & Hugging Face Deployment

### 1. Unified Multi-Stage Container (Hugging Face Spaces)
The root `Dockerfile` packages the entire application into a minimal, secure container:
* **Stage 1 (Frontend Build):** Uses `node:20-slim` to execute `npm ci` and compile the React application via `npm run build:standalone`.
* **Stage 2 (Runtime):** Uses `python:3.12-slim`, installs system runtime libraries (`ffmpeg`, `libgl1`, `libglib2.0-0`), sets up a non-root user `user` (UID 1000), copies static assets to `backend/app/static`, and runs Uvicorn on port `7860`.

```bash
# Build the unified container
docker build -t newgenhealthai:latest .

# Run container locally
docker run -p 7860:7860 \
  -e SESSION_SECRET_KEY="replace-with-at-least-32-chars-secret" \
  -e GROQ_API_KEY="your-groq-api-key" \
  newgenhealthai:latest
```

### 2. Hugging Face Spaces Deployment & Storage Reality
When deploying to Hugging Face Spaces (Docker SDK, port 7860):
> [!IMPORTANT]
> **Ephemeral Container Storage Reality**
> On Hugging Face Spaces standard CPU-Basic containers, the local container filesystem is **ephemeral**.
> The SQLite database (`susham_health.db`) is stored inside the container filesystem at `backend/storage/chat_db/`. Consequently, **database state resets whenever the Space restarts, rebuilds, or sleeps**.
> For persistent user account and conversation retention in production deployments, mount a persistent storage volume or attach an external database service.

---

## Verified Testing & Quality Assurance Baseline

Every change in NewGenHealthAI is verified against a rigorous, reproducible automated test suite:

| Test Suite | Scope | Automated Count | Status | Execution Command |
|---|---|:---:|:---:|---|
| **Backend Pytest** | Security, auth, ownership isolation, concurrency locks, LangGraph workflow, emergency red-flag screening, vision, voice bounds, persistence | **480 passed** (0 failed, 1 warning) | ✅ Green | `pytest backend/tests/ -v` |
| **Frontend Vitest** | UI component rendering, state coordinator, drawer, accessibility, theme toggle, modals, choice chips | **36 passed** (0 failed) | ✅ Green | `npm --prefix frontend test -- --run` |
| **Frontend ESLint** | Static code analysis and React Hook dependency rules | **0 errors, 0 warnings** | ✅ Clean | `npm --prefix frontend run lint` |
| **Standalone Build** | Vite production asset compilation to `frontend/dist/` | **Success** (~590ms) | ✅ Green | `npm --prefix frontend run build:standalone` |
| **GitHub Actions CI** | Multi-job workflow (`.github/workflows/docker-ci.yml`) testing Pytest, Vitest, and full Docker container smoke test | **3/3 jobs green** | ✅ Green | Verified on Run [#42657594147](https://github.com/sg721642/NewGenHealthAI/actions/runs/42657594147) |

### Reproducible CI via Git-Tracked Synthetic Fixtures
To guarantee that CI runs identically on fresh GitHub Actions runners without downloading unapproved clinical imagery or relying on locally ignored files:
* CI tests utilize Git-tracked synthetic image fixtures (`backend/tests/fixtures/synthetic_images/medical_skin_lesion.jpg`, `portrait_human.jpg`).
* Synthetic images are used strictly for input format validation, upload size enforcement, and safety gate testing.
* Synthetic images are **never** treated as clinically representative data or used to claim clinical diagnostic accuracy.

---

## Known Limitations & Future Improvements

As an academic prototype, NewGenHealthAI has several deliberate engineering trade-offs:

1. **Non-Diagnostic Academic Status:** The platform is an educational prototype and has not undergone formal clinical trials or regulatory review (FDA, CE, CDSCO). It must not be deployed as an autonomous diagnostic agent.
2. **Gated Specialist Classifiers:** Deep learning specialist diagnostic models remain disabled in production (`ENABLE_CLINICAL_SPECIALIST_MODELS=false`). Future work involves validating models against curated, ethically cleared clinical datasets under clinical protocol supervision.
3. **Ephemeral SQLite Storage:** Standard container deployments reset SQLite state on restart. Attaching managed PostgreSQL or external persistent volumes is planned for persistent multi-tenant deployments.
4. **Process-Local Concurrency Managers:** Concurrency semaphores and rate limiters (`BoundedRateLimiter`, `VoiceCapacityManager`) are held in memory per worker process. Horizontal scaling across distributed instances requires Redis-backed distributed semaphores.
5. **Synchronous Worker Sockets:** Python's `asyncio.to_thread` guarantees that the event loop times out gracefully (504 Gateway Timeout), but underlying C network sockets in external libraries cannot be forcibly killed by the Python runtime.

---

## Project Maintainer

* **Satyam Gupta** — *Project Lead, System Architect & Maintainer*

---

## License

No LICENSE file or open-source license has been specified for this repository. Permissions for reuse, modification, and redistribution have therefore not been explicitly granted through an open-source license.

---

## Acknowledgments

We gratefully acknowledge the open-source software libraries and foundational models that made this academic project possible:
* **FastAPI** & **Starlette** for high-performance backend infrastructure.
* **React 19**, **Vite**, **Tailwind CSS**, and **DaisyUI** for modern clinical web interfaces.
* **LangChain** & **LangGraph** for bounded, acyclic multi-agent orchestration.
* **Groq** for high-speed LLM inference and Whisper speech recognition.
* **Microsoft Edge TTS** for accessible speech synthesis.
* **PyTorch** & **Torchvision** for neural vision model execution.
