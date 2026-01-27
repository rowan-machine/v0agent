# src/app/domains/assistant/__init__.py
"""
Assistant Domain

Consolidates all assistant-related functionality:
- Chat conversations and threading
- AI assistant (Arjuna) interface
- MCP tool calling
- Smart context and suggestions
"""

from .api import router

__all__ = ["router"]
