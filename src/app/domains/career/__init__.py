# src/app/domains/career/__init__.py
"""
Career Domain - Skills, standups, coaching, and career development

Submodules:
- api/profile.py    - Career profile endpoints
- api/skills.py     - Skill tracking endpoints
- api/standups.py   - Standup updates endpoints
- api/suggestions.py - AI suggestions endpoints
- api/memories.py   - Career memories endpoints
- api/code_locker.py - Code snippet storage endpoints

- services/profile_service.py    - Profile business logic
- services/standup_service.py    - Standup analysis
- services/suggestion_service.py - AI suggestion generation
- services/coaching_service.py   - Career coaching logic

- models/dto.py - Request/response DTOs
- constants.py  - Career domain constants
"""

from fastapi import APIRouter

# Create main career router
career_router = APIRouter(prefix="/api/career", tags=["career"])

# Import and include sub-routers
from .api.profile import router as profile_router
from .api.skills import router as skills_router
from .api.standups import router as standups_router
from .api.suggestions import router as suggestions_router
from .api.memories import router as memories_router
from .api.code_locker import router as code_locker_router
from .api.chat import router as chat_router

career_router.include_router(profile_router)
career_router.include_router(skills_router)
career_router.include_router(standups_router)
career_router.include_router(suggestions_router)
career_router.include_router(memories_router)
career_router.include_router(code_locker_router)
career_router.include_router(chat_router)

__all__ = ["career_router"]
