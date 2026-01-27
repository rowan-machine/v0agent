# src/app/domains/meetings/constants.py
"""
Meetings Domain Constants
"""

# Meeting types
MEETING_TYPES = [
    "standup",
    "planning",
    "retrospective",
    "one_on_one",
    "all_hands",
    "workshop",
    "interview",
    "sync",
    "review",
    "other",
]

# Signal types extractable from meetings
SIGNAL_TYPES = [
    "decision",
    "action_item",
    "blocker",
    "risk",
    "idea",
    "insight",
    "question",
    "followup",
]

# Default limits
DEFAULT_MEETING_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 10

# Date formats
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
