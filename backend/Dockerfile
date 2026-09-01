FROM python:3.11-slim

# Install system runtime dependencies: FFmpeg runtime, OpenCV dependencies (libgl1, libglx-mesa0), curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Pre-install PyTorch CPU & pre-built binary wheel for av in isolated layer for Docker build caching
RUN pip install --no-cache-dir --default-timeout=100 torch torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir "av>=13.0.0"

# Copy requirements.txt and install remaining dependencies using CPU index URL to prevent pulling CUDA wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads /data/processed /data/frames /data/transcripts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]