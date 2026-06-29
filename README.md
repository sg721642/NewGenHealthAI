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

### An AI-powered Medical Consultation & Diagnostic Platform

<br/>

**Live Demo: Coming Soon**

<br/>

</div>

---

An AI-powered medical assistant with a FastAPI backend and a React frontend for conversational clinical guidance, session-based chat, and image-based disease analysis.

## Overview

NewGenHealthAI is a full-stack healthcare AI application designed to support medical interaction workflows through:

* conversational AI assistance
* image-based disease analysis
* session-based chat history
* diagnostics and model inspection utilities
* containerized deployment with Docker

The project is organized as a monorepo with separate backend and frontend applications.

## Repository Structure

```text
NewGenHealthAI/
├── backend/
│   ├── app/
│   ├── test_images/
│   ├── tests/
│   ├── .flake8
│   ├── Dockerfile
│   ├── inspect_models.py
│   ├── pyproject.toml
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── test_api.py
│   └── test_clip_routing.py
├── frontend/
│   ├── public/
│   ├── src/
│   ├── .gitignore
│   ├── Dockerfile
│   ├── README.md
│   ├── eslint.config.js
│   ├── index.html
│   ├── nginx.conf
│   ├── package-lock.json
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
├── .env.example
├── Dockerfile
├── check_model_on_image.py
├── diagnose_env.py
├── run.py
├── run_medai.bat
└── .gitignore
```

## Features

* AI-powered medical assistant interface
* FastAPI backend API
* React + Vite frontend
* Session-based conversation history
* Medical image analysis endpoint
* Model diagnostics endpoint
* Local testing utilities for medical images
* Docker support for deployment
* Environment-based configuration

## Tech Stack

### Backend

* Python
* FastAPI
* Uvicorn
* LangChain / LangGraph
* ChromaDB
* Sentence Transformers
* Hugging Face Transformers
* PyTorch
* SQLAlchemy

### Frontend

* React
* Vite
* Tailwind CSS
* DaisyUI

## Environment Variables

Create a `.env` file in the project root based on `.env.example`.

Required variables include:

```env
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
SESSION_SECRET_KEY=your_session_secret_key_here
```

Optional path overrides may also be configured for logs, database, vector store, and PDF sources.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/sg721642/NewGenHealthAI.git
cd NewGenHealthAI
```

### 2. Backend setup

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

**Windows**

```bash
.venv\Scripts\activate
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Frontend setup

Open a new terminal:

```bash
cd frontend
npm install
```

## Running the Project

### Option 1: Start with the root launcher

From the project root folder:

```bash
python run.py
```

This script:

* creates a virtual environment if needed
* installs backend dependencies
* installs frontend dependencies
* starts the backend on port `8000`
* waits for the backend health endpoint
* launches the frontend development server

### Option 2: Run backend and frontend separately

#### Start backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

#### Start frontend

```bash
cd frontend
npm run dev
```

## API Endpoints

Some important backend routes include:

* `GET /api/v1/health` — backend health check
* `GET /api/v1/diagnostics` — loaded model diagnostics
* `POST /api/v1/analyze-image` — upload an image for analysis

Depending on your backend router definitions, additional chat and session endpoints are also available.

## Testing

### Backend tests

Run pytest inside the backend folder:

```bash
cd backend
pytest
```

### Image API test script

```bash
cd backend
python test_api.py
```

### CLIP routing verification

```bash
cd backend
python test_clip_routing.py
```

These scripts test image classification and verify that domain routing works correctly for sample images such as skin, xray, and retina inputs.

## Docker

Dockerfiles are included for:

* project root
* backend
* frontend

You can use them to build and containerize the entire application or individual services depending on your deployment setup.

## Frontend

The frontend is built with React and Vite and provides:

* chat-based interaction
* conversation history
* a clean medical assistant interface

To create a production build:

```bash
cd frontend
npm run build
```

To preview the production build locally:

```bash
npm run preview
```

## Utilities

The project also includes utility scripts such as:

* `check_model_on_image.py` — test model behavior on a single image
* `diagnose_env.py` — inspect environment setup and issues
* `inspect_models.py` — inspect backend model loading/configuration
* `run_medai.bat` — Windows launcher helper

## Use Cases

* AI-assisted symptom guidance
* educational medical assistant demos
* image-based disease analysis workflows
* research prototypes for healthcare AI systems

## Disclaimer

This project is intended for educational, research, and prototype purposes only.

It must not be used as a replacement for licensed medical diagnosis, treatment, or professional clinical judgment.

## Contributors

* Satyam Gupta
* Khagesh Ranjan
* Sudipto Ghosh
* Ajitesh Baghel
* Yuvraj Singh

## License

Add your preferred license here, for example:

```text
MIT License
```

If you have not chosen one yet, create a `LICENSE` file before publishing for open-source reuse.

## Acknowledgments

Special thanks to the mentor, contributors, and open-source communities behind FastAPI, React, Vite, Hugging Face, LangChain, and related AI tooling.
