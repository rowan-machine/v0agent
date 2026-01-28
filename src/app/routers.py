# src/app/routers.py
"""
Router Registry - Centralized router registration for FastAPI app.

This module provides a single function to register all routers, making main.py
cleaner and providing a clear overview of all API routes.

Best Practice: Keep main.py minimal (~50-100 lines), centralize router
registration here for better maintainability.
"""

from fastapi import FastAPI


def register_routers(app: FastAPI) -> None:
    """
    Register all routers with the FastAPI application.
    
    Routers are organized in sections:
    1. Core domain routers (new architecture at /api/domains/*)
    2. Legacy routers (being deprecated, will be removed)
    3. Infrastructure routers (health, admin, etc.)
    """
    
    # =========================================================================
    # DOMAIN ROUTERS (New Architecture)
    # =========================================================================
    # These follow domain-driven design with repository pattern.
    # Mounted at /api/domains/* to avoid conflicts during migration.
    
    from .domains.career.api import router as career_domain_router
    from .domains.dikw.api import router as dikw_domain_router
    from .domains.meetings.api import router as meetings_domain_router
    from .domains.meetings.api import load_bundle_router_root as meetings_load_router
    from .domains.tickets.api import router as tickets_domain_router
    from .domains.documents.api import router as documents_domain_router
    from .domains.dashboard import router as dashboard_domain_router
    from .domains.signals import signals_router as signals_domain_router
    from .domains.search.api import router as search_domain_router
    from .domains.search.api import fulltext_router as search_fulltext_router
    from .domains.knowledge_graph import router as knowledge_graph_domain_router
    
    app.include_router(career_domain_router, prefix="/api/domains")
    app.include_router(dikw_domain_router, prefix="/api/domains")
    app.include_router(meetings_domain_router, prefix="/api/domains")
    app.include_router(meetings_load_router)  # /meetings/load at root level
    app.include_router(tickets_domain_router, prefix="/api/domains")
    app.include_router(documents_domain_router, prefix="/api/domains")
    app.include_router(signals_domain_router)  # Has /api/signals prefix
    app.include_router(dashboard_domain_router)  # Has /api/dashboard prefix
    app.include_router(search_domain_router, prefix="/api/domains")
    app.include_router(knowledge_graph_domain_router, prefix="/api/domains")
    
    # =========================================================================
    # API ROUTERS (Extracted from main.py)
    # =========================================================================
    # These are well-organized API modules that follow good patterns.
    
    from .api.v1 import router as v1_router
    from .api.mobile import router as mobile_router
    from .api.admin import router as admin_router
    from .api.auth import router as auth_router
    from .api.pages import router as pages_router
    from .api.ai_endpoints import router as ai_endpoints_router
    from .api.dashboard_page import router as dashboard_page_router
    from .api.pocket import router as pocket_router
    from .api.evaluations import router as evaluations_router
    from .api.reports import router as reports_router
    from .api.workflow import router as workflow_router
    from .api.notifications import router as notifications_router
    from .api.shortcuts import router as shortcuts_router
    from .api.versioning import version_router
    
    app.include_router(v1_router)
    app.include_router(mobile_router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(pages_router)
    app.include_router(ai_endpoints_router)
    app.include_router(dashboard_page_router)
    app.include_router(pocket_router)
    app.include_router(evaluations_router)
    app.include_router(reports_router)
    app.include_router(workflow_router)
    app.include_router(notifications_router)
    app.include_router(shortcuts_router)
    app.include_router(version_router)
    
    # =========================================================================
    # LEGACY ROUTERS (Being Migrated to Domain Architecture)
    # =========================================================================
    # These routers will be migrated to domain routers above.
    # Removed in Phase 3: api/search.py, api/knowledge_graph.py, api/dikw.py, api/career.py
    
    from .meetings import router as meetings_router
    from .documents import router as documents_router
    # Legacy search.py moved to domains/search/api/fulltext.py
    from .query import router as query_router
    from .signals import router as signals_router
    from .tickets import router as tickets_router
    from .test_plans import router as test_plans_router
    from .api.chat import router as chat_router
    from .api.mcp import router as mcp_router
    from .api.accountability import router as accountability_router
    from .api.settings import router as settings_router
    from .api.assistant import router as assistant_router
    from .api.mindmap import router as mindmap_router
    
    app.include_router(meetings_router)
    app.include_router(documents_router)
    app.include_router(search_fulltext_router)  # Legacy /search HTML template route
    app.include_router(query_router)
    app.include_router(signals_router)
    app.include_router(tickets_router)
    app.include_router(test_plans_router)
    app.include_router(chat_router)
    app.include_router(mcp_router)
    app.include_router(accountability_router)
    app.include_router(settings_router)
    app.include_router(assistant_router)
    app.include_router(mindmap_router)
