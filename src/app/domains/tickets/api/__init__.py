# src/app/domains/tickets/api/__init__.py
"""
Tickets Domain API Routes

Aggregates all ticket sub-routers into a single router for main.py.
"""

from fastapi import APIRouter

from .crud import router as crud_router
from .sprints import router as sprints_router

# Create the aggregated tickets router
router = APIRouter(prefix="/tickets", tags=["tickets"])

# Include all sub-routers
router.include_router(crud_router, tags=["tickets-crud"])
router.include_router(sprints_router)

__all__ = ["router"]
