# src/app/signals.py
"""
DEPRECATED: Signal views for browsing extracted meeting signals.

This module is deprecated. Use domains/signals/api instead.
Routes are available at:
- /api/signals/* (JSON API)
- /api/signals/view/* (HTML views)

Migration Status:
- New location: src/app/domains/signals/api/
- MeetingAnalyzerAgent: src/app/agents/meeting_analyzer.py
- This file: DEPRECATED - legacy routes only
"""

import warnings

# Emit deprecation warning on import
warnings.warn(
    "signals.py is deprecated. Use domains/signals/api instead. "
    "Routes available at /api/signals/*",
    DeprecationWarning,
    stacklevel=2
)

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import json
from .infrastructure.supabase_client import get_supabase_client

# Import from new MeetingAnalyzer agent (Checkpoint 2.4)
from .agents.meeting_analyzer import (
    MeetingAnalyzerAgent,
    get_meeting_analyzer,
    parse_meeting_summary_adaptive,
    extract_signals_from_meeting,
    SIGNAL_TYPES,
)

router = APIRouter()
templates = Jinja2Templates(directory="src/app/templates")

# Preset date ranges (days back from today)
DATE_PRESETS = {
    "all": None,
    "7": 7,       # Past week
    "14": 14,     # This sprint (2 weeks)
    "30": 30,     # Past month
    "42": 42,     # Last 3 sprints (6 weeks)
    "90": 90,     # Past quarter
}


def get_signals_by_type(signal_type: str, days: int = None, limit: int = 100):
    """Get all signals of a specific type across meetings."""
    type_map = {
        "decisions": "decision",
        "action_items": "action",
        "blockers": "blocker",
        "risks": "risk",
        "ideas": "idea",
    }
    
    supabase = get_supabase_client()
    if not supabase:
        return [], 0

    # Build query - use is_not for null check (neq with None causes JSON parse errors)
    query = supabase.table("meetings").select("id, meeting_name, meeting_date, signals").not_.is_("signals", "null").neq("signals", "{}")

    if days:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query = query.gte("meeting_date", cutoff_date)

    query = query.order("meeting_date", desc=True).limit(limit)
    result = query.execute()
    meetings = result.data or []

    meeting_ids = [m["id"] for m in meetings]
    status_map = {}
    if meeting_ids:
        status_result = supabase.table("signal_status").select("meeting_id, signal_type, signal_text, status").in_("meeting_id", meeting_ids).execute()
        status_rows = status_result.data or []
        for row in status_rows:
            key = f"{row['meeting_id']}:{row['signal_type']}:{row['signal_text']}"
            status_map[key] = row["status"]

    results = []
    total_signals = 0

    for meeting in meetings:
        if not meeting["signals"]:
            continue

        try:
            signals = meeting["signals"] if isinstance(meeting["signals"], dict) else json.loads(meeting["signals"])
        except Exception:
            continue
        
        if signal_type == "all":
            # Collect all signal types
            all_items = []
            for stype in ["decisions", "action_items", "blockers", "risks", "ideas"]:
                items = signals.get(stype, [])
                mapped_type = type_map.get(stype, stype)
                if isinstance(items, list):
                    for item in items:
                        if item:
                            status_key = f"{meeting['id']}:{mapped_type}:{item}"
                            all_items.append({
                                "text": item,
                                "type": mapped_type,
                                "status": status_map.get(status_key)
                            })
                elif isinstance(items, str) and items.strip():
                    status_key = f"{meeting['id']}:{mapped_type}:{items}"
                    all_items.append({
                        "text": items,
                        "type": mapped_type,
                        "status": status_map.get(status_key)
                    })
            
            if all_items:
                results.append({
                    "meeting_id": meeting["id"],
                    "meeting_name": meeting["meeting_name"],
                    "meeting_date": meeting["meeting_date"],
                    "signals": all_items
                })
                total_signals += len(all_items)
        else:
            # Specific signal type
            signal_items = signals.get(signal_type, [])
            items = []
            mapped_type = type_map.get(signal_type, signal_type)
            
            if isinstance(signal_items, list):
                for s in signal_items:
                    if s:
                        status_key = f"{meeting['id']}:{mapped_type}:{s}"
                        items.append({
                            "text": s,
                            "type": mapped_type,
                            "status": status_map.get(status_key)
                        })
            elif isinstance(signal_items, str) and signal_items.strip():
                status_key = f"{meeting['id']}:{mapped_type}:{signal_items}"
                items = [{
                    "text": signal_items,
                    "type": mapped_type,
                    "status": status_map.get(status_key)
                }]
            
            if items:
                results.append({
                    "meeting_id": meeting["id"],
                    "meeting_name": meeting["meeting_name"],
                    "meeting_date": meeting["meeting_date"],
                    "signals": items
                })
                total_signals += len(items)
    
    return results, total_signals


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


@router.get("/signals")
@router.get("/signals/all")
def signals_all(request: Request, days: str = Query(default="all")):
    return signals_response(request, "all", days)


@router.get("/signals/decisions")
def signals_decisions(request: Request, days: str = Query(default="all")):
    return signals_response(request, "decisions", days)


@router.get("/signals/action_items")
def signals_action_items(request: Request, days: str = Query(default="all")):
    return signals_response(request, "action_items", days)


@router.get("/signals/blockers")
def signals_blockers(request: Request, days: str = Query(default="all")):
    return signals_response(request, "blockers", days)


@router.get("/signals/risks")
def signals_risks(request: Request, days: str = Query(default="all")):
    return signals_response(request, "risks", days)


@router.get("/signals/ideas")
def signals_ideas(request: Request, days: str = Query(default="all")):
    return signals_response(request, "ideas", days)


@router.post("/api/signals/extract-from-document")
async def extract_signals_from_document(request: Request):
    """Extract signals from a document (transcript) using MeetingAnalyzerAgent.
    
    Delegates to MeetingAnalyzerAgent (Checkpoint 2.4) for signal extraction.
    This is useful for finding signals that weren't captured during the initial
    meeting summarization process.
    """
    data = await request.json()
    doc_id = data.get("document_id")
    meeting_id = data.get("meeting_id")  # Optional: associate with existing meeting
    
    if not doc_id:
        return JSONResponse({"error": "document_id is required"}, status_code=400)

    supabase = get_supabase_client()
    doc_result = supabase.table("documents").select("id, source, content").eq("id", doc_id).single().execute()
    doc = doc_result.data
    
    if not doc:
        return JSONResponse({"error": "Document not found"}, status_code=404)
    
    content = doc["content"]
    source = doc["source"]
    
    # Truncate if too long
    if len(content) > 15000:
        content = content[:15000] + "\n\n[... truncated for processing ...]"
    
    try:
        # Use MeetingAnalyzerAgent for signal extraction
        agent = get_meeting_analyzer()
        
        # First, try adaptive parsing to extract sections
        parsed_sections = agent.parse_adaptive(content)
        
        # Then extract signals from sections
        signals_result = agent.extract_signals_from_sections(parsed_sections)
        
        # If parsing didn't yield many signals, use AI extraction
        if agent._should_use_ai_extraction(signals_result):
            ai_signals = await agent._extract_signals_with_ai(content, source)
            # Merge with parsed signals
            signals = agent._merge_signals(signals_result, ai_signals)
        else:
            signals = signals_result
        
        # Deduplicate
        signals = agent._deduplicate_signals(signals)
        
        # Convert to expected format
        extracted_signals = {
            "decisions": signals.get("decisions", []),
            "action_items": signals.get("action_items", []),
            "blockers": signals.get("blockers", []),
            "risks": signals.get("risks", []),
            "ideas": signals.get("ideas", []),
        }
        
        # Count extracted signals
        total_extracted = sum(len(extracted_signals.get(k, [])) for k in ["decisions", "action_items", "blockers", "risks", "ideas"])
        
        # If meeting_id provided, merge with existing signals
        if meeting_id:
            meeting_result = supabase.table("meetings").select("signals").eq("id", meeting_id).single().execute()
            meeting = meeting_result.data

            if meeting and meeting.get("signals"):
                existing = meeting["signals"] if isinstance(meeting["signals"], dict) else json.loads(meeting["signals"])
                # Merge new signals (avoiding duplicates)
                for key in ["decisions", "action_items", "blockers", "risks", "ideas"]:
                    existing_items = existing.get(key, [])
                    new_items = extracted_signals.get(key, [])
                    for item in new_items:
                        if item not in existing_items:
                            existing_items.append(item)
                    existing[key] = existing_items

                # Update meeting with merged signals
                supabase.table("meetings").update({"signals": existing}).eq("id", meeting_id).execute()
                
                return JSONResponse({
                    "status": "ok",
                    "action": "merged",
                    "meeting_id": meeting_id,
                    "new_signals": total_extracted,
                    "signals": extracted_signals
                })
        
        return JSONResponse({
            "status": "ok",
            "action": "extracted",
            "document_id": doc_id,
            "total_signals": total_extracted,
            "signals": extracted_signals
        })
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/signals/save-from-document")
async def save_signals_from_document(request: Request):
    """Save extracted signals from a document to the meeting_summaries table.
    
    This creates a pseudo-meeting record to store signals extracted from documents,
    making them visible in the signals dashboard.
    """
    data = await request.json()
    doc_id = data.get("document_id")
    signals = data.get("signals")
    
    if not doc_id or not signals:
        return JSONResponse({"error": "document_id and signals are required"}, status_code=400)
    
    supabase = get_supabase_client()
    
    # Get document info
    doc_result = supabase.table("documents").select("id, source, content, document_date").eq("id", doc_id).single().execute()
    doc = doc_result.data

    if not doc:
        return JSONResponse({"error": "Document not found"}, status_code=404)

    # Check if signals already saved for this document
    existing_result = supabase.table("meetings").select("id").eq("source_document_id", doc_id).execute()
    existing = existing_result.data[0] if existing_result.data else None

    if existing:
        # Update existing record
        supabase.table("meetings").update({
            "signals": signals,
            "updated_at": datetime.now().isoformat()
        }).eq("source_document_id", doc_id).execute()
        return JSONResponse({
            "status": "ok",
            "action": "updated",
            "meeting_id": existing["id"]
        })
    
    # Create new meeting record for document signals
    meeting_name = f"[Document] {doc['source']}"
    meeting_date = doc.get("document_date") or datetime.now().strftime("%Y-%m-%d")
    
    # Count total signals
    total_signals = sum(len(signals.get(k, [])) for k in ["decisions", "action_items", "blockers", "risks", "ideas"])
    
    # Generate a brief summary of the signals for synthesized_notes
    signal_summary_parts = []
    if signals.get("decisions"):
        signal_summary_parts.append(f"{len(signals['decisions'])} decisions")
    if signals.get("action_items"):
        signal_summary_parts.append(f"{len(signals['action_items'])} action items")
    if signals.get("blockers"):
        signal_summary_parts.append(f"{len(signals['blockers'])} blockers")
    if signals.get("risks"):
        signal_summary_parts.append(f"{len(signals['risks'])} risks")
    if signals.get("ideas"):
        signal_summary_parts.append(f"{len(signals['ideas'])} ideas")
    
    synthesized_notes = f"Signals extracted from document: {', '.join(signal_summary_parts) if signal_summary_parts else 'none'}"
    
    insert_result = supabase.table("meetings").insert({
        "meeting_name": meeting_name,
        "meeting_date": meeting_date,
        "synthesized_notes": synthesized_notes,
        "signals": signals,
        "source_document_id": doc_id,
        "created_at": datetime.now().isoformat()
    }).execute()
    
    new_id = insert_result.data[0]["id"] if insert_result.data else None
    
    return JSONResponse({
        "status": "ok",
        "action": "created",
        "meeting_id": new_id,
        "total_signals": total_signals
    })
