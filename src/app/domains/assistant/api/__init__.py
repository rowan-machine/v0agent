# src/app/domains/assistant/api/__init__.py
"""
Assistant Domain API Routes

Aggregates:
- conversations.py: Chat conversation management
- arjuna.py: Smart assistant interface
- mcp.py: MCP tool calling
"""

from fastapi import APIRouter

from .conversations import router as conversations_router
from .arjuna import router as arjuna_router
from .mcp import router as mcp_router

router = APIRouter(prefix="/assistant", tags=["assistant"])

# Conversation management (from chat.py)
router.include_router(conversations_router)

# Arjuna smart assistant (from assistant.py)
router.include_router(arjuna_router)

# MCP tool calling (from mcp.py)
router.include_router(mcp_router)

__all__ = ["router"]
