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

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
