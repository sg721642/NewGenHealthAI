@echo off
setlocal

:: Check if internal venv exists, but we prefer conda if medai is active
:: The user specifically asked for Anaconda/medai

echo --- NewGenHealthAI Healthcare AI Launcher ---
echo Working Directory: %cd%

:: Set environment variables
set PYTHONPATH=%cd%\backend
set HF_HOME=%cd%\model_cache
set ALLOW_MODEL_DOWNLOADS=false
if not exist "model_cache" mkdir "model_cache"

echo Starting Backend (FastAPI)...
start "NewGenHealthAI Backend" cmd /k "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Waiting for backend to initialize...
timeout /t 5 /nobreak > nul

echo Starting Frontend (Vite/React)...
cd frontend
npm run dev

pause
