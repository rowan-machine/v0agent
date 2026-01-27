# src/app/domains/career/constants.py
"""
Career Domain Constants
"""

# Career suggestion types
SUGGESTION_TYPES = [
    "skill",
    "learning", 
    "project",
    "networking",
    "certification",
    "mentorship",
]

# Suggestion statuses
SUGGESTION_STATUSES = {
    "pending": "Pending review",
    "accepted": "Accepted",
    "dismissed": "Dismissed",
    "converted": "Converted to ticket",
}

# Skill categories
SKILL_CATEGORIES = [
    "programming",
    "frameworks",
    "databases",
    "devops",
    "soft_skills",
    "leadership",
    "domain_knowledge",
]

# Standup moods
STANDUP_MOODS = [
    "great",
    "good",
    "okay",
    "struggling",
    "blocked",
]

# Memory categories
MEMORY_CATEGORIES = [
    "achievement",
    "feedback",
    "learning",
    "challenge",
    "goal",
    "reflection",
]

# Default importance score
DEFAULT_IMPORTANCE = 50
MAX_IMPORTANCE = 100
MIN_IMPORTANCE = 1
