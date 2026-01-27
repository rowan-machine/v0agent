# src/app/domains/__init__.py
"""
Domain Layer - Business domains organized by bounded context

Each domain folder contains:
- api/       - HTTP route handlers (thin controllers)
- services/  - Business logic and use cases  
- models/    - Domain-specific models and DTOs
- constants/ - Domain constants and enums

Available domains:
- career/  - Career development, skills, standups, coaching
- dikw/    - Knowledge pyramid (Data, Information, Knowledge, Wisdom)

Usage:
    from src.app.domains.career.api import router as career_router
    from src.app.domains.dikw.api import router as dikw_router
"""

__all__ = [
    "career",
    "dikw",
]
