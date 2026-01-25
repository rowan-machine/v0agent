# src/app/infrastructure/feature_flags.py
"""
Feature Flags System

Provides beta flags for features that are still in development or have known issues.
Flags can be controlled via environment variables or the UI settings.

Usage:
    from src.app.infrastructure.feature_flags import is_enabled, get_all_flags
    
    if is_enabled('meeting_signals'):
        # Use the new feature
    else:
        # Use fallback
"""

import os
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class FeatureStatus(Enum):
    """Feature stability status."""
    STABLE = "stable"           # Production-ready
    BETA = "beta"               # Testing, may have bugs
    ALPHA = "alpha"             # Early development, expect issues
    DEPRECATED = "deprecated"   # Being phased out
    DISABLED = "disabled"       # Turned off


# Feature flag definitions with metadata
FEATURE_FLAGS: Dict[str, Dict[str, Any]] = {
    # ===== STABLE FEATURES =====
    "core_meetings": {
        "status": FeatureStatus.STABLE,
        "description": "Basic meeting CRUD operations",
        "default": True,
    },
    "core_documents": {
        "status": FeatureStatus.STABLE,
        "description": "Document management",
        "default": True,
    },
    "core_tickets": {
        "status": FeatureStatus.STABLE,
        "description": "Ticket tracking",
        "default": True,
    },
    
    # ===== BETA FEATURES =====
    "meeting_signals": {
        "status": FeatureStatus.BETA,
        "description": "AI signal extraction from meetings (decisions, actions, blockers)",
        "default": True,
        "known_issues": [
            "Signal confidence scores may be inconsistent",
            "Duplicate signals occasionally created",
        ],
    },
    "dikw_synthesis": {
        "status": FeatureStatus.BETA,
        "description": "DIKW knowledge pyramid synthesis",
        "default": True,
        "known_issues": [
            "Promotion criteria may need tuning",
            "Merge operations can lose metadata",
        ],
    },
    "career_coaching": {
        "status": FeatureStatus.BETA,
        "description": "AI-powered career suggestions and standup feedback",
        "default": True,
        "known_issues": [
            "Suggestions may repeat across sessions",
            "Skill tracking needs more data points",
        ],
    },
    "unified_search": {
        "status": FeatureStatus.BETA,
        "description": "Cross-entity search with semantic ranking",
        "default": True,
        "known_issues": [
            "May return stale results if embeddings not updated",
        ],
    },
    "documentation_reader": {
        "status": FeatureStatus.BETA,
        "description": "Extract career info from repository docs",
        "default": True,
        "known_issues": [
            "Only parses markdown files",
            "May miss nested documentation",
        ],
    },
    
    # ===== ALPHA FEATURES =====
    "real_time_sync": {
        "status": FeatureStatus.ALPHA,
        "description": "Real-time Supabase subscriptions for cross-device sync",
        "default": False,
        "known_issues": [
            "Connection drops under high load",
            "Conflict resolution needs work",
        ],
    },
    "mind_map_rag": {
        "status": FeatureStatus.ALPHA,
        "description": "RAG-enhanced mind map generation",
        "default": False,
        "known_issues": [
            "Context window limits on large meetings",
            "May produce incomplete hierarchies",
        ],
    },
    "multi_agent": {
        "status": FeatureStatus.ALPHA,
        "description": "Multi-agent AI architecture",
        "default": False,
        "known_issues": [
            "Agent routing not fully optimized",
            "Context passing between agents limited",
        ],
    },
    
    # ===== DEPRECATED FEATURES =====
    "sqlite_primary": {
        "status": FeatureStatus.DEPRECATED,
        "description": "Use SQLite as primary database (migrating to Supabase)",
        "default": False,
        "deprecation_notice": "Supabase is now the primary database. SQLite will be removed in v2.0.",
    },
}


def is_enabled(feature_name: str, default: Optional[bool] = None) -> bool:
    """
    Check if a feature is enabled.
    
    Checks in order:
    1. Environment variable: FEATURE_{FEATURE_NAME}=true/false
    2. Feature flag default value
    3. Provided default parameter
    
    Args:
        feature_name: Name of the feature
        default: Default if feature not found
    
    Returns:
        True if feature is enabled
    """
    # Check environment variable override
    env_key = f"FEATURE_{feature_name.upper()}"
    env_value = os.environ.get(env_key)
    
    if env_value is not None:
        return env_value.lower() in ("true", "1", "yes", "on")
    
    # Check feature definition
    feature = FEATURE_FLAGS.get(feature_name)
    if feature:
        # Disabled features are always off
        if feature["status"] == FeatureStatus.DISABLED:
            return False
        return feature.get("default", True)
    
    # Fall back to provided default
    if default is not None:
        return default
    
    # Unknown features are disabled by default
    logger.warning(f"Unknown feature flag: {feature_name}")
    return False


def get_feature_status(feature_name: str) -> Optional[FeatureStatus]:
    """Get the stability status of a feature."""
    feature = FEATURE_FLAGS.get(feature_name)
    if feature:
        return feature["status"]
    return None


def get_all_flags() -> Dict[str, Dict[str, Any]]:
    """
    Get all feature flags with their current state.
    
    Returns:
        Dict mapping feature name to flag info including current enabled state
    """
    result = {}
    for name, config in FEATURE_FLAGS.items():
        result[name] = {
            **config,
            "status": config["status"].value,  # Convert enum to string
            "enabled": is_enabled(name),
        }
    return result


def get_beta_features() -> Dict[str, Dict[str, Any]]:
    """Get only beta features with known issues."""
    return {
        name: {**config, "status": config["status"].value, "enabled": is_enabled(name)}
        for name, config in FEATURE_FLAGS.items()
        if config["status"] == FeatureStatus.BETA
    }


def get_alpha_features() -> Dict[str, Dict[str, Any]]:
    """Get only alpha features (experimental)."""
    return {
        name: {**config, "status": config["status"].value, "enabled": is_enabled(name)}
        for name, config in FEATURE_FLAGS.items()
        if config["status"] == FeatureStatus.ALPHA
    }


def run_diagnostics() -> Dict[str, Any]:
    """
    Run feature diagnostics and return status report.
    
    Checks:
    - Feature flag configuration
    - Environment overrides
    - Known issues summary
    """
    diagnostics = {
        "feature_count": len(FEATURE_FLAGS),
        "enabled_count": sum(1 for f in FEATURE_FLAGS if is_enabled(f)),
        "by_status": {
            "stable": [],
            "beta": [],
            "alpha": [],
            "deprecated": [],
            "disabled": [],
        },
        "environment_overrides": [],
        "all_known_issues": [],
    }
    
    for name, config in FEATURE_FLAGS.items():
        status = config["status"].value
        diagnostics["by_status"][status].append(name)
        
        # Check for env overrides
        env_key = f"FEATURE_{name.upper()}"
        if os.environ.get(env_key):
            diagnostics["environment_overrides"].append({
                "feature": name,
                "env_var": env_key,
                "value": os.environ.get(env_key),
            })
        
        # Collect known issues
        if "known_issues" in config:
            for issue in config["known_issues"]:
                diagnostics["all_known_issues"].append({
                    "feature": name,
                    "status": status,
                    "issue": issue,
                })
    
    return diagnostics
