# src/app/domains/career/api/__init__.py
"""
Career Domain API Routes

Thin controllers that delegate to services and repositories.
Aggregates all career sub-routers into a single router for main.py.
"""

from fastapi import APIRouter

from .profile import router as profile_router
from .skills import router as skills_router
from .standups import router as standups_router
from .suggestions import router as suggestions_router
from .memories import router as memories_router
from .code_locker import router as code_locker_router
from .chat import router as chat_router
from .insights import router as insights_router
from .projects import router as projects_router
from .docs import router as docs_router

# Create the aggregated career router
router = APIRouter(prefix="/career", tags=["career"])

# Include all sub-routers
router.include_router(profile_router)
router.include_router(skills_router)
router.include_router(standups_router)
router.include_router(suggestions_router)
router.include_router(memories_router)
router.include_router(code_locker_router)
router.include_router(chat_router)
router.include_router(insights_router)
router.include_router(projects_router)
router.include_router(docs_router)

__all__ = ["router"]
