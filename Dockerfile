# --- STAGE 1: Build Frontend ---
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- STAGE 2: Build Backend & Final Image ---
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Copy built frontend from Stage 1 to the backend's static directory
COPY --from=frontend-builder /app/backend/app/static /app/backend/app/static

# Set environment variables
ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/tmp/huggingface

# Create necessary directories
RUN mkdir -p /app/backend/storage/chat_db /app/backend/storage/vector_store /app/backend/logs /tmp/huggingface

# Expose the port (Hugging Face Spaces often uses 7860)
EXPOSE 7860

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
