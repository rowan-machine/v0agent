# src/app/domains/dikw/__init__.py
"""
DIKW Domain - Data-Information-Knowledge-Wisdom Pyramid

Hierarchical knowledge organization system.

Structure:
- api/: FastAPI route handlers
- services/: Business logic
- constants.py: Domain constants

Endpoints:
- /items: DIKW items CRUD
- /relationships: Links between items
- /synthesis: Knowledge synthesis operations
- /promotion: Tier promotion logic
"""

from fastapi import APIRouter

from .api import items, relationships, synthesis, promotion

# Create domain router
dikw_router = APIRouter(prefix="/dikw", tags=["dikw"])

# Mount sub-routers
dikw_router.include_router(items.router)
dikw_router.include_router(relationships.router)
dikw_router.include_router(synthesis.router)
dikw_router.include_router(promotion.router)

__all__ = ["dikw_router"]
