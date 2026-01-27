# src/app/shared/config/__init__.py
"""
Shared Configuration - Application settings and configuration management

Provides centralized access to application configuration from various sources.
"""

from ...config import (
    Settings,
    get_settings,
)

__all__ = [
    "Settings",
    "get_settings",
]
