# src/app/domains/signals/api/browse.py
"""
Signal Browsing API - Browse signals by type with date filtering.

Provides endpoints for viewing signals across all meetings, filtered by:
- Signal type (decisions, action_items, blockers, risks, ideas, all)
- Date range (7 days, 14 days, 30 days, 42 days, 90 days, all)

Uses repository pattern for data access.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import logging

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from ....repositories import get_meeting_repository, get_signal_repository

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")

# =============================================================================
# CONSTANTS
# =============================================================================

# Preset date ranges (days back from today)
DATE_PRESETS = {
    "all": None,
    "7": 7,       # Past week
    "14": 14,     # This sprint (2 weeks)
    "30": 30,     # Past month
    "42": 42,     # Last 3 sprints (6 weeks)
    "90": 90,     # Past quarter
}

# Map display names to database field names
SIGNAL_TYPE_MAP = {
    "decisions": "decision",
    "action_items": "action",
    "blockers": "blocker",
    "risks": "risk",
    "ideas": "idea",
}

SIGNAL_TYPES = ["decisions", "action_items", "blockers", "risks", "ideas"]


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def get_signals_by_type(
    signal_type: str, 
    days: Optional[int] = None, 
    limit: int = 100
) -> tuple[List[Dict[str, Any]], int]:
    """Get all signals of a specific type across meetings.
    
    Args:
        signal_type: Type of signal ('decisions', 'action_items', 'blockers', 
                     'risks', 'ideas', or 'all')
        days: Optional number of days to look back (None = all time)
        limit: Maximum number of meetings to fetch
    
    Returns:
        Tuple of (list of meeting signal results, total signal count)
    """
    meeting_repo = get_meeting_repository()
    signal_repo = get_signal_repository()
    
    # Get meetings with signals using repository
    meetings = meeting_repo.get_with_signals_by_days(days=days, limit=limit)
    if not meetings:
        return [], 0

    # Get signal statuses using repository
    meeting_ids = [m["id"] for m in meetings]
    status_map = signal_repo.get_status_for_meetings(meeting_ids) if meeting_ids else {}

    results = []
    total_signals = 0

    for meeting in meetings:
        if not meeting.get("signals"):
            continue

        try:
            signals = meeting["signals"] if isinstance(meeting["signals"], dict) else json.loads(meeting["signals"])
        except Exception:
            continue
        
        if signal_type == "all":
            items = _collect_all_signals(meeting, signals, status_map)
        else:
            items = _collect_typed_signals(meeting, signals, signal_type, status_map)
        
        if items:
            results.append({
                "meeting_id": meeting["id"],
                "meeting_name": meeting["meeting_name"],
                "meeting_date": meeting["meeting_date"],
                "signals": items
            })
            total_signals += len(items)
    
    return results, total_signals


def _collect_all_signals(
    meeting: Dict[str, Any],
    signals: Dict[str, Any],
    status_map: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Collect signals of all types from a meeting."""
    all_items = []
    
    for stype in SIGNAL_TYPES:
        items = signals.get(stype, [])
        mapped_type = SIGNAL_TYPE_MAP.get(stype, stype)
        
        if isinstance(items, list):
            for item in items:
                if item:
                    status_key = f"{meeting['id']}:{mapped_type}:{item}"
                    status_data = status_map.get(status_key, {})
                    all_items.append({
                        "text": item,
                        "type": mapped_type,
                        "status": status_data.get("status") if status_data else None
                    })
        elif isinstance(items, str) and items.strip():
            status_key = f"{meeting['id']}:{mapped_type}:{items}"
            status_data = status_map.get(status_key, {})
            all_items.append({
                "text": items,
                "type": mapped_type,
                "status": status_data.get("status") if status_data else None
            })
    
    return all_items


def _collect_typed_signals(
    meeting: Dict[str, Any],
    signals: Dict[str, Any],
    signal_type: str,
    status_map: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Collect signals of a specific type from a meeting."""
    signal_items = signals.get(signal_type, [])
    items = []
    mapped_type = SIGNAL_TYPE_MAP.get(signal_type, signal_type)
    
    if isinstance(signal_items, list):
        for s in signal_items:
            if s:
                status_key = f"{meeting['id']}:{mapped_type}:{s}"
                status_data = status_map.get(status_key, {})
                items.append({
                    "text": s,
                    "type": mapped_type,
                    "status": status_data.get("status") if status_data else None
                })
    elif isinstance(signal_items, str) and signal_items.strip():
        status_key = f"{meeting['id']}:{mapped_type}:{signal_items}"
        status_data = status_map.get(status_key, {})
        items = [{
            "text": signal_items,
            "type": mapped_type,
            "status": status_data.get("status") if status_data else None
        }]
    
    return items


def signals_response(request: Request, signal_type: str, days: str = "all"):
    """Common response builder for all signal endpoints."""
    days_int = DATE_PRESETS.get(days)
    meetings, total = get_signals_by_type(signal_type, days=days_int)
    return templates.TemplateResponse(
        "signals.html",
        {
            "request": request,
            "signal_type": signal_type,
            "meetings": meetings,
            "total_signals": total,
            "selected_days": days,
        },
    )


# =============================================================================
# API ENDPOINTS - JSON
# =============================================================================

@router.get("/list")
async def list_signals(
    signal_type: str = Query(default="all", description="Signal type to filter by"),
    days: str = Query(default="all", description="Date range preset")
):
    """List signals with optional filtering.
    
    Returns JSON list of signals across meetings.
    """
    days_int = DATE_PRESETS.get(days)
    meetings, total = get_signals_by_type(signal_type, days=days_int)
    
    return JSONResponse({
        "signal_type": signal_type,
        "days": days,
        "meetings": meetings,
        "total_signals": total
    })


# =============================================================================
# HTML ENDPOINTS - Signal Browsing
# =============================================================================

@router.get("/view")
@router.get("/view/all")
def signals_all(request: Request, days: str = Query(default="all")):
    """View all signals (HTML)."""
    return signals_response(request, "all", days)


@router.get("/view/decisions")
def signals_decisions(request: Request, days: str = Query(default="all")):
    """View decision signals (HTML)."""
    return signals_response(request, "decisions", days)


@router.get("/view/action_items")
def signals_action_items(request: Request, days: str = Query(default="all")):
    """View action item signals (HTML)."""
    return signals_response(request, "action_items", days)


@router.get("/view/blockers")
def signals_blockers(request: Request, days: str = Query(default="all")):
    """View blocker signals (HTML)."""
    return signals_response(request, "blockers", days)


@router.get("/view/risks")
def signals_risks(request: Request, days: str = Query(default="all")):
    """View risk signals (HTML)."""
    return signals_response(request, "risks", days)


@router.get("/view/ideas")
def signals_ideas(request: Request, days: str = Query(default="all")):
    """View idea signals (HTML)."""
    return signals_response(request, "ideas", days)
