"""
MCP Tool Registry - Central registry for all available tools/commands.

This module provides:
1. Tool registration and discovery
2. Hierarchical tool organization by category
3. MCP server management for optional integrations
4. Subcommand routing for complex tools
5. Tool access control (future)

Architecture:
- Tools are organized by category (data_access, agent_comms, external_tools, etc.)
- Each tool has metadata: name, description, input/output schema, retry policy
- Tools can have subcommands for fine-grained control
- MCP servers are optional integrations registered in config

Example:
    registry = get_tool_registry()
    
    # Get a tool
    tool = registry.get_tool("query_data")
    
    # Get tools by category
    data_tools = registry.get_tools_by_category(ToolCategory.DATA_QUERY)
    
    # List available subcommands for a tool
    subcommands = registry.get_tool_subcommands("query_data")
    # Returns: ["list", "search", "filter", "aggregate"]
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Callable, Any, Optional

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Hierarchical tool categories for organization."""
    # Data access and queries
    DATA_ACCESS = "data_access"
    DATA_QUERY = "data_access.query"
    DATA_WRITE = "data_access.write"
    DATA_SEARCH = "data_access.search"
    
    # Agent-to-agent communication
    AGENT_COMMS = "agent_comms"
    AGENT_QUERY = "agent_comms.query"
    AGENT_TASK = "agent_comms.task"
    
    # External tools (MCP servers, APIs)
    EXTERNAL_TOOLS = "external_tools"
    EXTERNAL_MCP = "external_tools.mcp"
    EXTERNAL_API = "external_tools.api"
    
    # Analysis and intelligence
    ANALYSIS = "analysis"
    ANALYSIS_SEMANTIC = "analysis.semantic"
    ANALYSIS_GRAPH = "analysis.graph"
    
    # System utilities
    SYSTEM = "system"
    SYSTEM_CONFIG = "system.config"
    SYSTEM_MONITORING = "system.monitoring"


@dataclass
class Tool:
    """Tool definition with metadata and configuration.
    
    Attributes:
        name: Unique tool name
        category: ToolCategory for organization
        description: Human-readable description
        func: Callable that implements the tool
        input_schema: JSON schema for input validation
        output_schema: JSON schema for output
        requires_auth: Whether tool requires authentication
        enabled: Whether tool is currently available
        mcp_server: MCP server name if external tool
        retry_policy: Dict with retry configuration
        rate_limit: Max calls per minute (None = unlimited)
        subcommands: List of available subcommands
        parent_tool: Parent tool name if nested
    """
    name: str
    category: ToolCategory
    description: str
    func: Callable = None  # Implementation stub
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    requires_auth: bool = False
    enabled: bool = True
    mcp_server: Optional[str] = None
    retry_policy: Optional[Dict] = None
    rate_limit: Optional[int] = None
    subcommands: List[str] = field(default_factory=list)
    parent_tool: Optional[str] = None
    
    def to_openai_function(self) -> dict:
        """Convert to OpenAI function schema for function calling.
        
        Returns:
            Dict compatible with OpenAI function calling API
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }
    
    def to_dict(self) -> dict:
        """Serialize tool to dictionary.
        
        Returns:
            Dictionary representation of tool
        """
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "enabled": self.enabled,
            "requires_auth": self.requires_auth,
            "mcp_server": self.mcp_server,
            "subcommands": self.subcommands,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class ToolRegistry:
    """Central registry for all available tools and MCP servers.
    
    This class manages:
    - Tool registration and lookup
    - Category-based tool filtering
    - MCP server integration
    - Tool availability and enable/disable
    
    Usage:
        registry = ToolRegistry()
        
        # Register a tool
        tool = Tool(name="query_data", ...)
        registry.register_tool(tool)
        
        # Get a tool
        tool = registry.get_tool("query_data")
        
        # Get tools by category
        query_tools = registry.get_tools_by_category(ToolCategory.DATA_QUERY)
        
        # List MCP servers
        servers = registry.list_mcp_servers()
    """
    
    def __init__(self):
        """Initialize empty tool registry."""
        self.tools: Dict[str, Tool] = {}
        self.mcp_servers: Dict[str, Dict] = {}
        logger.info("ToolRegistry initialized")
    
    def register_tool(self, tool: Tool) -> None:
        """Register a tool in the registry.
        
        Args:
            tool: Tool object to register
            
        Raises:
            ValueError: If tool with same name already registered
        """
        if tool.name in self.tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")
        
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} ({tool.category.value})")
    
    def register_mcp_server(self, name: str, config: Dict) -> None:
        """Register an MCP server for optional integration.
        
        Args:
            name: MCP server name (e.g., "notion", "github", "slack")
            config: Configuration dict with enabled, endpoint, credentials
        """
        self.mcp_servers[name] = {
            "name": name,
            "enabled": config.get("enabled", False),
            "endpoint": config.get("endpoint"),
            "credentials": config.get("credentials"),
            "tools": config.get("tools", []),
        }
        logger.info(
            f"Registered MCP server: {name} (enabled={config.get('enabled', False)})"
        )
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool object or None if not found
        """
        return self.tools.get(name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[Tool]:
        """Get all tools in a specific category.
        
        Args:
            category: ToolCategory to filter by
            
        Returns:
            List of Tool objects in that category
        """
        return [t for t in self.tools.values() if t.category == category and t.enabled]
    
    def get_tools_for_agent(self, agent_name: str) -> List[Tool]:
        """Get available tools for a specific agent.
        
        Future: Implement role-based access control
        
        Args:
            agent_name: Name of agent
            
        Returns:
            List of tools available to agent
        """
        # For now, return all enabled tools
        # Future: Check agent permissions
        return [t for t in self.tools.values() if t.enabled]
    
    def get_tool_subcommands(self, tool_name: str) -> List[str]:
        """Get available subcommands for a tool.
        
        Args:
            tool_name: Tool name
            
        Returns:
            List of subcommand names, or empty list if tool not found
        """
        tool = self.get_tool(tool_name)
        return tool.subcommands if tool else []
    
    def list_mcp_servers(self, enabled_only: bool = False) -> List[str]:
        """List registered MCP servers.
        
        Args:
            enabled_only: Only return enabled servers
            
        Returns:
            List of MCP server names
        """
        if enabled_only:
            return [
                name for name, config in self.mcp_servers.items()
                if config["enabled"]
            ]
        return list(self.mcp_servers.keys())
    
    def get_mcp_server(self, name: str) -> Optional[Dict]:
        """Get MCP server configuration.
        
        Args:
            name: MCP server name
            
        Returns:
            Server configuration dict or None if not found
        """
        return self.mcp_servers.get(name)
    
    def enable_tool(self, tool_name: str) -> None:
        """Enable a tool.
        
        Args:
            tool_name: Tool name
        """
        if tool_name in self.tools:
            self.tools[tool_name].enabled = True
            logger.info(f"Tool enabled: {tool_name}")
    
    def disable_tool(self, tool_name: str) -> None:
        """Disable a tool.
        
        Args:
            tool_name: Tool name
        """
        if tool_name in self.tools:
            self.tools[tool_name].enabled = False
            logger.info(f"Tool disabled: {tool_name}")
    
    def list_all_tools(self) -> List[str]:
        """List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self.tools.keys())
    
    def list_enabled_tools(self) -> List[str]:
        """List all enabled tool names.
        
        Returns:
            List of enabled tool names
        """
        return [name for name, tool in self.tools.items() if tool.enabled]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics.
        
        Returns:
            Dict with tool counts and stats
        """
        total_tools = len(self.tools)
        enabled_tools = len([t for t in self.tools.values() if t.enabled])
        
        categories = {}
        for tool in self.tools.values():
            cat = tool.category.value
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1
        
        return {
            "total_tools": total_tools,
            "enabled_tools": enabled_tools,
            "disabled_tools": total_tools - enabled_tools,
            "categories": categories,
            "mcp_servers": len(self.mcp_servers),
            "mcp_servers_enabled": len(self.list_mcp_servers(enabled_only=True)),
        }


class BuiltInTools:
    """Factory for built-in tool definitions.
    
    These are stubs that define the interface for built-in tools.
    Actual implementation happens in the routers/handlers.
    """
    
    @staticmethod
    def create_data_query_tool() -> Tool:
        """Create data query tool for accessing meetings, documents, etc.
        
        Subcommands: list, search, filter, aggregate
        """
        return Tool(
            name="query_data",
            category=ToolCategory.DATA_QUERY,
            description="Execute structured queries against meetings, documents, tickets, and signals",
            input_schema={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["meetings", "documents", "signals", "tickets"],
                        "description": "Type of data to query"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria (dynamic based on query_type)"
                    },
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["query_type"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {"type": "array"},
                    "count": {"type": "integer"},
                    "query_time_ms": {"type": "number"},
                }
            },
            subcommands=["list", "search", "filter", "aggregate"],
        )
    
    @staticmethod
    def create_semantic_search_tool() -> Tool:
        """Create semantic search tool using embeddings.
        
        Subcommands: search, cluster, detect_duplicates
        """
        return Tool(
            name="semantic_search",
            category=ToolCategory.ANALYSIS_SEMANTIC,
            description="Search for semantically similar content using embeddings",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "entity_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["meetings", "documents", "signals", "tickets", "dikw"]
                        },
                    },
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                                "similarity": {"type": "number"},
                                "source": {"type": "string"},
                            }
                        }
                    }
                }
            },
            subcommands=["search", "cluster", "detect_duplicates"],
        )
    
    @staticmethod
    def create_agent_query_tool() -> Tool:
        """Create tool for agent-to-agent communication.
        
        Subcommands: ask, get_status, list_agents
        """
        return Tool(
            name="query_agent",
            category=ToolCategory.AGENT_QUERY,
            description="Send a query to another agent and wait for response",
            input_schema={
                "type": "object",
                "properties": {
                    "target_agent": {
                        "type": "string",
                        "enum": ["arjuna", "career_coach", "meeting_analyzer", "dikw_synthesizer"],
                    },
                    "query_text": {"type": "string"},
                    "context": {"type": "object"},
                },
                "required": ["target_agent", "query_text"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "response": {"type": "string"},
                    "confidence": {"type": "number"},
                    "sources": {"type": "array"},
                }
            },
            subcommands=["ask", "get_status", "list_agents"],
        )
    
    @staticmethod
    def create_mcp_tool_stub(mcp_server: str, tool_name: str) -> Tool:
        """Create stub for external MCP tool (not yet implemented).
        
        Args:
            mcp_server: MCP server name (e.g., "notion", "github")
            tool_name: Tool name from MCP server
            
        Returns:
            Tool stub with MCP server reference
        """
        return Tool(
            name=f"mcp_{mcp_server}_{tool_name}",
            category=ToolCategory.EXTERNAL_MCP,
            description=f"MCP tool from {mcp_server} server: {tool_name}",
            input_schema={"type": "object"},  # Stub - actual from MCP
            output_schema={"type": "object"},  # Stub
            mcp_server=mcp_server,
            enabled=False,  # Disabled until server is configured
            subcommands=["execute"],
        )


# Global registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get global tool registry (singleton).
    
    Initializes with built-in tools on first call.
    
    Returns:
        ToolRegistry instance
    """
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        # Register built-in tools
        _tool_registry.register_tool(BuiltInTools.create_data_query_tool())
        _tool_registry.register_tool(BuiltInTools.create_semantic_search_tool())
        _tool_registry.register_tool(BuiltInTools.create_agent_query_tool())
        logger.info("Built-in tools registered")
    return _tool_registry


def initialize_tool_registry() -> ToolRegistry:
    """Initialize tool registry with built-in tools.
    
    Returns:
        ToolRegistry instance
    """
    return get_tool_registry()
