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

### An Educational and Research Healthcare AI Assistant Platform

<br/>

🚀 **Live Demo on Hugging Face Spaces**

[https://huggingface.co/spaces/sg721642/NewGenHealthAI](https://huggingface.co/spaces/sg721642/NewGenHealthAI)

[![Hugging Face Spaces](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Spaces-blue)](https://huggingface.co/spaces/sg721642/NewGenHealthAI)

<br/>

</div>

---

NewGenHealthAI is a full-stack educational and research healthcare AI assistant built with a FastAPI backend and a React + Vite frontend. It provides conversational health intake, image-based prototype observations, voice input/output, and robust session security.

> [!WARNING]
> **Clinical Safety & Research Prototype Disclaimer**
> NewGenHealthAI is strictly designed for **educational, prototype, and research purposes only**. It does **NOT** provide medical diagnosis, treatment, physician consultations, or clinical decision-making. Model findings and chat outputs are uncalibrated experimental outputs and must never replace qualified clinical judgment by a licensed medical professional. In an emergency, immediately contact your local emergency services (e.g. 911 in US/CA, 999 in UK, 112 in India/EU) or a crisis hotline.

---

## Architecture Overview

```
                                      ┌─────────────────────────────────┐
                                      │   React 19 + Vite + DaisyUI     │
                                      │   Single Page Application (SPA) │
                                      └────────────────┬────────────────┘
                                                       │
                                  Bearer Token Auth / TLS (HTTP & Streaming)
                                                       │
                                                       ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Backend Application                                                                   │
├──────────────────────────────┬───────────────────────────────┬────────────────────────────────┤
│ Security & Isolation Layer   │ Clinical Workflow (LangGraph) │ Multimodal AI Engines          │
│ • Centralized Auth (Bearer)  │ • Bounded Acyclic DAG Routing │ • Hard Modality Vision Lock   │
│ • Argon2id Password Hashing  │ • Pure Offline Emergency Gate │   (Skin, X-ray, Retina, Gen)   │
│ • SHA-256 Token Storage      │ • Single-visit node budget    │ • Normal/Anatomy Preservation  │
│ • Bounded Rate Limiting      │ • 90s Consultation Deadline   │ • Decompression Bomb Limits    │
│ • Trusted Reverse Proxies    │ • No Physician Impersonation  │ • EXIF Metadata Stripping      │
│ • Conversation Lock Manager  │ • No Forced Diagnosis/Dosages │ • Lazy On-Demand Checkpoints   │
│ • Generational Race Guards   │ • Citations with Provenance   │ • Inference Capacity Semaphore │
├──────────────────────────────┴───────────────────────────────┴────────────────────────────────┤
│ Voice Processing Pipeline                                                                     │
│ • Chunked Upload (500B..10MB) & Container Magic Byte Validation (WAV, WebM, OGG, MP3, M4A)    │
│ • Private Temporary Files (0o700/0o600) with Deterministic Cleanup in finally:                │
│ • Non-Blocking AsyncGroq (timeout=15s) with Overall Deadline (30s) & Whisper Fallback         │
│ • Process-Local Voice Capacity Manager (STT=3, TTS=5, wait timeout=5.0s, per-user limit=1)   │
│ • Hardened Edge TTS Streaming (2..2000 chars, markdown stripping, neural voice allowlists)    │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ Persistence Layer                                                                             │
│ • SQLite in WAL Mode with Online Backup API and PRAGMA integrity_check                        │
│ • Step-wise Atomic Schema Migrations (v1: conversations & quarantine; v2: SHA-256 sessions)   │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```text
NewGenHealthAI/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Endpoints (auth, chat, image, voice, sessions, health)
│   │   ├── core/            # Configuration, dependencies, security, urgent care
│   │   ├── db/              # SQLite migrations, backup API, schemas
│   │   ├── models/          # SQLAlchemy ORM models (User, Session, Conversation)
│   │   ├── services/        # Chat service, clinical engine, disease classifiers
│   │   └── tools/           # Audio & image preprocessing, capacity managers
│   ├── tests/               # 285+ pytest unit, security, concurrency, and API tests
│   ├── Dockerfile           # Standalone backend container definition
│   ├── pyproject.toml       # Backend packaging and dependency definitions
│   └── requirements.txt     # Python production and test dependencies
├── frontend/
│   ├── src/                 # React 19 application components and integration tests
│   ├── public/              # Static assets (favicon.svg)
│   ├── Dockerfile           # Standalone frontend container definition (Nginx SPA)
│   ├── nginx.conf           # Standalone Nginx reverse proxy configuration
│   ├── package.json         # Frontend dependencies and build scripts
│   └── vite.config.js       # Vite configuration with integrated and standalone modes
├── docs/                    # Authoritative engineering documentation & test evidence
├── .dockerignore            # Container build exclusion rules
├── .env.example             # Comprehensive environment variable documentation
├── Dockerfile               # Root multi-stage unified Dockerfile (Hugging Face Spaces)
├── run.py                   # Hardened local development launcher
└── run_medai.bat            # Windows launcher helper
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure your credentials. Key parameters include:

| Variable | Required | Default | Description |
|---|---|---|---|
| `SESSION_SECRET_KEY` | **Yes** | — | Cryptographic secret for session cookie signing (min 32 chars) |
| `GROQ_API_KEY` | **Yes** | — | Groq API key for LLaMA-3 clinical LLM and Whisper STT |
| `TAVILY_API_KEY` | Optional | — | Tavily API key for medical web search fallback |
| `CONSULTATION_TIMEOUT_SECONDS` | Optional | `90.0` | Wall-clock consultation timeout in seconds |
| `MAX_IMAGE_UPLOAD_BYTES` | Optional | `5242880` (5MB) | Maximum compressed image upload size |
| `MAX_AUDIO_UPLOAD_BYTES` | Optional | `10485760` (10MB) | Maximum audio upload size |
| `MAX_CONCURRENT_INFERENCE` | Optional | `2` | Process-local specialist vision inference semaphore |
| `MAX_CONCURRENT_STT` | Optional | `3` | Process-local STT transcription semaphore |
| `MAX_CONCURRENT_TTS` | Optional | `5` | Process-local TTS speech synthesis semaphore |
| `ALLOW_MODEL_DOWNLOADS` | Optional | `false` | Blocks implicit multi-GB downloads from remote hubs |

---

## Local Development Quick Start

### Option 1: Root Development Launcher (Recommended)

From the project root:

```bash
# Start backend and frontend with auto-setup
python run.py

# Or explicitly install/update dependencies:
python run.py --install-deps
```

The launcher:
1. Resolves paths relative to `__file__` without relying on working directory state.
2. Checks environment without `shell=True` or version spoofing hacks.
3. Starts the backend on `http://127.0.0.1:8000` with hot-reloading.
4. Waits for the `/api/v1/health` endpoint to report healthy.
5. Launches the Vite development server on `http://localhost:5173`.
6. Traps `SIGINT` (Ctrl+C) and cleanly terminates all child processes without leaving orphaned background workers.

### Option 2: Running Services Separately

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## Building & Containerization

### 1. Integrated Build (Default)
Outputs static assets into `backend/app/static/` so FastAPI serves the SPA directly:
```bash
cd frontend
npm run build
```

### 2. Standalone Frontend Build
Outputs static assets into `frontend/dist/` for standalone Nginx hosting:
```bash
cd frontend
npm run build:standalone
```

### 3. Docker Deployment Options

* **Unified Image (Hugging Face Spaces):**
  Uses root `Dockerfile` (multi-stage: Node build → Python runtime, port 7860, non-root user UID 1000):
  ```bash
  docker build -t newgenhealthai:latest .
  docker run -p 7860:7860 -e SESSION_SECRET_KEY="your-32-char-secret" -e GROQ_API_KEY="your-key" newgenhealthai:latest
  ```

* **Standalone Frontend Container:**
  Uses `frontend/Dockerfile` with Nginx reverse proxy on port 80:
  ```bash
  cd frontend
  docker build -t newgenhealthai-frontend:latest .
  docker run -p 80:80 newgenhealthai-frontend:latest
  ```

* **Standalone Backend Container:**
  Uses `backend/Dockerfile` running Uvicorn on port 8000:
  ```bash
  cd backend
  docker build -t newgenhealthai-backend:latest .
  docker run -p 8000:8000 newgenhealthai-backend:latest
  ```

---

## Testing & Quality Assurance

### Full Backend Test Suite (Pytest)
```bash
pytest backend/tests/ -v
```
Runs 285+ automated tests across 20 modules verifying:
* Centralized authentication & ownership isolation (`test_security_ownership.py`, `test_auth_hardening.py`)
* Concurrency, locking & clinical memory rehydration (`test_phase1d_concurrency.py`)
* Image validation, modality lock & safe inference (`test_phase2a_image_classifier.py`, `test_phase3a_image_security.py`)
* Bounded clinical workflow, urgent care gate & response safety (`test_phase2b_workflow_safety.py`, `test_phase2b1_corrections.py`)
* Voice upload bounds, temporary file isolation, AsyncGroq, capacity manager & TTS streaming (`test_phase3b_voice_security.py`)

### Frontend Test Suite (Vitest)
```bash
npm --prefix frontend test -- --run
```

### Frontend Linter
```bash
npm --prefix frontend run lint
```

---

## Contributors

* **Satyam Gupta** (First-Party Maintainer)
* **Khagesh Ranjan**
* **Sudipto Ghosh**
* **Ajitesh Baghel**
* **Yuvraj Singh**

---

## License & Intellectual Property

This project is a university/research healthcare prototype. All rights reserved by the original project contributors. Formal open-source licensing terms are pending decision by first-party maintainer Satyam Gupta.

---

## Acknowledgments

Special thanks to the open-source communities behind FastAPI, React, Vite, Hugging Face, LangChain, Groq, and PyTorch.
