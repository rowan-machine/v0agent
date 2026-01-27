# src/app/domains/dikw/constants.py
"""
DIKW Domain Constants

Centralized constants for the DIKW knowledge pyramid.
"""

# DIKW Tiers
TIERS = ["data", "information", "knowledge", "wisdom"]

# Default confidence thresholds for promotion
PROMOTION_THRESHOLDS = {
    "data_to_information": 0.6,
    "information_to_knowledge": 0.75,
    "knowledge_to_wisdom": 0.9,
}

# Maximum items per synthesis batch
MAX_SYNTHESIS_BATCH = 50

# Minimum confidence score
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0

# Relationship types
RELATIONSHIP_TYPES = [
    "relates_to",
    "derived_from",
    "supports",
    "contradicts",
    "extends",
    "synthesizes",
]

# Item types by tier
TIER_ITEM_TYPES = {
    "data": ["raw_text", "transcript", "note"],
    "information": ["summary", "insight", "signal"],
    "knowledge": ["pattern", "rule", "principle"],
    "wisdom": ["decision", "recommendation", "strategy"],
}
