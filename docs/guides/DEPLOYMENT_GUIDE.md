# Containerization & Deployment Guide

**Status:** Architecture & Planning Document  
**Purpose:** Prepare for easy deployment via Docker/Kubernetes  

---

## 1. Docker Architecture

### 1.1 Container Strategy

```
┌─────────────────────────────────────────────┐
│  FastAPI Application Container              │
│  - Python 3.11 runtime                      │
│  - All dependencies (poetry/pip)            │
│  - Agent system & services                  │
│  - SQLite database (volume mount)           │
│  - Port 8000 exposed                        │
└─────────────────────────────────────────────┘
         ↓                              ↓
┌──────────────────────┐    ┌──────────────────────┐
│  Data Persistence    │    │  Optional Services   │
│  (Docker Volume)     │    │  (docker-compose)    │
│  - agent.db          │    │  - ChromaDB          │
│  - embeddings        │    │  - Neo4j             │
│  - uploads/          │    │  - Redis (cache)     │
└──────────────────────┘    └──────────────────────┘
```

### 1.2 Images

```dockerfile
# Production: Multi-stage build (slim image)
- Build stage (install deps)
- Runtime stage (minimal runtime)

# Development: Full image with dev tools
- pytest, black, pylint, ipython

# Testing: Test-specific image
- Same as production + test dependencies
```

---

## 2. Dockerfile

```dockerfile
# Dockerfile (NEW)

# ===== Build Stage =====
FROM python:3.11-slim as builder

WORKDIR /tmp
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (for better caching)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ===== Runtime Stage =====
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install only runtime dependencies (from builder)
COPY --from=builder /root/.local /root/.local

# Add pip packages to PATH
ENV PATH=/root/.local/bin:$PATH

# Create app user (security best practice)
RUN useradd -m -u 1000 appuser

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser .env.example ./.env

# Create directories for data persistence
RUN mkdir -p /app/data /app/uploads && \
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

# ===== Development Stage (optional) =====
FROM python:3.11-slim as development

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install all dependencies including dev
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY src/ ./src/
COPY config/ ./config/
COPY tests/ ./tests/
COPY .env.example ./.env

# Install development tools
RUN pip install \
    black \
    pylint \
    isort \
    pytest-watch \
    ipython

EXPOSE 8000

# Run with hot reload for development
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

---

## 3. Docker Compose

```yaml
# docker-compose.yaml (NEW)

version: '3.8'

services:
  # Main FastAPI application
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data                    # Persistent data
      - ./uploads:/app/uploads              # User uploads
      - ./logs:/app/logs                    # Application logs
      - ./.env:/app/.env:ro                 # Environment file (read-only)
    environment:
      - DATABASE_PATH=/app/data/agent.db
      - UPLOAD_DIR=/app/uploads
      - LOG_DIR=/app/logs
      - LOG_LEVEL=INFO
    depends_on:
      chroma:
        condition: service_healthy
    networks:
      - v0agent_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
  
  # ChromaDB for embeddings
  chroma:
    image: ghcr.io/chroma-core/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/data
    environment:
      - IS_PERSISTENT=TRUE
    networks:
      - v0agent_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 5s
      retries: 3
  
  # Neo4j Knowledge Graph (optional)
  neo4j:
    image: neo4j:latest
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    environment:
      - NEO4J_AUTH=neo4j/password123
      - NEO4J_dbms_memory_heap_initial__size=1G
      - NEO4J_dbms_memory_heap_max__size=2G
    networks:
      - v0agent_network
    restart: unless-stopped
    profiles:
      - with-knowledge-graph  # Only run with: docker-compose --profile with-knowledge-graph
  
  # Redis for caching (optional)
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - v0agent_network
    restart: unless-stopped
    profiles:
      - with-cache
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 5s
      retries: 3
  
  # pgAdmin for database management (dev only)
  pgadmin:
    image: dpage/pgadmin4:latest
    ports:
      - "5050:80"
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@example.com
      - PGADMIN_DEFAULT_PASSWORD=admin
    networks:
      - v0agent_network
    profiles:
      - dev-tools

# Volumes for data persistence
volumes:
  chroma_data:
  neo4j_data:
  neo4j_logs:
  redis_data:

# Networks
networks:
  v0agent_network:
    driver: bridge
```

---

## 4. Environment Configuration

```bash
# .dockerignore (NEW)

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
htmlcov/

# Virtual environments
venv/
env/
ENV/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Git
.git/
.gitignore

# OS
.DS_Store
Thumbs.db

# Project specific
.env
.env.local
.env.*.local
data/
uploads/
logs/
*.db

# CI/CD
.github/
.gitlab-ci.yml
```

```bash
# .env.docker (NEW)

# Database
DATABASE_PATH=/app/data/agent.db
DATABASE_URL=sqlite:///app/data/agent.db

# Application
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-change-in-production

# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# ChromaDB
CHROMA_HOST=chroma
CHROMA_PORT=8000
CHROMA_ENABLED=true

# Neo4j (optional)
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
NEO4J_ENABLED=false

# Redis (optional)
REDIS_URL=redis://redis:6379
REDIS_ENABLED=false

# Features
ENABLE_MULTI_AGENT=true
ENABLE_EMBEDDINGS=true
ENABLE_NEO4J=false
ENABLE_REDIS=false

# File storage
UPLOAD_DIR=/app/uploads
LOG_DIR=/app/logs
```

---

## 5. Build & Deployment Scripts

### 5.1 Makefile

```makefile
# Makefile (NEW)

.PHONY: help build build-dev run stop clean test logs shell

help:
	@echo "V0Agent Docker Commands"
	@echo ""
	@echo "Build & Run:"
	@echo "  make build          Build production image"
	@echo "  make build-dev      Build development image"
	@echo "  make run            Start all services (production)"
	@echo "  make run-dev        Start with development image"
	@echo "  make stop           Stop all services"
	@echo ""
	@echo "Testing & Maintenance:"
	@echo "  make test           Run tests in container"
	@echo "  make shell          Open shell in running app container"
	@echo "  make logs           Tail application logs"
	@echo "  make clean          Remove containers and volumes"
	@echo ""
	@echo "Advanced:"
	@echo "  make build-no-cache Build without using cache"
	@echo "  make push           Push image to registry"
	@echo "  make pull           Pull image from registry"

# Build targets
build:
	docker build -t v0agent:latest \
		--target runtime \
		.

build-dev:
	docker build -t v0agent:dev \
		--target development \
		.

build-no-cache:
	docker build -t v0agent:latest \
		--target runtime \
		--no-cache \
		.

# Run targets
run:
	docker-compose up -d

run-dev:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up

run-debug:
	docker-compose -f docker-compose.yaml -f docker-compose.debug.yaml up

stop:
	docker-compose down

# Testing
test:
	docker-compose exec app pytest tests/ -v

test-unit:
	docker-compose exec app pytest tests/unit -v

test-integration:
	docker-compose exec app pytest tests/integration -v

test-e2e:
	docker-compose exec app pytest tests/e2e -v

test-coverage:
	docker-compose exec app pytest tests/ --cov=src/app --cov-report=html

# Maintenance
shell:
	docker-compose exec app /bin/bash

logs:
	docker-compose logs -f app

logs-chroma:
	docker-compose logs -f chroma

clean:
	docker-compose down -v
	docker rmi v0agent:latest v0agent:dev
	rm -rf data/ logs/

# Image registry
push:
	docker tag v0agent:latest myregistry.azurecr.io/v0agent:latest
	docker push myregistry.azurecr.io/v0agent:latest

pull:
	docker pull myregistry.azurecr.io/v0agent:latest
	docker tag myregistry.azurecr.io/v0agent:latest v0agent:latest

# Development compose override
.PHONY: compose-dev
compose-dev:
	@echo "services:" > docker-compose.dev.yaml
	@echo "  app:" >> docker-compose.dev.yaml
	@echo "    build:" >> docker-compose.dev.yaml
	@echo "      target: development" >> docker-compose.dev.yaml
	@echo "    command: uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload" >> docker-compose.dev.yaml
	@echo "    volumes:" >> docker-compose.dev.yaml
	@echo "      - ./src:/app/src" >> docker-compose.dev.yaml
	@echo "      - ./tests:/app/tests" >> docker-compose.dev.yaml
```

### 5.2 Deploy Script

```bash
#!/bin/bash
# scripts/deploy.sh (NEW)

set -e

# Configuration
REGISTRY="myregistry.azurecr.io"
IMAGE_NAME="v0agent"
TAG="${1:-latest}"
ENV="${2:-production}"

echo "🚀 Deploying V0Agent"
echo "Registry: $REGISTRY"
echo "Image: $IMAGE_NAME:$TAG"
echo "Environment: $ENV"

# Build image
echo "📦 Building Docker image..."
docker build -t $REGISTRY/$IMAGE_NAME:$TAG \
    --target runtime \
    --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
    --build-arg VCS_REF=$(git rev-parse --short HEAD) \
    .

# Push to registry
echo "📤 Pushing to registry..."
docker push $REGISTRY/$IMAGE_NAME:$TAG

# Deploy based on environment
case $ENV in
    production)
        echo "🔧 Deploying to production..."
        # Kubernetes deployment or similar
        kubectl set image deployment/v0agent \
            app=$REGISTRY/$IMAGE_NAME:$TAG \
            -n production
        kubectl rollout status deployment/v0agent -n production
        ;;
    staging)
        echo "🔧 Deploying to staging..."
        kubectl set image deployment/v0agent \
            app=$REGISTRY/$IMAGE_NAME:$TAG \
            -n staging
        ;;
    *)
        echo "✅ Image built and pushed. Use your deployment tool to deploy."
        ;;
esac

echo "✅ Deployment complete!"
```

---

## 6. Kubernetes Deployment (Optional)

```yaml
# k8s/deployment.yaml (NEW - for Kubernetes)

apiVersion: apps/v1
kind: Deployment
metadata:
  name: v0agent-app
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: v0agent
  template:
    metadata:
      labels:
        app: v0agent
    spec:
      containers:
      - name: app
        image: myregistry.azurecr.io/v0agent:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_PATH
          value: /data/agent.db
        - name: LOG_LEVEL
          value: INFO
        volumeMounts:
        - name: data
          mountPath: /app/data
        - name: uploads
          mountPath: /app/uploads
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: v0agent-data
      - name: uploads
        persistentVolumeClaim:
          claimName: v0agent-uploads

---
apiVersion: v1
kind: Service
metadata:
  name: v0agent-service
spec:
  selector:
    app: v0agent
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: v0agent-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: standard

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: v0agent-uploads
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
  storageClassName: standard
```

---

## 7. Health Checks & Monitoring

### 7.1 Health Endpoints

```python
# src/app/api/health.py (NEW)

from fastapi import APIRouter, HTTPException
from datetime import datetime
import psutil
import logging

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """Basic health check for load balancers."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@router.get("/ready")
async def readiness_check():
    """Readiness check - are we ready to serve?"""
    from ..db import connect
    from ..services.agent_bus import get_agent_bus
    
    checks = {
        "database": False,
        "agent_bus": False,
        "memory": False,
    }
    
    try:
        # Check database
        with connect() as conn:
            conn.execute("SELECT 1")
            checks["database"] = True
    except Exception as e:
        logger.error(f"Database check failed: {e}")
    
    try:
        # Check agent bus
        bus = get_agent_bus()
        checks["agent_bus"] = True
    except Exception as e:
        logger.error(f"Agent bus check failed: {e}")
    
    # Check memory
    memory_percent = psutil.virtual_memory().percent
    checks["memory"] = memory_percent < 90
    
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return {
        "status": "ready",
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }

@router.get("/metrics")
async def metrics():
    """Prometheus-style metrics."""
    import time
    
    return {
        "memory_percent": psutil.virtual_memory().percent,
        "cpu_percent": psutil.cpu_percent(interval=1),
        "disk_percent": psutil.disk_usage("/").percent,
        "uptime_seconds": int(time.time() - psutil.boot_time()),
    }
```

### 7.2 Logging Configuration

```python
# src/app/logging_config.py (NEW)

import logging
import logging.handlers
from pathlib import Path
import os

def setup_logging():
    """Setup application logging with rotation."""
    
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (with rotation)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    return root_logger
```

---

## 8. Deployment Checklist

### Pre-Deployment

- [ ] All tests passing (`pytest tests/`)
- [ ] Code linted and formatted (`black`, `isort`, `pylint`)
- [ ] Security scan passed (`bandit`)
- [ ] Docker image builds successfully
- [ ] Environment variables documented
- [ ] Database migrations tested
- [ ] README.md updated

### Deployment

- [ ] Tag git release
- [ ] Build Docker image with correct tag
- [ ] Push to registry
- [ ] Update deployment manifests (if K8s)
- [ ] Run health checks post-deployment
- [ ] Monitor logs for errors
- [ ] Verify all endpoints responsive

### Post-Deployment

- [ ] Monitor CPU/memory usage
- [ ] Check database growth
- [ ] Review error logs
- [ ] Verify backups running
- [ ] Communicate to team

---

## 9. Quick Start

```bash
# Clone and setup
git clone https://github.com/yourusername/v0agent.git
cd v0agent

# Build and run
make build
make run

# Check status
docker-compose ps
docker-compose logs -f app

# Run tests
make test

# Access application
open http://localhost:8000

# Stop
make stop

# Clean up
make clean
```

---

## Summary

✅ **Multi-stage Docker builds** for lean production images  
✅ **Docker Compose** for local development with all services  
✅ **Kubernetes ready** with deployment manifests  
✅ **Health checks** for load balancers  
✅ **Logging & monitoring** hooks  
✅ **Security** with non-root users  
✅ **Environment isolation** with clear config  
✅ **Easy CI/CD integration** via Makefile and scripts

