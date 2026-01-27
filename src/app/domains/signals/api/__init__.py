# src/app/domains/signals/api/__init__.py
"""
Signals Domain API - Combined router for all signal endpoints.

Combines sub-routers:
- browse: Signal browsing by type with filtering
- extraction: Document signal extraction
- status: Signal status management
"""

from fastapi import APIRouter

from .browse import router as browse_router
from .extraction import router as extraction_router

# Create combined router
router = APIRouter(prefix="/api/signals", tags=["signals"])

# Include sub-routers
router.include_router(browse_router)
router.include_router(extraction_router)

__all__ = ["router"]
