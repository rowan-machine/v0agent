from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import json
import logging
import os
import re

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# SQLite imports removed - using Supabase-only mode
from .meetings import router as meetings_router
from .documents import router as documents_router
from .search import router as search_router
from .query import router as query_router
from .signals import router as signals_router
from .tickets import router as tickets_router
from .test_plans import router as test_plans_router
from .chat import models as chat_models  # Chat module functions
from .api.chat import router as chat_router
from .api.mcp import router as mcp_router
from .api.accountability import router as accountability_router
from .api.settings import router as settings_router
from .api.assistant import router as assistant_router
# REMOVED: from .api.career import router as career_router (DEPRECATED - use domains/career/api)
from .api.v1 import router as v1_router  # API v1 (Phase 3.1)
from .api.mobile import router as mobile_router  # Mobile sync (Phase 3.2)
from .api.admin import router as admin_router  # Admin endpoints (Phase 4.1)
from .api.search import router as api_search_router  # Semantic/Hybrid search (Phase 5.2)
from .api.knowledge_graph import router as knowledge_graph_router  # Knowledge graph (Phase 5.10)
from .api.shortcuts import router as shortcuts_router  # Arjuna shortcuts (Technical Debt)
from .api.dikw import router as dikw_router  # DIKW pyramid (Refactor Phase 2)
from .api.mindmap import router as mindmap_router  # Mindmap visualization (Refactor Phase 2)
from .api.notifications import router as notifications_router  # Notifications (Refactor Phase 2)
from .api.workflow import router as workflow_router  # Workflow modes & timer (Refactor Phase 2)
from .api.reports import router as reports_router  # Reports & analytics (Refactor Phase 2)
from .api.evaluations import router as evaluations_router  # LangSmith evaluations (Refactor Phase 2)
from .api.pocket import router as pocket_router  # Pocket integration (Refactor Phase 2)
from .api.auth import router as auth_router  # Authentication (Refactor Phase 2.9)
from .api.pages import router as pages_router  # Page renders (Refactor Phase 2.9)
from .api.ai_endpoints import router as ai_endpoints_router  # AI endpoints (Refactor Phase 2.9)
from .api.dashboard_page import router as dashboard_page_router  # Dashboard page (Refactor Phase 2.9)
from .services.startup import initialize_app  # Startup logic (Refactor Phase 2.9)
# New domain-driven routers (Phase 3 - Domain Decomposition)
from .domains.career.api import router as career_domain_router
from .domains.dikw.api import router as dikw_domain_router
from .domains.meetings.api import router as meetings_domain_router
from .domains.tickets.api import router as tickets_domain_router
from .domains.documents.api import router as documents_domain_router
from .domains.dashboard import router as dashboard_domain_router  # Dashboard (Refactor Phase 2)
from .domains.signals import signals_router as signals_domain_router  # Signals (Refactor Phase 2.8)
from .domains.search.api import router as search_domain_router  # Search domain (Refactor Phase 2.10)
from .domains.knowledge_graph import router as knowledge_graph_domain_router  # Knowledge graph domain (Refactor Phase 2.10)
from .mcp.registry import TOOL_REGISTRY
from .llm import ask as ask_llm
from .auth import AuthMiddleware
from .integrations.pocket import PocketClient, extract_latest_summary, extract_transcript_text, extract_mind_map, extract_action_items, get_all_summary_versions, get_all_mind_map_versions
from .services import meeting_service, document_service, ticket_service
from .infrastructure.supabase_client import get_supabase_client
from typing import Optional

# Initialize logger
logger = logging.getLogger(__name__)

# =============================================================================
# DIKW SYNTHESIZER AGENT NOTE (Checkpoint 2.5)
# =============================================================================
# DIKW endpoints have been moved to api/dikw.py router (Refactor Phase 2).
# The dikw_router is included via include_router() at the bottom of this file.
# Agent adapters are imported lazily in that router for backward compatibility.
# =============================================================================

# OpenAPI/Swagger configuration (Phase 3.3)
API_VERSION = "1.0.0"
API_DESCRIPTION = """
# SignalFlow API

A knowledge work management system built around signal extraction from meetings,
hierarchical knowledge organization, and AI-assisted workflow management.

## API Versions

- **v1** (`/api/v1/*`): RESTful API with proper pagination, HTTP status codes, and Pydantic models
- **mobile** (`/api/mobile/*`): Offline-first sync endpoints for mobile apps
- **legacy** (other routes): Original HTML-returning endpoints for web app

## Core Features

### 🎯 Signal Extraction
Extract decisions, action items, blockers, risks, and ideas from meetings.

### 📚 Knowledge Organization  
DIKW pyramid implementation with hierarchical knowledge synthesis.

### 🏃 Sprint Management
Sprint cycles, ticket management, and AI-powered standup analysis.

### 📱 Multi-Device Sync
Bidirectional sync with conflict resolution for mobile apps.

## Authentication
All endpoints require authentication. Set the `STATIC_TOKEN` environment variable.
"""

app = FastAPI(
    title="SignalFlow - Memory & Signal Intelligence",
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "v1", "description": "API v1 endpoints with proper REST semantics"},
        {"name": "meetings", "description": "Meeting CRUD operations"},
        {"name": "documents", "description": "Document CRUD operations"},
        {"name": "signals", "description": "Signal extraction and management"},
        {"name": "tickets", "description": "Ticket and sprint management"},
        {"name": "mobile", "description": "Mobile app sync endpoints"},
        {"name": "sync", "description": "Device sync operations"},
        {"name": "device", "description": "Device registration and management"},
    ]
)

# Health check endpoint (required for Railway)
@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint for Railway and other platforms."""
    return {"status": "healthy", "version": API_VERSION}

# Add authentication middleware
app.add_middleware(AuthMiddleware)

# Serve static files (CSS, JS)
STATIC_DIR = "src/app/static"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# NOTE: Uploads folder removed - attachments are stored in Supabase Storage
# See services/storage_supabase.py for file storage operations

templates = Jinja2Templates(directory="src/app/templates")

# Expose environment variables to Jinja2 templates
templates.env.globals['env'] = os.environ


# NOTE: Neo4j removed - using Supabase knowledge graph instead (Phase 5.10)


@app.on_event("startup")
def startup():
    """Initialize the application on startup."""
    initialize_app()


# =============================================================================
# DASHBOARD PAGE - MIGRATED TO ROUTER
# =============================================================================
# The dashboard page route (GET /) has been moved to api/dashboard_page.py
# The dashboard_page_router handles the / path.
# =============================================================================


# =============================================================================
# SIGNAL ROUTES - MIGRATED TO DOMAIN
# =============================================================================
# The following signal routes have been moved to domains/signals/api/status.py:
# - POST /api/signals/feedback
# - POST /api/signals/status
# - POST /api/signals/convert-to-ticket
# - GET /api/signals/unprocessed
#
# The signals_domain_router handles these paths.
# =============================================================================


# =============================================================================
# DASHBOARD ROUTES - MIGRATED TO DOMAIN
# =============================================================================
# The following dashboard routes have been moved to domains/dashboard/api/:
# - POST /api/dashboard/quick-ask -> domains/dashboard/api/quick_ask.py
# - GET /api/dashboard/highlights -> domains/dashboard/api/highlights.py  
# - POST /api/dashboard/highlight-context -> domains/dashboard/api/context.py
#
# These legacy routes below are kept for backward compatibility but will be
# removed in a future release. The domain router is included and handles
# the same paths.
# =============================================================================


# DEPRECATED: Use dashboard_domain_router instead
# @app.post("/api/dashboard/quick-ask")
# async def dashboard_quick_ask(request: Request):
#     """MOVED to domains/dashboard/api/quick_ask.py"""
#     pass


# DEPRECATED: Use dashboard_domain_router instead  
# @app.get("/api/dashboard/highlights")
# async def get_highlights(request: Request):
#     """MOVED to domains/dashboard/api/highlights.py"""
#     pass


# =============================================================================
# AI ROUTES - MIGRATED TO ROUTER
# =============================================================================
# The following routes have been moved to api/ai_endpoints.py:
# - POST /api/ai/draft-summary
# - POST /api/ai-memory/save
# - POST /api/ai-memory/reject
# - POST /api/ai-memory/to-action
#
# The ai_endpoints_router handles these paths.
# =============================================================================


# =============================================================================
# USER STATUS & MODE TIMER ROUTES - MIGRATED TO DOMAIN
# =============================================================================
# The following routes have been moved to domains/workflow/api/user_status.py:
# - POST /api/user-status/update
# - GET /api/user-status/current
# - POST /api/mode-timer/calculate-stats
#
# The workflow_router handles these paths.
# =============================================================================


# NOTE: DIKW Pyramid API endpoints moved to api/dikw.py router (Refactor Phase 2)
# The dikw_router is included via include_router() at the bottom of this file.

# NOTE: Mindmap API endpoints moved to api/mindmap.py router (Refactor Phase 2)
# The mindmap_router is included via include_router() at the bottom of this file.
# Removed duplicate routes: /api/mindmap/data, /api/mindmap/data-hierarchical,
# /api/mindmap/nodes-by-level/{level}, /api/mindmap/conversations, /api/mindmap/synthesize,
# /api/mindmap/synthesis, /api/mindmap/synthesize-all, /api/mindmap/generate,
# /api/mindmap/tags, /api/mindmap/status

# NOTE: Additional DIKW endpoints (backfill-tags, compress-dedupe, history, 
# normalize-categories, auto-process) moved to api/dikw.py router (Refactor Phase 2)


@app.post("/meetings/load")
async def load_meeting_bundle_ui(
    request: Request,
    background_tasks: BackgroundTasks,
    meeting_name: str = Form(...),
    meeting_date: str = Form(None),
    summary_text: str = Form(...),
    pocket_recording_id: str = Form(None),
    pocket_ai_summary: str = Form(None),
    pocket_mind_map: str = Form(None),
    mindmap_level: int = Form(0),
    pocket_action_items: str = Form(None),
    pocket_transcript: str = Form(None),
    teams_transcript: str = Form(None),
):
    """
    Load a complete meeting bundle with:
    - Structured summary (canonical format)
    - Optional Pocket AI summary (creates document for signal extraction)
    - Optional Pocket Mind Map (triggers synthesis)
    - Optional Pocket Action Items (merged into signals_json)
    - Optional transcripts (merged into searchable document)
    - Optional screenshots (attached to meeting)
    """
    tool = TOOL_REGISTRY["load_meeting_bundle"]
    
    # Merge transcripts if provided
    transcript_parts = []
    if pocket_transcript and pocket_transcript.strip():
        transcript_parts.append(f"=== Pocket Transcript ===\n{pocket_transcript.strip()}")
    if teams_transcript and teams_transcript.strip():
        transcript_parts.append(f"=== Teams Transcript ===\n{teams_transcript.strip()}")
    
    merged_transcript = "\n\n".join(transcript_parts) if transcript_parts else None

    result = tool({
        "meeting_name": meeting_name,
        "meeting_date": meeting_date,
        "summary_text": summary_text,
        "transcript_text": merged_transcript,
        "pocket_ai_summary": pocket_ai_summary,
        "pocket_mind_map": pocket_mind_map,
        "pocket_recording_id": pocket_recording_id,
        "format": "plain",
    })
    
    meeting_id = result.get("meeting_id")
    
    # Store Pocket action items in signals if provided
    if meeting_id and pocket_action_items and pocket_action_items.strip():
        try:
            # Parse action items from the text format back to structured data
            # Parse JSON from hidden field (contains array of action item objects)
            pocket_items = json.loads(pocket_action_items.strip())
            
            # Add source marker to each item
            for item in pocket_items:
                item["source"] = "pocket"
            
            if pocket_items:
                # Get current meeting signals from Supabase
                meeting = meeting_service.get_meeting_by_id(meeting_id)
                if meeting:
                    signals = meeting.get("signals", {})
                    
                    # Merge Pocket action items (preserve existing)
                    existing_items = signals.get("action_items", [])
                    signals["action_items"] = existing_items + pocket_items
                    
                    # Update in Supabase
                    meeting_service.update_meeting(meeting_id, {"signals": signals})
                    
                logging.getLogger(__name__).info(f"Added {len(pocket_items)} Pocket action items to meeting {meeting_id}")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to parse/store Pocket action items: {e}")
    
    # Handle screenshot uploads if meeting was created successfully
    if meeting_id:
        form = await request.form()
        screenshots = form.getlist("screenshots")
        
        for screenshot in screenshots:
            if hasattr(screenshot, 'file') and screenshot.filename:
                try:
                    import uuid
                    import os
                    
                    content = await screenshot.read()
                    mime_type = screenshot.content_type or 'image/png'
                    
                    # Try Supabase Storage first
                    supabase_url = None
                    supabase_path = None
                    local_path = None
                    
                    try:
                        from .services.storage_supabase import upload_file_to_supabase
                        supabase_url, supabase_path = await upload_file_to_supabase(
                            content=content,
                            filename=screenshot.filename,
                            meeting_id=meeting_id,
                            content_type=mime_type
                        )
                    except Exception as e:
                        logger.warning(f"Supabase upload failed, using local: {e}")
                    
                    # Fallback to local storage if Supabase fails
                    if not supabase_url:
                        ext = os.path.splitext(screenshot.filename)[1] or '.png'
                        unique_name = f"{uuid.uuid4().hex}{ext}"
                        file_path = os.path.join(UPLOAD_DIR, unique_name)
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        local_path = f"uploads/{unique_name}"
                    
                    # Record in Supabase attachments table
                    supabase.table("attachments").insert({
                        "ref_type": "meeting",
                        "ref_id": meeting_id,
                        "filename": screenshot.filename,
                        "file_path": local_path or "",
                        "mime_type": mime_type,
                        "file_size": len(content),
                        "supabase_url": supabase_url,
                        "supabase_path": supabase_path
                    }).execute()
                except Exception as e:
                    logger.warning(f"Failed to upload screenshot: {e}")
        
        # Auto-trigger synthesis if mindmap was provided
        if pocket_mind_map and pocket_mind_map.strip():
            def trigger_synthesis():
                try:
                    from .services.mindmap_synthesis import MindmapSynthesizer
                    
                    # Store the mindmap for this conversation
                    MindmapSynthesizer.store_conversation_mindmap(
                        conversation_id=f"meeting_{meeting_id}",
                        title=meeting_name,
                        mindmap_data=pocket_mind_map,
                        hierarchy_level=mindmap_level
                    )
                    
                    # Regenerate synthesis
                    MindmapSynthesizer.generate_synthesis(force=True)
                    logger.info(f"✅ Mindmap synthesis triggered for new meeting {meeting_id}")
                except Exception as e:
                    logger.error(f"Failed to trigger mindmap synthesis: {e}")
            
            background_tasks.add_task(trigger_synthesis)
            logger.info(f"Scheduled mindmap synthesis for meeting {meeting_id} at level {mindmap_level}")

    return RedirectResponse(
        url="/meetings?success=meeting_loaded",
        status_code=303,
    )


# -------------------------
# Routers
# -------------------------

app.include_router(meetings_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(query_router)
app.include_router(signals_router)
app.include_router(tickets_router)
app.include_router(test_plans_router)
app.include_router(chat_router)
app.include_router(mcp_router)
app.include_router(accountability_router)
app.include_router(settings_router)
app.include_router(assistant_router)
# REMOVED: app.include_router(career_router) - migrated to career_domain_router
app.include_router(v1_router)  # API v1 versioned endpoints (Phase 3.1)
app.include_router(mobile_router)  # Mobile sync endpoints (Phase 3.2)
app.include_router(admin_router)  # Admin endpoints (Phase 4.1)
app.include_router(api_search_router)  # Semantic/Hybrid search (Phase 5.2)
app.include_router(knowledge_graph_router)  # Knowledge graph links (Phase 5.10)
app.include_router(shortcuts_router)  # Arjuna shortcuts (Technical Debt)
app.include_router(dikw_router)  # DIKW pyramid (Refactor Phase 2) - DEPRECATED: use dikw_domain_router
app.include_router(mindmap_router)  # Mindmap visualization (Refactor Phase 2)
app.include_router(notifications_router)  # Notifications (Refactor Phase 2)
app.include_router(workflow_router)  # Workflow modes & timer (Refactor Phase 2)
app.include_router(reports_router)  # Reports & analytics (Refactor Phase 2)
app.include_router(evaluations_router)  # LangSmith evaluations (Refactor Phase 2)
app.include_router(pocket_router)  # Pocket integration (Refactor Phase 2)
app.include_router(auth_router)  # Authentication (Refactor Phase 2.9)
app.include_router(pages_router)  # Page renders (Refactor Phase 2.9)
app.include_router(ai_endpoints_router)  # AI endpoints (Refactor Phase 2.9)
app.include_router(dashboard_page_router)  # Dashboard page (Refactor Phase 2.9)

# =============================================================================
# New Domain-Driven Routers (Phase 3 - Domain Decomposition)
# =============================================================================
# These are the refactored routers using the repository pattern.
# They will eventually replace the legacy routers above.
# Mounted at /api/domains/* to avoid conflicts during migration.
app.include_router(career_domain_router, prefix="/api/domains")  # Career domain
app.include_router(dikw_domain_router, prefix="/api/domains")  # DIKW domain
app.include_router(meetings_domain_router, prefix="/api/domains")  # Meetings domain
app.include_router(tickets_domain_router, prefix="/api/domains")  # Tickets domain
app.include_router(documents_domain_router, prefix="/api/domains")  # Documents domain
app.include_router(signals_domain_router)  # Signals domain (already has /api/signals prefix)
app.include_router(dashboard_domain_router)  # Dashboard (already has /api/dashboard prefix)
app.include_router(search_domain_router, prefix="/api/domains")  # Search domain (Refactor Phase 2.10)
app.include_router(knowledge_graph_domain_router, prefix="/api/domains")  # Knowledge graph domain (Refactor Phase 2.10)