# src/app/domains/tickets/api/__init__.py
"""
Tickets Domain API Routes

Aggregates all ticket sub-routers into a single router for main.py.
"""

from fastapi import APIRouter

from .crud import router as crud_router
from .sprints import router as sprints_router
from .ai_features import router as ai_features_router
from .deployment import router as deployment_router
from .attachments import router as attachments_router

# Create the aggregated tickets router
router = APIRouter(prefix="/tickets", tags=["tickets"])

# Include all sub-routers
router.include_router(crud_router, tags=["tickets-crud"])
router.include_router(sprints_router)
router.include_router(ai_features_router, tags=["tickets-ai"])
router.include_router(deployment_router, tags=["tickets-deployment"])
router.include_router(attachments_router, tags=["tickets-attachments"])

__all__ = ["router"]
