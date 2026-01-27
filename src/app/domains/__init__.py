# src/app/domains/__init__.py
"""
Domain Layer - Business domains organized by bounded context

Each domain folder contains:
- api/       - HTTP route handlers (thin controllers)
- services/  - Business logic and use cases  
- models/    - Domain-specific models and DTOs
- constants/ - Domain constants and enums

Available domains:
- career/    - Career development, skills, standups, coaching
- dikw/      - Knowledge pyramid (Data, Information, Knowledge, Wisdom)
- meetings/  - Meeting intelligence and signal extraction
- tickets/   - Sprint and ticket management
- documents/ - Document and knowledge management

Usage:
    from src.app.domains.career.api import router as career_router
    from src.app.domains.dikw.api import router as dikw_router
    from src.app.domains.meetings.api import router as meetings_router
    from src.app.domains.tickets.api import router as tickets_router
    from src.app.domains.documents.api import router as documents_router
"""

__all__ = [
    "career",
    "dikw",
    "meetings",
    "tickets",
    "documents",
]
