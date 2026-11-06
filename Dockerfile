# --- STAGE 1: Build Frontend ---
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build:standalone

# --- STAGE 2: Build Backend & Final Image ---
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Create non-root user (UID 1000 is standard for Hugging Face Spaces)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Copy backend code
COPY backend/ /app/backend/

# Copy built frontend from Stage 1 to the backend's static directory
COPY --from=frontend-builder /app/frontend/dist /app/backend/app/static

# Set environment variables
ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/tmp/huggingface
ENV ALLOW_MODEL_DOWNLOADS=false

# Create necessary directories and set ownership for non-root user
RUN mkdir -p /app/backend/storage/chat_db /app/backend/storage/vector_store /app/backend/logs /tmp/huggingface \
    && chown -R user:user /app /tmp/huggingface

USER user

# Health check using standard backend health route
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-7860}/api/v1/health || exit 1

# Expose the port (Hugging Face Spaces uses 7860)
EXPOSE 7860

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
