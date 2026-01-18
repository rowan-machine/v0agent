from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
from ..mcp.registry import TOOL_REGISTRY
from ..mcp.schemas import MCPCall
from ..db import connect

router = APIRouter()


class SignalSearchRequest(BaseModel):
    query: str
    signal_type: str = "all"
    limit: int = 50


@router.post("/mcp/call")
def call_tool(payload: MCPCall):
    tool = TOOL_REGISTRY.get(payload.name)

    if not tool:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown MCP tool: {payload.name}",
        )

    try:
        return tool(payload.args)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.post("/api/signals/search")
def search_signals(request: SignalSearchRequest):
    """
    Search signals across all meetings by keyword.
    Returns meetings with matching signals.
    """
    query_lower = request.query.lower()
    signal_type = request.signal_type
    
    with connect() as conn:
        meetings = conn.execute(
            """
            SELECT id, meeting_name, meeting_date, signals_json
            FROM meeting_summaries
            WHERE signals_json IS NOT NULL AND signals_json != '{}'
            ORDER BY COALESCE(meeting_date, created_at) DESC
            LIMIT ?
            """,
            (request.limit,)
        ).fetchall()
    
    results = []
    
    signal_types_to_search = ["decisions", "action_items", "blockers", "risks", "ideas", "key_signals"]
    if signal_type != "all":
        signal_types_to_search = [signal_type]
    
    for meeting in meetings:
        if not meeting["signals_json"]:
            continue
        
        try:
            signals = json.loads(meeting["signals_json"])
        except:
            continue
        
        matching_signals = []
        
        for stype in signal_types_to_search:
            signal_list = signals.get(stype, [])
            
            # Handle both list and string formats
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
                        # Handle dict format
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
