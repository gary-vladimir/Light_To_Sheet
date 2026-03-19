FROM python:3.11-slim

# System dependencies: FFmpeg for video processing, OpenCV runtime libs, Deno for yt-dlp
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (required by yt-dlp for YouTube's JS challenges)
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh

WORKDIR /app

# Ensure Python output is sent straight to logs (no buffering)
ENV PYTHONUNBUFFERED=1

# Install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY src/ src/
COPY templates/ templates/
COPY static/ static/

EXPOSE 8080

# Gunicorn configuration:
# - workers=1: single instance handles one video at a time
# - threads=2: serve downloads/previews while processing
# - timeout=900: 15 minutes for long video processing
# - exec: run as PID 1 for proper signal handling on Cloud Run
CMD exec gunicorn \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 1 \
    --threads 2 \
    --timeout 900 \
    app:app
