# src/app/domains/dikw/services/promotion_service.py
"""
DIKW Promotion Service

Business logic for determining promotion readiness and suggestions.
"""

import logging
from typing import Optional

from ..constants import PROMOTION_THRESHOLDS, TIERS

logger = logging.getLogger(__name__)


def calculate_promotion_readiness(item: dict) -> dict:
    """
    Calculate how ready an item is for promotion to the next level.
    
    Args:
        item: DIKW item dictionary
        
    Returns:
        Dictionary with readiness score and factors
    """
    current_level = item.get("level", "data")
    
    # Can't promote beyond wisdom
    if current_level == "wisdom":
        return {
            "ready": False,
            "score": 0.0,
            "reason": "Already at highest level",
            "next_level": None,
            "factors": {}
        }
    
    # Determine next level
    level_index = TIERS.index(current_level)
    next_level = TIERS[level_index + 1]
    
    # Calculate factors
    confidence = item.get("confidence", 0.5)
    if confidence > 1:
        confidence = confidence / 100  # Normalize if percentage
    
    validation_count = item.get("validation_count", 0)
    has_summary = bool(item.get("summary"))
    has_tags = bool(item.get("tags"))
    content_length = len(item.get("content", ""))
    
    # Factor weights
    factors = {
        "confidence": confidence,
        "validations": min(1.0, validation_count / 3),  # Max out at 3 validations
        "has_summary": 1.0 if has_summary else 0.0,
        "has_tags": 1.0 if has_tags else 0.0,
        "content_quality": min(1.0, content_length / 200)  # Favor longer content
    }
    
    # Weighted score
    weights = {
        "confidence": 0.35,
        "validations": 0.25,
        "has_summary": 0.15,
        "has_tags": 0.10,
        "content_quality": 0.15
    }
    
    score = sum(factors[k] * weights[k] for k in factors)
    
    # Get threshold for this promotion
    threshold_key = f"{current_level}_to_{next_level}"
    threshold = PROMOTION_THRESHOLDS.get(threshold_key, 0.7)
    
    ready = score >= threshold
    
    return {
        "ready": ready,
        "score": round(score, 2),
        "threshold": threshold,
        "next_level": next_level,
        "factors": factors,
        "reason": "Ready for promotion" if ready else f"Score {score:.2f} below threshold {threshold}"
    }


def suggest_next_level(item: dict) -> Optional[str]:
    """
    Suggest the next level for a DIKW item.
    
    Args:
        item: DIKW item dictionary
        
    Returns:
        Suggested next level string, or None if at top level
    """
    current_level = item.get("level", "data")
    
    try:
        level_index = TIERS.index(current_level)
        if level_index < len(TIERS) - 1:
            return TIERS[level_index + 1]
    except ValueError:
        pass
    
    return None


def get_promotion_requirements(current_level: str) -> dict:
    """
    Get the requirements for promoting from a given level.
    
    Args:
        current_level: Current DIKW level
        
    Returns:
        Dictionary describing requirements
    """
    requirements = {
        "data": {
            "next_level": "information",
            "requirements": [
                "Content should be parsed and structured",
                "Key facts should be identified",
                "Context should be established",
                "At least 1 validation recommended"
            ],
            "threshold": PROMOTION_THRESHOLDS.get("data_to_information", 0.6)
        },
        "information": {
            "next_level": "knowledge",
            "requirements": [
                "Patterns should be identified across data points",
                "Relationships should be established",
                "Meaning should be interpreted",
                "At least 2 validations recommended"
            ],
            "threshold": PROMOTION_THRESHOLDS.get("information_to_knowledge", 0.75)
        },
        "knowledge": {
            "next_level": "wisdom",
            "requirements": [
                "Actionable insights should be derived",
                "Strategic implications understood",
                "Cross-domain applicability established",
                "At least 3 validations recommended"
            ],
            "threshold": PROMOTION_THRESHOLDS.get("knowledge_to_wisdom", 0.9)
        },
        "wisdom": {
            "next_level": None,
            "requirements": ["Already at highest level"],
            "threshold": 1.0
        }
    }
    
    return requirements.get(current_level, requirements["data"])
