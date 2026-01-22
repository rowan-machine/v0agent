# Multi-Agent System & MCP Integration Architecture

**Status:** Planning & Design Document  
**Purpose:** Define groundwork for agent communication, MCP tool integration, and system extensibility

---

## 1. Multi-Agent System Architecture

### Current State Analysis
- **Agents identified:** Arjuna (assistant), CareerCoach, MeetingAnalyzer, DIKWSynthesizer
- **Communication:** Currently via shared database (meetings, signals, tickets)
- **No direct agent-to-agent messaging** - all communication is implicit via state changes
- **LLM calls:** Each agent independently calls OpenAI (no coordination)
- **Tool access:** Limited to database reads/writes

### Proposed Architecture

#### 1.1 Agent Communication Bus (Message Queue)

```python
# src/app/services/agent_bus.py (NEW)

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
import json
from ..db import connect

class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class AgentMessage:
    """Message passed between agents."""
    id: str
    source_agent: str  # "arjuna", "career_coach", etc.
    target_agent: str | None  # None = broadcast
    message_type: str  # "query", "signal", "task", "result"
    content: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = None
    processed_at: Optional[datetime] = None
    status: str = "pending"  # pending, processing, completed, failed, archived
    retry_count: int = 0
    max_retries: int = 3
    ttl_seconds: int = 3600  # 1 hour default
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "message_type": self.message_type,
            "content": json.dumps(self.content),
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "status": self.status,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "ttl_seconds": self.ttl_seconds,
        }

class AgentBus:
    """Central message bus for agent communication."""
    
    def __init__(self, db_path: str = "agent.db"):
        self.db_path = db_path
        self._initialize_tables()
    
    def _initialize_tables(self):
        """Create message queue table if not exists."""
        with connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    target_agent TEXT,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 2,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    ttl_seconds INTEGER DEFAULT 3600,
                    error_message TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_messages_status 
                ON agent_messages(status, priority DESC, created_at ASC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_messages_target 
                ON agent_messages(target_agent, status)
            """)
            conn.commit()
    
    def send(self, msg: AgentMessage) -> str:
        """Send a message from one agent to another (or broadcast)."""
        msg.created_at = msg.created_at or datetime.now()
        
        with connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO agent_messages (
                    id, source_agent, target_agent, message_type, content,
                    priority, created_at, status, retry_count, max_retries, ttl_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tuple(msg.to_dict().values())[:-1])  # Exclude error_message
            conn.commit()
        
        logger.info(f"Message sent: {msg.source_agent} → {msg.target_agent or 'broadcast'}: {msg.message_type}")
        return msg.id
    
    def receive(self, agent_name: str, limit: int = 10) -> List[AgentMessage]:
        """Get pending messages for an agent."""
        with connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT * FROM agent_messages
                WHERE (target_agent = ? OR target_agent IS NULL)
                AND status = 'pending'
                AND ttl_seconds > 0
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (agent_name, limit)).fetchall()
        
        messages = []
        for row in rows:
            messages.append(AgentMessage(
                id=row["id"],
                source_agent=row["source_agent"],
                target_agent=row["target_agent"],
                message_type=row["message_type"],
                content=json.loads(row["content"]),
                priority=MessagePriority(row["priority"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                processed_at=datetime.fromisoformat(row["processed_at"]) if row["processed_at"] else None,
                status=row["status"],
                retry_count=row["retry_count"],
                max_retries=row["max_retries"],
                ttl_seconds=row["ttl_seconds"],
            ))
        
        return messages
    
    def mark_processing(self, message_id: str):
        """Mark a message as being processed."""
        with connect(self.db_path) as conn:
            conn.execute("""
                UPDATE agent_messages
                SET status = 'processing'
                WHERE id = ?
            """, (message_id,))
            conn.commit()
    
    def mark_completed(self, message_id: str, result: Optional[Dict] = None):
        """Mark a message as completed."""
        with connect(self.db_path) as conn:
            conn.execute("""
                UPDATE agent_messages
                SET status = 'completed', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (message_id,))
            conn.commit()
        
        logger.info(f"Message completed: {message_id}")
    
    def mark_failed(self, message_id: str, error: str):
        """Mark a message as failed."""
        with connect(self.db_path) as conn:
            msg = conn.execute("SELECT * FROM agent_messages WHERE id = ?", (message_id,)).fetchone()
            
            if msg["retry_count"] < msg["max_retries"]:
                # Retry: reset to pending
                conn.execute("""
                    UPDATE agent_messages
                    SET status = 'pending', retry_count = retry_count + 1, error_message = ?
                    WHERE id = ?
                """, (error, message_id))
                logger.warning(f"Message retry: {message_id} (attempt {msg['retry_count'] + 1})")
            else:
                # Max retries exceeded
                conn.execute("""
                    UPDATE agent_messages
                    SET status = 'failed', error_message = ?
                    WHERE id = ?
                """, (error, message_id))
                logger.error(f"Message failed after {msg['max_retries']} retries: {message_id}")
            
            conn.commit()

# Global bus instance
_bus: Optional[AgentBus] = None

def get_agent_bus() -> AgentBus:
    """Get global agent bus instance."""
    global _bus
    if _bus is None:
        _bus = AgentBus()
    return _bus
```

#### 1.2 Agent Lifecycle & Registry

```python
# src/app/services/agent_lifecycle.py (NEW)

from abc import ABC, abstractmethod
from typing import Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class AgentState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING = "waiting"
    ERROR = "error"
    TERMINATED = "terminated"

class AgentLifecycle(ABC):
    """Base class for agent lifecycle management."""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.state = AgentState.IDLE
        self.metrics = {
            "messages_processed": 0,
            "errors": 0,
            "last_activity": None,
            "uptime_seconds": 0,
        }
    
    @abstractmethod
    async def process_message(self, msg):
        """Process an incoming message."""
        pass
    
    @abstractmethod
    async def startup(self):
        """Initialize agent resources."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Clean up agent resources."""
        pass
    
    def set_state(self, state: AgentState):
        """Update agent state."""
        self.state = state
        logger.info(f"Agent {self.name} state: {state.value}")
    
    def record_error(self, error: Exception):
        """Record an error."""
        self.metrics["errors"] += 1
        logger.error(f"Agent {self.name} error: {error}")

class AgentRegistry:
    """Registry of all available agents."""
    
    def __init__(self):
        self.agents: Dict[str, AgentLifecycle] = {}
        self.dependencies: Dict[str, list[str]] = {}  # agent → [dependencies]
    
    def register(self, agent: AgentLifecycle, dependencies: list[str] = None):
        """Register an agent."""
        self.agents[agent.name] = agent
        self.dependencies[agent.name] = dependencies or []
        logger.info(f"Registered agent: {agent.name}")
    
    def get(self, name: str) -> Optional[AgentLifecycle]:
        """Get an agent by name."""
        return self.agents.get(name)
    
    def list_agents(self) -> list[str]:
        """List all registered agents."""
        return list(self.agents.keys())
    
    async def startup_all(self):
        """Start all agents in dependency order."""
        started = set()
        
        while len(started) < len(self.agents):
            for agent_name, deps in self.dependencies.items():
                if agent_name in started:
                    continue
                
                # Check if dependencies are satisfied
                if all(dep in started for dep in deps):
                    agent = self.agents[agent_name]
                    await agent.startup()
                    started.add(agent_name)
                    logger.info(f"Started agent: {agent_name}")
    
    async def shutdown_all(self):
        """Shutdown all agents."""
        for agent in self.agents.values():
            await agent.shutdown()
            logger.info(f"Shutdown agent: {agent.name}")

# Global registry
_registry: Optional[AgentRegistry] = None

def get_agent_registry() -> AgentRegistry:
    """Get global agent registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
```

---

## 2. MCP (Model Context Protocol) Integration Points

### 2.1 Tool Registry & Hierarchical Structure

```python
# src/app/mcp/tool_registry.py (NEW/ENHANCED)

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Callable, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

class ToolCategory(Enum):
    """Hierarchical tool categories."""
    # Core data access
    DATA_ACCESS = "data_access"
    DATA_QUERY = "data_access.query"
    DATA_WRITE = "data_access.write"
    DATA_SEARCH = "data_access.search"
    
    # Agent coordination
    AGENT_COMMS = "agent_comms"
    AGENT_QUERY = "agent_comms.query"
    AGENT_TASK = "agent_comms.task"
    
    # External tools (MCP, APIs)
    EXTERNAL_TOOLS = "external_tools"
    EXTERNAL_MCP = "external_tools.mcp"
    EXTERNAL_API = "external_tools.api"
    
    # Analysis & intelligence
    ANALYSIS = "analysis"
    ANALYSIS_SEMANTIC = "analysis.semantic"
    ANALYSIS_GRAPH = "analysis.graph"
    
    # System utilities
    SYSTEM = "system"
    SYSTEM_CONFIG = "system.config"
    SYSTEM_MONITORING = "system.monitoring"

@dataclass
class Tool:
    """Tool definition with metadata."""
    name: str
    category: ToolCategory
    description: str
    func: Callable
    input_schema: Dict[str, Any]  # JSON schema
    output_schema: Dict[str, Any]  # JSON schema
    requires_auth: bool = False
    enabled: bool = True
    mcp_server: Optional[str] = None  # e.g., "notion", "github", "slack"
    retry_policy: Optional[Dict] = None
    rate_limit: Optional[int] = None  # Calls per minute
    
    # Hierarchy hints
    subcommands: List[str] = None  # e.g., ["list", "get", "create", "update"]
    parent_tool: Optional[str] = None
    
    def to_openai_function(self) -> dict:
        """Convert to OpenAI function schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }

class ToolRegistry:
    """Central registry for all available tools."""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.mcp_servers: Dict[str, Dict] = {}  # name → connection info
    
    def register_tool(self, tool: Tool):
        """Register a tool."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} ({tool.category.value})")
    
    def register_mcp_server(self, name: str, config: Dict):
        """Register an MCP server for optional integration."""
        self.mcp_servers[name] = {
            "name": name,
            "enabled": config.get("enabled", False),
            "endpoint": config.get("endpoint"),
            "credentials": config.get("credentials"),  # Can be secrets
            "tools": [],
        }
        logger.info(f"Registered MCP server: {name} (enabled={config.get('enabled', False)})")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name."""
        return self.tools.get(name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[Tool]:
        """Get all tools in a category."""
        return [t for t in self.tools.values() if t.category == category]
    
    def get_tools_for_agent(self, agent_name: str) -> List[Tool]:
        """Get available tools for an agent (by privilege level)."""
        # Future: Implement role-based access control
        return [t for t in self.tools.values() if t.enabled]
    
    def list_mcp_servers(self, enabled_only: bool = False) -> List[str]:
        """List registered MCP servers."""
        servers = self.mcp_servers.keys()
        if enabled_only:
            return [s for s in servers if self.mcp_servers[s]["enabled"]]
        return list(servers)
    
    def get_mcp_server(self, name: str) -> Optional[Dict]:
        """Get MCP server configuration."""
        return self.mcp_servers.get(name)

# Example stub definitions
class BuiltInTools:
    """Built-in tool stubs for core functionality."""
    
    @staticmethod
    def create_data_query_tool() -> Tool:
        """Query tool: flexible database queries."""
        return Tool(
            name="query_data",
            category=ToolCategory.DATA_QUERY,
            description="Execute structured queries against meetings, documents, tickets",
            func=lambda q: None,  # Stub
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
        """Semantic search: query by meaning, not keywords."""
        return Tool(
            name="semantic_search",
            category=ToolCategory.ANALYSIS_SEMANTIC,
            description="Search for semantically similar content using embeddings",
            func=lambda q, top_k=5: None,  # Stub
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "entity_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["meetings", "documents", "signals", "tickets", "dikw"]},
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
            subcommands=["search", "similar"],
        )
    
    @staticmethod
    def create_agent_query_tool() -> Tool:
        """Query tool: ask another agent for information."""
        return Tool(
            name="query_agent",
            category=ToolCategory.AGENT_QUERY,
            description="Send a query to another agent and wait for response",
            func=lambda agent, query: None,  # Stub
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
            subcommands=["ask", "get_status"],
        )
    
    @staticmethod
    def create_mcp_tool_stub(mcp_server: str, tool_name: str) -> Tool:
        """Create stub for external MCP tool."""
        return Tool(
            name=f"mcp_{mcp_server}_{tool_name}",
            category=ToolCategory.EXTERNAL_MCP,
            description=f"MCP tool from {mcp_server} server",
            func=lambda: None,  # Stub - actual implementation in MCP server
            input_schema={"type": "object"},  # Stub - schema from MCP
            output_schema={"type": "object"},  # Stub
            mcp_server=mcp_server,
            enabled=False,  # Disabled until server is configured
            subcommands=["execute"],
        )

# Global registry
_tool_registry: Optional[ToolRegistry] = None

def get_tool_registry() -> ToolRegistry:
    """Get global tool registry."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        # Register built-in tools
        _tool_registry.register_tool(BuiltInTools.create_data_query_tool())
        _tool_registry.register_tool(BuiltInTools.create_semantic_search_tool())
        _tool_registry.register_tool(BuiltInTools.create_agent_query_tool())
    return _tool_registry
```

### 2.2 MCP Server Integration (Stubs)

```python
# src/app/mcp/server_manager.py (NEW)

from typing import Dict, Optional, List
import logging
import asyncio

logger = logging.getLogger(__name__)

class MCPServerManager:
    """Manage optional MCP server integrations."""
    
    def __init__(self):
        self.active_servers: Dict[str, 'MCPServer'] = {}
    
    async def register_server(self, name: str, server_class: type, config: Dict):
        """Register and initialize an MCP server."""
        try:
            server = server_class(name, config)
            await server.connect()
            self.active_servers[name] = server
            logger.info(f"MCP server registered: {name}")
        except Exception as e:
            logger.error(f"Failed to register MCP server {name}: {e}")
    
    async def get_server_tools(self, server_name: str) -> List[Dict]:
        """Get available tools from an MCP server."""
        if server_name not in self.active_servers:
            return []
        
        server = self.active_servers[server_name]
        return await server.list_tools()
    
    async def execute_server_tool(self, server_name: str, tool_name: str, args: Dict):
        """Execute a tool from an MCP server."""
        if server_name not in self.active_servers:
            raise ValueError(f"MCP server not active: {server_name}")
        
        server = self.active_servers[server_name]
        return await server.call_tool(tool_name, args)
    
    async def shutdown_all(self):
        """Shutdown all MCP servers."""
        for server in self.active_servers.values():
            await server.disconnect()
        self.active_servers.clear()

class MCPServer:
    """Base class for MCP server integrations (stub)."""
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
    
    async def connect(self):
        """Connect to MCP server."""
        pass  # Stub
    
    async def disconnect(self):
        """Disconnect from MCP server."""
        pass  # Stub
    
    async def list_tools(self) -> List[Dict]:
        """List available tools from this server."""
        return []  # Stub
    
    async def call_tool(self, tool_name: str, args: Dict):
        """Execute a tool on this server."""
        pass  # Stub

# Stub implementations for common services
class NotionMCPServer(MCPServer):
    """Notion MCP server stub."""
    
    async def list_tools(self) -> List[Dict]:
        return [
            {"name": "list_pages", "description": "List Notion pages"},
            {"name": "get_page", "description": "Get a specific page"},
            {"name": "create_page", "description": "Create a new page"},
        ]

class GitHubMCPServer(MCPServer):
    """GitHub MCP server stub."""
    
    async def list_tools(self) -> List[Dict]:
        return [
            {"name": "list_issues", "description": "List GitHub issues"},
            {"name": "create_issue", "description": "Create a GitHub issue"},
            {"name": "get_repo_info", "description": "Get repository information"},
        ]

class SlackMCPServer(MCPServer):
    """Slack MCP server stub."""
    
    async def list_tools(self) -> List[Dict]:
        return [
            {"name": "send_message", "description": "Send a Slack message"},
            {"name": "list_channels", "description": "List Slack channels"},
            {"name": "get_user_info", "description": "Get user information"},
        ]

# Global manager
_mcp_manager: Optional[MCPServerManager] = None

def get_mcp_manager() -> MCPServerManager:
    """Get global MCP server manager."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPServerManager()
    return _mcp_manager
```

---

## 3. Tool Access Hierarchy & Subcommand Structure

### 3.1 Hierarchical Tool Organization

```
Tools (Root)
├── Data Access
│   ├── Query (subcommands: list, search, filter, aggregate)
│   ├── Write (subcommands: create, update, delete)
│   └── Search (subcommands: full_text, semantic, hybrid)
├── Agent Communications
│   ├── Query (subcommands: ask, get_status, list_agents)
│   └── Task (subcommands: submit, check_status, cancel)
├── External Tools
│   ├── MCP (Notion, GitHub, Slack, etc.)
│   └── APIs (REST, webhooks, etc.)
├── Analysis & Intelligence
│   ├── Semantic (subcommands: search, cluster, detect_duplicates)
│   └── Graph (subcommands: query, update, visualize)
└── System
    ├── Config (subcommands: get, set, reload)
    └── Monitoring (subcommands: metrics, health, logs)
```

### 3.2 Subcommand Routing

```python
# src/app/mcp/subcommand_router.py (NEW)

from typing import Dict, Callable, Any, List
import logging

logger = logging.getLogger(__name__)

class SubcommandRouter:
    """Route subcommands to appropriate handlers."""
    
    def __init__(self):
        self.handlers: Dict[str, Dict[str, Callable]] = {}
    
    def register(self, tool_name: str, subcommand: str, handler: Callable):
        """Register a subcommand handler."""
        if tool_name not in self.handlers:
            self.handlers[tool_name] = {}
        
        self.handlers[tool_name][subcommand] = handler
        logger.info(f"Registered subcommand: {tool_name}.{subcommand}")
    
    def route(self, tool_name: str, subcommand: str, args: Dict) -> Any:
        """Route a subcommand to its handler."""
        if tool_name not in self.handlers:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        if subcommand not in self.handlers[tool_name]:
            available = list(self.handlers[tool_name].keys())
            raise ValueError(f"Unknown subcommand: {subcommand}. Available: {available}")
        
        handler = self.handlers[tool_name][subcommand]
        return handler(**args)
    
    def list_subcommands(self, tool_name: str) -> List[str]:
        """List available subcommands for a tool."""
        return list(self.handlers.get(tool_name, {}).keys())

# Example subcommand registrations
def setup_data_access_subcommands(router: SubcommandRouter):
    """Setup data access subcommands."""
    
    def query_list(entity_type: str, limit: int = 50):
        """List entities."""
        # Implementation stub
        pass
    
    def query_search(entity_type: str, term: str, limit: int = 10):
        """Search entities."""
        # Implementation stub
        pass
    
    def query_filter(entity_type: str, filters: Dict):
        """Filter entities by criteria."""
        # Implementation stub
        pass
    
    def query_aggregate(entity_type: str, group_by: str):
        """Aggregate data."""
        # Implementation stub
        pass
    
    router.register("query_data", "list", query_list)
    router.register("query_data", "search", query_search)
    router.register("query_data", "filter", query_filter)
    router.register("query_data", "aggregate", query_aggregate)

def setup_semantic_search_subcommands(router: SubcommandRouter):
    """Setup semantic search subcommands."""
    
    def search(query: str, entity_types: List[str] = None, top_k: int = 5):
        """Search by semantic similarity."""
        # Implementation stub
        pass
    
    def cluster(entity_type: str, num_clusters: int = 5):
        """Cluster similar items."""
        # Implementation stub
        pass
    
    def detect_duplicates(entity_type: str, threshold: float = 0.95):
        """Find duplicate/similar items."""
        # Implementation stub
        pass
    
    router.register("semantic_search", "search", search)
    router.register("semantic_search", "cluster", cluster)
    router.register("semantic_search", "detect_duplicates", detect_duplicates)

# Global router
_router: SubcommandRouter = SubcommandRouter()

def get_subcommand_router() -> SubcommandRouter:
    """Get global subcommand router."""
    return _router

def initialize_subcommands():
    """Initialize all subcommand handlers."""
    setup_data_access_subcommands(_router)
    setup_semantic_search_subcommands(_router)
    # Add more as needed
```

---

## 4. Integration Points in Existing Code

### 4.1 Areas Needing Multi-Agent Infrastructure

| Current Code | Purpose | Integration Point |
|--------------|---------|------------------|
| `main.py` | Flask/FastAPI routes | Agent message handlers |
| `llm.py` | LLM calls | Tool usage before calling LLM |
| `api/assistant.py` | Arjuna agent | Message bus for agent-to-agent comms |
| `api/career.py` | Career Coach agent | Task queue for long-running analysis |
| `api/neo4j_graph.py` | Knowledge graph | Graph analysis tools |
| `search.py` | Search functionality | Hybrid search with semantic layer |
| `db.py` | Database layer | Query tool access control |
| `config.py` | Configuration | MCP server registration config |

### 4.2 Initialization Order

```python
# src/app/startup.py (NEW)

import logging
from .services.agent_lifecycle import get_agent_registry
from .services.agent_bus import get_agent_bus
from .mcp.tool_registry import get_tool_registry, initialize_subcommands
from .mcp.server_manager import get_mcp_manager
from .config import MCP_SERVERS_CONFIG, ENABLE_MULTI_AGENT

logger = logging.getLogger(__name__)

async def initialize_multi_agent_system():
    """Initialize multi-agent system and MCP integrations."""
    
    if not ENABLE_MULTI_AGENT:
        logger.info("Multi-agent system disabled")
        return
    
    logger.info("Initializing multi-agent system...")
    
    # 1. Initialize tool registry
    tool_registry = get_tool_registry()
    initialize_subcommands()
    logger.info("Tool registry initialized")
    
    # 2. Initialize agent bus
    agent_bus = get_agent_bus()
    logger.info("Agent bus initialized")
    
    # 3. Register MCP servers (from config)
    mcp_manager = get_mcp_manager()
    for server_name, server_config in MCP_SERVERS_CONFIG.items():
        if server_config.get("enabled"):
            await mcp_manager.register_server(
                server_name,
                server_config["class"],  # MCPServer subclass
                server_config,
            )
    logger.info(f"MCP servers initialized: {list(mcp_manager.active_servers.keys())}")
    
    # 4. Startup agents
    agent_registry = get_agent_registry()
    await agent_registry.startup_all()
    logger.info("All agents started")

async def shutdown_multi_agent_system():
    """Shutdown multi-agent system gracefully."""
    
    if not ENABLE_MULTI_AGENT:
        return
    
    logger.info("Shutting down multi-agent system...")
    
    mcp_manager = get_mcp_manager()
    await mcp_manager.shutdown_all()
    
    agent_registry = get_agent_registry()
    await agent_registry.shutdown_all()
    
    logger.info("Multi-agent system shutdown complete")
```

---

## 5. Configuration Structure

```yaml
# config/multi_agent.yaml (NEW)

# Enable multi-agent system
enabled: true

# Agent configuration
agents:
  arjuna:
    enabled: true
    auto_start: true
    message_handlers:
      - message_type: "query"
        handler: "src.app.agents.arjuna.handle_query"
  
  career_coach:
    enabled: true
    auto_start: true
  
  meeting_analyzer:
    enabled: true
    auto_start: false  # Start on demand
  
  dikw_synthesizer:
    enabled: true
    auto_start: true

# MCP servers (optional integrations)
mcp_servers:
  notion:
    enabled: false  # Enable when configured
    endpoint: "http://localhost:3000"
    credentials:
      api_key: ${NOTION_API_KEY}
  
  github:
    enabled: false
    credentials:
      token: ${GITHUB_TOKEN}
  
  slack:
    enabled: false
    credentials:
      bot_token: ${SLACK_BOT_TOKEN}

# Tool access control
tool_access:
  default_policy: "deny"  # deny/allow
  per_agent:
    arjuna:
      allowed_tools:
        - "query_data"
        - "semantic_search"
        - "query_agent"
    
    career_coach:
      allowed_tools:
        - "query_data"
        - "semantic_search"

# Message queue settings
message_queue:
  max_size: 10000
  retention_hours: 24
  cleanup_interval_minutes: 60
```

---

## 6. Future Extensions

### 6.1 New MCP Servers (Stubs for Planning)

- **Notion**: Sync knowledge base with Notion
- **GitHub**: Auto-create issues, track PRs
- **Slack**: Send notifications, get channel history
- **Google Calendar**: Meeting imports and scheduling
- **Linear**: Task management integration
- **LangChain**: Advanced chain coordination
- **Custom**: User-defined MCP servers

### 6.2 Agent Capabilities (Extensible)

- **Skills registry**: What each agent can do
- **Performance tracking**: Agent metrics and optimization
- **Learning**: Agents improve from feedback
- **Specialization**: Deep expertise in domains
- **Collaboration**: Multi-agent workflows

---

## Summary

This architecture provides:
✅ **Agent Communication Bus** - Messages between agents  
✅ **Tool Registry** - Hierarchical tool organization  
✅ **Subcommand Routing** - Efficient tool access  
✅ **MCP Integration Points** - Optional external services  
✅ **Extensibility** - Easy to add agents, tools, MCP servers  
✅ **Future-Proof** - Designed for growth and new capabilities

