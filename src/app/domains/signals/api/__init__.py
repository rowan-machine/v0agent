# src/app/domains/signals/api/__init__.py
"""
Signals Domain API - Combined router for all signal endpoints.

Combines sub-routers:
- browse: Signal browsing by type with filtering
- extraction: Document signal extraction
- learning: Signal feedback learning and quality hints
- status: Signal status, feedback, and ticket conversion
"""

from fastapi import APIRouter

from .browse import router as browse_router
from .extraction import router as extraction_router
from .learning import router as learning_router
from .status import router as status_router

# Create combined router
router = APIRouter(prefix="/api/signals", tags=["signals"])

# Include sub-routers
router.include_router(browse_router)
router.include_router(extraction_router)
router.include_router(learning_router)
router.include_router(status_router)

__all__ = ["router"]
