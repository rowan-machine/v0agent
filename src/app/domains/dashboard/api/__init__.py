# src/app/domains/dashboard/api/__init__.py
"""
Dashboard API Router

Combines all dashboard-related sub-routers.
"""

from fastapi import APIRouter

from .quick_ask import router as quick_ask_router
from .highlights import router as highlights_router
from .context import router as context_router

# Create combined router with /api/dashboard prefix
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Include sub-routers
router.include_router(quick_ask_router)
router.include_router(highlights_router)
router.include_router(context_router)

__all__ = ["router"]
