# src/app/domains/workflow/api/tracing.py
"""
LangSmith Tracing Status API Routes

Provides debug information about LangSmith tracing configuration.
"""

import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/v1/tracing/status")
async def get_tracing_status():
    """Debug endpoint to check LangSmith tracing status."""
    tracing_status = {
        "langchain_tracing_v2": os.environ.get("LANGCHAIN_TRACING_V2", "not set"),
        "langsmith_tracing": os.environ.get("LANGSMITH_TRACING", "not set"),
        "langsmith_api_key_set": bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")),
        "langsmith_project": os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT", "signalflow"),
        "langsmith_endpoint": os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
    }
    
    # Check if tracing module is available and enabled
    try:
        from ....tracing import is_tracing_enabled, get_langsmith_client, get_project_name
        tracing_status["tracing_module_available"] = True
        tracing_status["tracing_enabled"] = is_tracing_enabled()
        tracing_status["project_name"] = get_project_name()
        
        # Try to get client
        client = get_langsmith_client()
        tracing_status["langsmith_client_initialized"] = client is not None
        
        if client:
            # Try a simple health check
            try:
                # List a few runs to verify connectivity
                runs = list(client.list_runs(project_name=get_project_name(), limit=1))
                tracing_status["langsmith_connectivity"] = "ok"
                tracing_status["recent_runs_count"] = len(runs)
            except Exception as e:
                tracing_status["langsmith_connectivity"] = f"error: {str(e)}"
    except ImportError as e:
        tracing_status["tracing_module_available"] = False
        tracing_status["import_error"] = str(e)
    
    return JSONResponse(tracing_status)
