# src/app/domains/dikw/api/__init__.py
"""
DIKW API Layer

Route handlers organized by resource:
- items: CRUD operations for DIKW items
- relationships: Links between items  
- synthesis: Knowledge synthesis operations
- promotion: Tier promotion logic

Aggregates all DIKW sub-routers into a single router for main.py.
"""

from fastapi import APIRouter

from .items import router as items_router
from .relationships import router as relationships_router
from .synthesis import router as synthesis_router
from .promotion import router as promotion_router

# Create the aggregated DIKW router
router = APIRouter(prefix="/dikw", tags=["dikw"])

# Include all sub-routers
router.include_router(items_router)
router.include_router(relationships_router)
router.include_router(synthesis_router)
router.include_router(promotion_router)

__all__ = ["router"]
