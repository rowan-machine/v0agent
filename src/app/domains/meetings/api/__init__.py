# src/app/domains/meetings/api/__init__.py
"""
Meetings Domain API Routes

Aggregates all meeting sub-routers into a single router for main.py.
"""

from fastapi import APIRouter

from .crud import router as crud_router
from .search import router as search_router
from .signals import router as signals_router
from .transcripts import router as transcripts_router
from .load_bundle import router as load_bundle_router

# Create the aggregated meetings router
router = APIRouter(prefix="/meetings", tags=["meetings"])

# Include all sub-routers
# crud_router has no prefix (routes at /meetings/*)
router.include_router(crud_router, tags=["meetings-crud"])
router.include_router(search_router)
router.include_router(signals_router)
router.include_router(transcripts_router)

# Load bundle router - mounted at root level (not under /meetings prefix)
# because the route is /meetings/load, not /meetings/meetings/load
load_bundle_router_root = APIRouter()
load_bundle_router_root.include_router(load_bundle_router)

__all__ = ["router", "load_bundle_router_root"]
