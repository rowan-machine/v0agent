# src/app/mcp/server.py
"""
MCP Server for V0Agent

Standalone Model Context Protocol server that exposes V0Agent tools to AI agents.
Can run as a separate service for better isolation and scalability.

Usage:
    # Development
    python -m src.app.mcp.server
    
    # Docker
    docker build -f Dockerfile.mcp -t v0agent-mcp .
    docker run -p 8002:8002 v0agent-mcp
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

# Try fastmcp first, fall back to mcp
try:
    from fastmcp import FastMCP
    USING_FASTMCP = True
except ImportError:
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
        USING_FASTMCP = False
    except ImportError:
        raise ImportError("Please install fastmcp or mcp: pip install fastmcp mcp")

logger = logging.getLogger(__name__)

# Server configuration
MCP_SERVER_NAME = "v0agent-mcp"
MCP_SERVER_VERSION = "1.0.0"


# =============================================================================
# SERVICE LAYER ACCESS (Clean Architecture - DDD Compliant)
# =============================================================================

def _get_meetings_service():
    """Get meetings service module (lazy import)."""
    from ..services import meetings_supabase
    return meetings_supabase


def _get_tickets_service():
    """Get tickets service module (lazy import)."""
    from ..services import tickets_supabase
    return tickets_supabase


def _get_db_adapter():
    """Get database adapter for repositories (lazy import)."""
    from ..adapters.database.supabase import SupabaseDatabaseAdapter
    return SupabaseDatabaseAdapter()


def _get_dikw_repository():
    """Get DIKW repository (lazy import)."""
    from ..adapters.database.supabase import SupabaseDIKWRepository
    db = _get_db_adapter()
    return SupabaseDIKWRepository(db)


def _get_career_helper():
    """Get career supabase helper (lazy import)."""
    from ..api.career_supabase_helper import get_supabase_client
    return get_supabase_client()


# =============================================================================
# TOOL IMPLEMENTATIONS (Using Service Layer)
# =============================================================================

async def search_meetings(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search meetings by name or content."""
    meetings_svc = _get_meetings_service()
    
    meetings = meetings_svc.search_meetings(query, limit=limit)
    
    return {
        "meetings": meetings or [],
        "count": len(meetings or [])
    }


async def get_meeting(meeting_id: str) -> Dict[str, Any]:
    """Get a specific meeting by ID."""
    meetings_svc = _get_meetings_service()
    
    meeting = meetings_svc.get_meeting_by_id(meeting_id)
    
    if not meeting:
        return {"error": "Meeting not found"}
    
    return {"meeting": meeting}


async def get_recent_signals(limit: int = 20, signal_type: Optional[str] = None) -> Dict[str, Any]:
    """Get recent signals from meetings."""
    meetings_svc = _get_meetings_service()
    
    # Get recent meetings with signals (using service layer)
    meetings = meetings_svc.get_meetings_with_signals_in_range(days=30)
    
    signals = []
    for meeting in meetings or []:
        meeting_signals = meeting.get("signals") or {}
        if isinstance(meeting_signals, str):
            try:
                meeting_signals = json.loads(meeting_signals)
            except:
                continue
        
        for stype, items in meeting_signals.items():
            if signal_type and stype != signal_type:
                continue
            if isinstance(items, list):
                for item in items:
                    signals.append({
                        "meeting_id": meeting["id"],
                        "meeting_name": meeting["meeting_name"],
                        "meeting_date": meeting["meeting_date"],
                        "signal_type": stype,
                        "content": item
                    })
    
    return {
        "signals": signals[:limit],
        "count": len(signals)
    }


async def search_knowledge(query: str, level: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Search DIKW knowledge items."""
    dikw_repo = _get_dikw_repository()
    
    # Get filtered items from repository
    items = dikw_repo.get_items(level=level, status="active", limit=limit * 2)
    
    # Manual text filter since repository doesn't support text search
    filtered = []
    query_lower = query.lower()
    for item in items or []:
        content = (item.get("content", "") or "").lower()
        summary = (item.get("summary", "") or "").lower()
        tags = (item.get("tags", "") or "").lower()
        if query_lower in content or query_lower in summary or query_lower in tags:
            filtered.append(item)
            if len(filtered) >= limit:
                break
    
    return {
        "items": filtered,
        "count": len(filtered)
    }


async def get_dikw_pyramid() -> Dict[str, Any]:
    """Get the full DIKW pyramid structure."""
    dikw_repo = _get_dikw_repository()
    
    # Use repository's pyramid method
    pyramid_raw = dikw_repo.get_pyramid()
    
    # Format for API response
    pyramid = {
        "data": [],
        "information": [],
        "knowledge": [],
        "wisdom": []
    }
    
    for level, items in pyramid_raw.items():
        if level in pyramid:
            for item in items:
                pyramid[level].append({
                    "id": item["id"],
                    "content": item.get("content", "")[:200],
                    "summary": item.get("summary", ""),
                    "tags": item.get("tags", ""),
                    "confidence": item.get("confidence", 70)
                })
    
    return {
        "pyramid": pyramid,
        "counts": {k: len(v) for k, v in pyramid.items()}
    }


async def get_tickets(status: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """Get tickets with optional status filter."""
    tickets_svc = _get_tickets_service()
    
    if status:
        tickets = tickets_svc.get_tickets_by_status(status, limit=limit)
    else:
        tickets = tickets_svc.get_all_tickets(limit=limit)
    
    return {
        "tickets": tickets or [],
        "count": len(tickets or [])
    }


async def create_ticket(
    title: str,
    description: Optional[str] = None,
    status: str = "backlog",
    priority: str = "medium"
) -> Dict[str, Any]:
    """Create a new ticket."""
    tickets_svc = _get_tickets_service()
    
    import uuid
    ticket_id = f"TKT-{str(uuid.uuid4())[:8].upper()}"
    
    ticket_data = {
        "ticket_id": ticket_id,
        "title": title,
        "description": description,
        "status": status,
        "priority": priority
    }
    
    result = tickets_svc.create_ticket(ticket_data)
    
    return {
        "status": "ok" if result else "error",
        "ticket": result
    }


async def get_career_profile() -> Dict[str, Any]:
    """Get the user's career profile."""
    # Use career helper (until career repository is extracted)
    client = _get_career_helper()
    
    if not client:
        return {"profile": None, "message": "Career service unavailable"}
    
    result = client.table("career_profiles").select("*").eq("id", 1).execute()
    
    if not result.data:
        return {"profile": None, "message": "No career profile found"}
    
    return {"profile": result.data[0]}


async def get_career_suggestions(status: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Get career suggestions."""
    # Use career helper (until career repository is extracted)
    client = _get_career_helper()
    
    if not client:
        return {"suggestions": [], "message": "Career service unavailable"}
    
    q = client.table("career_suggestions").select("*")
    
    if status:
        q = q.eq("status", status)
    else:
        q = q.in_("status", ["suggested", "accepted"])
    
    result = q.order("created_at", desc=True).limit(limit).execute()
    
    return {
        "suggestions": result.data or [],
        "count": len(result.data or [])
    }


async def semantic_search(query: str, content_type: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """Perform semantic search across all content."""
    try:
        from ..memory.embed import embed_text
        from ..memory.vector_store import search_similar
        
        # Generate query embedding
        query_vector = embed_text(query)
        
        # Search for similar content
        results = search_similar(
            query_vector,
            content_type=content_type,
            top_k=limit
        )
        
        return {
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return {"error": str(e), "results": []}


async def ask_arjuna(question: str, context: Optional[str] = None) -> Dict[str, Any]:
    """Ask Arjuna AI assistant a question."""
    try:
        from ..chat.turn import run_turn
        
        messages = []
        if context:
            messages.append({"role": "system", "content": f"Context: {context}"})
        messages.append({"role": "user", "content": question})
        
        response = await run_turn(messages)
        
        return {
            "answer": response.get("content", ""),
            "status": "ok"
        }
    except Exception as e:
        logger.error(f"Arjuna query failed: {e}")
        return {"error": str(e)}


# =============================================================================
# SERVER SETUP
# =============================================================================

if USING_FASTMCP:
    # FastMCP provides a simpler API
    mcp = FastMCP(MCP_SERVER_NAME)
    
    @mcp.tool()
    async def tool_search_meetings(query: str, limit: int = 10) -> str:
        """Search meetings by name or content. Returns matching meetings."""
        result = await search_meetings(query, limit)
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_get_meeting(meeting_id: str) -> str:
        """Get a specific meeting by ID. Returns meeting details with signals."""
        result = await get_meeting(meeting_id)
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_get_recent_signals(limit: int = 20, signal_type: str = None) -> str:
        """Get recent signals extracted from meetings. Types: decision, action_item, blocker, risk, idea."""
        result = await get_recent_signals(limit, signal_type)
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_search_knowledge(query: str, level: str = None, limit: int = 10) -> str:
        """Search DIKW knowledge items. Levels: data, information, knowledge, wisdom."""
        result = await search_knowledge(query, level, limit)
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_get_dikw_pyramid() -> str:
        """Get the full DIKW knowledge pyramid structure with items organized by level."""
        result = await get_dikw_pyramid()
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_get_tickets(status: str = None, limit: int = 20) -> str:
        """Get tickets. Status: backlog, ready, in_progress, blocked, done."""
        result = await get_tickets(status, limit)
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_create_ticket(title: str, description: str = None, status: str = "backlog", priority: str = "medium") -> str:
        """Create a new ticket. Priority: low, medium, high, critical."""
        result = await create_ticket(title, description, status, priority)
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_get_career_profile() -> str:
        """Get the user's career profile including role, skills, and goals."""
        result = await get_career_profile()
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_get_career_suggestions(status: str = None, limit: int = 10) -> str:
        """Get career development suggestions. Status: suggested, accepted, dismissed, completed."""
        result = await get_career_suggestions(status, limit)
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_semantic_search(query: str, content_type: str = None, limit: int = 5) -> str:
        """Semantic search across all content using embeddings. Content types: meeting, document, ticket."""
        result = await semantic_search(query, content_type, limit)
        return json.dumps(result, indent=2, default=str)
    
    @mcp.tool()
    async def tool_ask_arjuna(question: str, context: str = None) -> str:
        """Ask Arjuna AI assistant a question about meetings, tasks, or career."""
        result = await ask_arjuna(question, context)
        return json.dumps(result, indent=2, default=str)


def main():
    """Run the MCP server."""
    if USING_FASTMCP:
        mcp.run()
    else:
        # Standard MCP server
        import asyncio
        
        server = Server(MCP_SERVER_NAME)
        
        @server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="search_meetings",
                    description="Search meetings by name or content",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_meeting",
                    description="Get a specific meeting by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "meeting_id": {"type": "string"}
                        },
                        "required": ["meeting_id"]
                    }
                ),
                Tool(
                    name="get_recent_signals",
                    description="Get recent signals from meetings",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "default": 20},
                            "signal_type": {"type": "string"}
                        }
                    }
                ),
                Tool(
                    name="search_knowledge",
                    description="Search DIKW knowledge items",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "level": {"type": "string"},
                            "limit": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_tickets",
                    description="Get tickets with optional status filter",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "limit": {"type": "integer", "default": 20}
                        }
                    }
                ),
                Tool(
                    name="semantic_search",
                    description="Semantic search across content",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "content_type": {"type": "string"},
                            "limit": {"type": "integer", "default": 5}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="ask_arjuna",
                    description="Ask Arjuna AI assistant",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "context": {"type": "string"}
                        },
                        "required": ["question"]
                    }
                )
            ]
        
        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[TextContent]:
            handlers = {
                "search_meetings": search_meetings,
                "get_meeting": get_meeting,
                "get_recent_signals": get_recent_signals,
                "search_knowledge": search_knowledge,
                "get_tickets": get_tickets,
                "semantic_search": semantic_search,
                "ask_arjuna": ask_arjuna,
            }
            
            if name not in handlers:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
            result = await handlers[name](**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
        async def run():
            async with stdio_server() as streams:
                await server.run(
                    streams[0],
                    streams[1],
                    server.create_initialization_options()
                )
        
        asyncio.run(run())


if __name__ == "__main__":
    main()
