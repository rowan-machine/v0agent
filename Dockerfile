# Dockerfile - Multi-stage build for V0Agent
# 
# Stages:
#   1. builder - Install dependencies
#   2. runtime - Production image
#   3. development - Development image with dev tools

# ===== Stage 1: Builder =====
FROM python:3.11-slim as builder

WORKDIR /tmp
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ===== Stage 2: Runtime =====
FROM python:3.11-slim as runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/home/appuser/.local/bin:$PATH

# Create non-root user for security FIRST
RUN useradd -m -u 1000 appuser

# Copy Python packages to appuser's directory
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser .env.example ./.env

# Create data directories
RUN mkdir -p /app/data /app/uploads /app/logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Expose port
EXPOSE 8000

# Start application
CMD ["python", "-m", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ===== Stage 3: Development =====
FROM python:3.11-slim as development

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH

# Install both requirements and dev requirements
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -r requirements-dev.txt && \
    pip install --no-cache-dir \
    black \
    pylint \
    isort \
    pytest-watch \
    ipython \
    debugpy

# Copy code and tests
COPY src/ ./src/
COPY config/ ./config/
COPY tests/ ./tests/
COPY .env.example ./.env

# Create directories
RUN mkdir -p /app/data /app/uploads /app/logs

EXPOSE 8000

# Run with hot reload
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
