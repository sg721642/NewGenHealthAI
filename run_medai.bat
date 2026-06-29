@echo off
setlocal

:: Check if internal venv exists, but we prefer conda if medai is active
:: The user specifically asked for Anaconda/medai

echo --- MEDICAL AI STARTUP (CONDA: medai) ---
echo Working Directory: %cd%

:: Set environment variables
set PYTHONPATH=%cd%\backend
set HF_HOME=%cd%\model_cache
if not exist "model_cache" mkdir "model_cache"

:: Check for model files
if not exist "backend\app\models" (
    echo [ERROR] Models directory not found at backend\app\models
    pause
    exit /b
)

echo Starting Backend (FastAPI)...
start "NewGenHealthAI Healthcare AI" cmd /k "conda activate medai && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo Waiting for backend to initialize...
timeout /t 5 /nobreak > nul

echo Starting Frontend (Vite/React)...
cd frontend
npm run dev

pause
