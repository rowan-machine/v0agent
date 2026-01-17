from fastapi import APIRouter, HTTPException
from ..mcp.registry import TOOL_REGISTRY
from ..mcp.schemas import MCPCall

router = APIRouter()


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
