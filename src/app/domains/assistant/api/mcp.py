# src/app/domains/assistant/api/mcp.py
"""
MCP (Model Context Protocol) Tool Calling Routes

Provides API endpoints for MCP tool calls and signal search.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import json
import logging

from ....infrastructure.supabase_client import get_supabase_client
from ....mcp.registry import TOOL_REGISTRY
from ....mcp.schemas import MCPCall

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


class SignalSearchRequest(BaseModel):
    query: str
    signal_type: str = "all"
    limit: int = 50


@router.post("/tools/call")
def call_tool(payload: MCPCall):
    """Execute an MCP tool by name with given arguments."""
    tool = TOOL_REGISTRY.get(payload.name)

    if not tool:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown MCP tool: {payload.name}",
        )

    try:
        return tool(payload.args)
    except Exception as e:
        logger.error(f"MCP tool error: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/tools")
def list_tools():
    """List all available MCP tools."""
    return JSONResponse({
        "tools": list(TOOL_REGISTRY.keys()),
        "count": len(TOOL_REGISTRY),
    })


@router.post("/signals/search")
def search_signals(request: SignalSearchRequest):
    """
    Search signals across all meetings by keyword.
    Returns meetings with matching signals.
    """
    query_lower = request.query.lower()
    signal_type = request.signal_type
    
    supabase = get_supabase_client()
    if not supabase:
        return {"query": request.query, "signal_type": signal_type, "count": 0, "results": []}
    
    response = supabase.table("meetings").select(
        "id, meeting_name, meeting_date, signals"
    ).not_.is_("signals", "null").neq("signals", "{}").order(
        "meeting_date", desc=True, nullsfirst=False
    ).limit(request.limit).execute()
    meetings = response.data
    
    results = []
    
    signal_types_to_search = ["decisions", "action_items", "blockers", "risks", "ideas", "key_signals"]
    if signal_type != "all":
        signal_types_to_search = [signal_type]
    
    for meeting in meetings:
        if not meeting.get("signals_json"):
            continue
        
        try:
            signals = json.loads(meeting["signals_json"]) if isinstance(meeting["signals_json"], str) else meeting["signals_json"]
        except:
            continue
        
        matching_signals = []
        
        for stype in signal_types_to_search:
            signal_list = signals.get(stype, [])
            
            if isinstance(signal_list, str):
                if query_lower in signal_list.lower():
                    matching_signals.append({
                        "type": stype,
                        "text": signal_list
                    })
            elif isinstance(signal_list, list):
                for item in signal_list:
                    if isinstance(item, str) and query_lower in item.lower():
                        matching_signals.append({
                            "type": stype,
                            "text": item
                        })
                    elif isinstance(item, dict):
                        text = item.get("text", item.get("description", str(item)))
                        if query_lower in text.lower():
                            matching_signals.append({
                                "type": stype,
                                "text": text
                            })
        
        if matching_signals:
            results.append({
                "meeting_id": meeting["id"],
                "meeting_name": meeting["meeting_name"],
                "meeting_date": meeting["meeting_date"],
                "matching_signals": matching_signals
            })
    
    return {
        "query": request.query,
        "signal_type": signal_type,
        "count": len(results),
        "results": results
    }


__all__ = ["router"]
