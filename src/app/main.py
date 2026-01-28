# src/app/main.py
"""
SignalFlow - Memory & Signal Intelligence Platform

FastAPI application entry point. This file should remain minimal,
delegating to specialized modules for:
- Router registration (routers.py)
- Startup logic (services/startup.py)
- Authentication (auth.py)

Best Practice: Keep main.py under 100 lines for maintainability.
"""

import os
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from .auth import AuthMiddleware
from .routers import register_routers
from .services.startup import initialize_app
from .api.versioning import APIVersionMiddleware, version_router, API_VERSION

# Initialize logger
logger = logging.getLogger(__name__)

# =============================================================================
# API CONFIGURATION
# =============================================================================

# Use version from centralized versioning module
# API_VERSION imported from .api.versioning
API_DESCRIPTION = """
# SignalFlow API

A knowledge work management system built around signal extraction from meetings,
hierarchical knowledge organization, and AI-assisted workflow management.

## API Versions

- **v1** (`/api/v1/*`): RESTful API with proper pagination and Pydantic models
- **mobile** (`/api/mobile/*`): Offline-first sync endpoints for mobile apps
- **domains** (`/api/domains/*`): New domain-driven architecture (recommended)

## Core Features

- 🎯 **Signal Extraction**: Extract decisions, action items, blockers from meetings
- 📚 **Knowledge Organization**: DIKW pyramid with hierarchical synthesis
- 🏃 **Sprint Management**: Tickets, sprints, AI-powered standup analysis
- 📱 **Multi-Device Sync**: Bidirectional sync with conflict resolution
"""

# =============================================================================
# APPLICATION SETUP
# =============================================================================

app = FastAPI(
    title="SignalFlow - Memory & Signal Intelligence",
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "v1", "description": "API v1 endpoints with proper REST semantics"},
        {"name": "domains", "description": "Domain-driven API (new architecture)"},
        {"name": "meetings", "description": "Meeting CRUD operations"},
        {"name": "documents", "description": "Document CRUD operations"},
        {"name": "signals", "description": "Signal extraction and management"},
        {"name": "tickets", "description": "Ticket and sprint management"},
        {"name": "mobile", "description": "Mobile app sync endpoints"},
    ]
)


# =============================================================================
# MIDDLEWARE & STATIC FILES
# =============================================================================

app.add_middleware(APIVersionMiddleware)
app.add_middleware(AuthMiddleware)

STATIC_DIR = "src/app/static"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates with environment variables exposed
templates = Jinja2Templates(directory="src/app/templates")
templates.env.globals['env'] = os.environ


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint for Railway and other platforms."""
    return {"status": "healthy", "version": API_VERSION}


# =============================================================================
# STARTUP & ROUTERS
# =============================================================================

@app.on_event("startup")
def startup():
    """Initialize the application on startup."""
    initialize_app()


# Register all routers (domain + legacy)
register_routers(app)
