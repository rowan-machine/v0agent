# src/app/signals.py
"""Signal views for browsing extracted meeting signals."""

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import json
from .db import connect
from .llm import ask as ask_llm

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
    
    # Build date filter
    date_filter = ""
    params = []
    
    if days:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        date_filter = "AND (meeting_date >= ? OR (meeting_date IS NULL AND created_at >= ?))"
        params = [cutoff_date, cutoff_date]
    
    params.append(limit)
    
    with connect() as conn:
        meetings = conn.execute(
            f"""
            SELECT id, meeting_name, meeting_date, signals_json
            FROM meeting_summaries
            WHERE signals_json IS NOT NULL AND signals_json != '{{}}'
            {date_filter}
            ORDER BY COALESCE(meeting_date, created_at) DESC
            LIMIT ?
            """,
            tuple(params)
        ).fetchall()

        meeting_ids = [m["id"] for m in meetings]
        status_map = {}
        if meeting_ids:
            placeholders = ",".join(["?"] * len(meeting_ids))
            status_rows = conn.execute(
                f"""
                SELECT meeting_id, signal_type, signal_text, status
                FROM signal_status
                WHERE meeting_id IN ({placeholders})
                """,
                tuple(meeting_ids)
            ).fetchall()
            for row in status_rows:
                key = f"{row['meeting_id']}:{row['signal_type']}:{row['signal_text']}"
                status_map[key] = row["status"]
    
    results = []
    total_signals = 0
    
    for meeting in meetings:
        if not meeting["signals_json"]:
            continue
        
        try:
            signals = json.loads(meeting["signals_json"])
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
    """Extract signals from a document (transcript) using LLM.
    
    This is useful for finding signals that weren't captured during the initial
    meeting summarization process.
    """
    data = await request.json()
    doc_id = data.get("document_id")
    meeting_id = data.get("meeting_id")  # Optional: associate with existing meeting
    
    if not doc_id:
        return JSONResponse({"error": "document_id is required"}, status_code=400)
    
    with connect() as conn:
        doc = conn.execute(
            "SELECT id, source, content FROM docs WHERE id = ?",
            (doc_id,)
        ).fetchone()
        
        if not doc:
            return JSONResponse({"error": "Document not found"}, status_code=404)
        
        content = doc["content"]
        source = doc["source"]
        
        # Truncate if too long
        if len(content) > 15000:
            content = content[:15000] + "\n\n[... truncated for processing ...]"
        
        # Extract signals using LLM
        prompt = f"""Analyze this transcript/document and extract important signals. Look for items that may have been missed during initial meeting summarization.

Document: {source}

Content:
{content}

Extract and categorize signals into these types:
1. **Decisions** - Any decisions made or agreed upon
2. **Action Items** - Tasks, commitments, follow-ups assigned to people
3. **Blockers** - Issues blocking progress, dependencies
4. **Risks** - Potential problems, concerns, uncertainties
5. **Ideas** - Suggestions, proposals, future possibilities

Return as JSON with this exact structure:
{{
  "decisions": ["decision 1", "decision 2"],
  "action_items": ["action 1 @person", "action 2"],
  "blockers": ["blocker 1", "blocker 2"],
  "risks": ["risk 1", "risk 2"],
  "ideas": ["idea 1", "idea 2"]
}}

Only include signals that are clearly stated or strongly implied. Be specific and include @mentions where people are assigned tasks. Return empty arrays for categories with no signals."""

        try:
            response = ask_llm(prompt, model="gpt-4o-mini")
            
            # Parse the JSON response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                signals = json.loads(response[json_start:json_end])
            else:
                signals = json.loads(response)
            
            # Count extracted signals
            total_extracted = sum(len(signals.get(k, [])) for k in ["decisions", "action_items", "blockers", "risks", "ideas"])
            
            # If meeting_id provided, merge with existing signals
            if meeting_id:
                meeting = conn.execute(
                    "SELECT signals_json FROM meeting_summaries WHERE id = ?",
                    (meeting_id,)
                ).fetchone()
                
                if meeting and meeting["signals_json"]:
                    existing = json.loads(meeting["signals_json"])
                    # Merge new signals (avoiding duplicates)
                    for key in ["decisions", "action_items", "blockers", "risks", "ideas"]:
                        existing_items = existing.get(key, [])
                        new_items = signals.get(key, [])
                        for item in new_items:
                            if item not in existing_items:
                                existing_items.append(item)
                        existing[key] = existing_items
                    
                    # Update meeting with merged signals
                    conn.execute(
                        "UPDATE meeting_summaries SET signals_json = ? WHERE id = ?",
                        (json.dumps(existing), meeting_id)
                    )
                    conn.commit()
                    
                    return JSONResponse({
                        "status": "ok",
                        "action": "merged",
                        "meeting_id": meeting_id,
                        "new_signals": total_extracted,
                        "signals": signals
                    })
            
            return JSONResponse({
                "status": "ok",
                "action": "extracted",
                "document_id": doc_id,
                "total_signals": total_extracted,
                "signals": signals
            })
            
        except json.JSONDecodeError:
            return JSONResponse({
                "error": "Failed to parse AI response",
                "raw_response": response
            }, status_code=500)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
