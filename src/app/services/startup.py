"""
Application startup initialization.

Handles FastAPI startup event tasks including scheduler initialization.
Extracted from main.py during Phase 2.9 refactoring.
"""
import logging

logger = logging.getLogger(__name__)


def initialize_app():
    """Initialize the application on startup.
    
    Called by FastAPI's startup event handler.
    """
    print("ℹ️ Starting application with Supabase-only mode")

    # Initialize background job scheduler (production only)
    try:
        from .scheduler import init_scheduler

        scheduler = init_scheduler()
        if scheduler:
            print("✅ Background job scheduler initialized")
    except Exception as e:
        print(f"⚠️ Scheduler init failed (non-fatal): {e}")


def get_startup_handler():
    """Return the startup handler function for FastAPI.
    
    Usage in main.py:
        from .services.startup import get_startup_handler
        app.on_event("startup")(get_startup_handler())
    
    Or:
        @app.on_event("startup")
        def startup():
            initialize_app()
    """
    return initialize_app
