# src/app/ui/__init__.py
"""
UI Configuration Package - Phase 3.5

Provides JSON-based UI configuration for swappable frontend implementations.
"""

from .config import UIConfig, get_ui_config, reload_ui_config

__all__ = ["UIConfig", "get_ui_config", "reload_ui_config"]
