# src/app/domains/tickets/constants.py
"""
Tickets Domain Constants
"""

# Ticket statuses
TICKET_STATUSES = [
    "backlog",
    "todo",
    "in_progress",
    "in_review",
    "done",
    "blocked",
    "cancelled",
]

# Ticket types
TICKET_TYPES = [
    "feature",
    "bug",
    "task",
    "spike",
    "chore",
    "epic",
]

# Priority levels
PRIORITIES = ["critical", "high", "medium", "low"]

# Default limits
DEFAULT_TICKET_LIMIT = 50
DEFAULT_SPRINT_LIMIT = 10
