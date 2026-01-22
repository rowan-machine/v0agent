# src/app/ui/config.py
"""
UI Configuration System - Phase 3.5

Provides JSON-based UI configuration for swappable frontend implementations.
Supports multiple frontends (Jinja2, React, React Native) from single config.

Usage:
    from .ui.config import UIConfig, get_ui_config
    
    # Get singleton config
    config = get_ui_config()
    
    # Check feature flag
    if config.is_feature_enabled("enableAssistantWidget"):
        # Show assistant widget
        
    # Get layout for page
    layout = config.get_layout("dashboard", breakpoint="desktop")
    
    # Get theme
    theme = config.get_theme("light")
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache


class UIConfig:
    """
    JSON-based UI configuration manager.
    
    Loads config/ui.json and provides typed access to:
    - Layouts (page structures with breakpoints)
    - Components (implementation mappings)
    - Themes (colors, fonts, spacing)
    - Feature flags (enable/disable features)
    """
    
    _instance: Optional['UIConfig'] = None
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Load UI configuration from JSON file.
        
        Args:
            config_path: Path to ui.json. Defaults to config/ui.json
        """
        if config_path is None:
            # Find config relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / "config" / "ui.json"
        
        self._config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load and parse the UI configuration file."""
        if not self._config_path.exists():
            print(f"⚠️ UI config not found at {self._config_path}, using defaults")
            self._config = self._default_config()
            return
        
        try:
            with open(self._config_path, 'r') as f:
                self._config = json.load(f)
            print(f"✅ Loaded UI config v{self._config.get('version', '?')}")
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse UI config: {e}")
            self._config = self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return minimal default configuration."""
        return {
            "version": "1.0",
            "layouts": {},
            "components": {},
            "themes": {
                "light": {
                    "name": "Light Theme",
                    "colors": {"primary": "#0066cc", "background": "#ffffff"}
                }
            },
            "featureFlags": {}
        }
    
    @property
    def version(self) -> str:
        """Get config schema version."""
        return self._config.get("version", "1.0")
    
    # -------------------------
    # Feature Flags
    # -------------------------
    
    def is_feature_enabled(
        self, 
        feature_name: str, 
        environment: str = "development",
        user_id: Optional[str] = None
    ) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            feature_name: Name of the feature flag
            environment: Current environment (development/production)
            user_id: Optional user ID for percentage-based rollout
            
        Returns:
            True if feature is enabled for this context
        """
        flags = self._config.get("featureFlags", {})
        flag = flags.get(feature_name)
        
        if not flag:
            return False
        
        if not flag.get("enabled", False):
            return False
        
        # Check environment restriction
        allowed_envs = flag.get("environments", [])
        if allowed_envs and environment not in allowed_envs:
            return False
        
        # Check rollout percentage
        rollout = flag.get("rolloutPercentage", 100)
        if rollout < 100 and user_id:
            # Deterministic percentage based on user_id hash
            user_bucket = hash(user_id) % 100
            if user_bucket >= rollout:
                return False
        
        return True
    
    def get_feature_flags(self) -> Dict[str, Dict[str, Any]]:
        """Get all feature flags."""
        return self._config.get("featureFlags", {})
    
    # -------------------------
    # Layouts
    # -------------------------
    
    def get_layout(
        self, 
        page_name: str, 
        breakpoint: str = "desktop"
    ) -> Optional[Dict[str, Any]]:
        """
        Get layout configuration for a page.
        
        Args:
            page_name: Name of the page (dashboard, meetings, signals, etc.)
            breakpoint: Breakpoint name (desktop, tablet, mobile)
            
        Returns:
            Layout configuration dict or None
        """
        layouts = self._config.get("layouts", {})
        page_layout = layouts.get(page_name)
        
        if not page_layout:
            return None
        
        breakpoints = page_layout.get("breakpoints", {})
        return breakpoints.get(breakpoint)
    
    def get_page_sections(
        self, 
        page_name: str, 
        breakpoint: str = "desktop"
    ) -> List[Dict[str, Any]]:
        """
        Get sections for a page layout.
        
        Returns list of section configs with component names and props.
        """
        layout = self.get_layout(page_name, breakpoint)
        if not layout:
            return []
        return layout.get("sections", [])
    
    # -------------------------
    # Components
    # -------------------------
    
    def get_component(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Get component configuration by name."""
        components = self._config.get("components", {})
        return components.get(component_name)
    
    def get_component_implementation(
        self, 
        component_name: str, 
        implementation_type: str = "jinja"
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific implementation for a component.
        
        Args:
            component_name: Name of the component
            implementation_type: Type (jinja, react, mobile, etc.)
            
        Returns:
            Implementation config with path and type
        """
        component = self.get_component(component_name)
        if not component:
            return None
        
        implementations = component.get("implementations", {})
        return implementations.get(implementation_type)
    
    def get_component_path(
        self, 
        component_name: str, 
        implementation_type: str = "jinja"
    ) -> Optional[str]:
        """Get the file path for a component implementation."""
        impl = self.get_component_implementation(component_name, implementation_type)
        if impl:
            return impl.get("path")
        return None
    
    # -------------------------
    # Themes
    # -------------------------
    
    def get_theme(self, theme_name: str = "light") -> Dict[str, Any]:
        """
        Get theme configuration.
        
        Args:
            theme_name: Theme name (light, dark)
            
        Returns:
            Theme config with colors, fonts, spacing
        """
        themes = self._config.get("themes", {})
        return themes.get(theme_name, themes.get("light", {}))
    
    def get_theme_colors(self, theme_name: str = "light") -> Dict[str, str]:
        """Get color palette for a theme."""
        theme = self.get_theme(theme_name)
        return theme.get("colors", {})
    
    def get_theme_fonts(self, theme_name: str = "light") -> Dict[str, Any]:
        """Get font configuration for a theme."""
        theme = self.get_theme(theme_name)
        return theme.get("fonts", {})
    
    # -------------------------
    # Utilities
    # -------------------------
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()
    
    def to_dict(self) -> Dict[str, Any]:
        """Get full configuration as dict."""
        return self._config.copy()
    
    def get_frontend_config(self, implementation_type: str = "jinja") -> Dict[str, Any]:
        """
        Get configuration formatted for frontend consumption.
        
        Returns simplified config with resolved component paths.
        """
        return {
            "version": self.version,
            "theme": self.get_theme(),
            "featureFlags": {
                name: flag.get("enabled", False)
                for name, flag in self.get_feature_flags().items()
            }
        }


# Singleton accessor
_ui_config: Optional[UIConfig] = None


def get_ui_config() -> UIConfig:
    """Get singleton UIConfig instance."""
    global _ui_config
    if _ui_config is None:
        _ui_config = UIConfig()
    return _ui_config


def reload_ui_config() -> UIConfig:
    """Reload UI configuration from file."""
    global _ui_config
    _ui_config = UIConfig()
    return _ui_config
