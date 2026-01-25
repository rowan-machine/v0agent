# Integration Quick Start - Multi-Agent Infrastructure

This guide shows how to integrate the new multi-agent system into existing code.

---

## 1. Update Application Startup

In `src/app/main.py`, add to startup event:

```python
from src.app.services.agent_bus import initialize_agent_bus
from src.app.mcp.tool_registry import initialize_tool_registry
from src.app.mcp.subcommand_router import initialize_subcommand_handlers
from src.app.services.agent_lifecycle import get_agent_registry

@app.on_event("startup")
async def startup():
    """Initialize multi-agent system on app startup."""
    
    # Initialize components
    logger.info("Initializing multi-agent system...")
    
    # 1. Agent bus for messaging
    bus = initialize_agent_bus(db_path="agent.db")
    logger.info("✓ Agent bus initialized")
    
    # 2. Tool registry
    tool_registry = initialize_tool_registry()
    logger.info("✓ Tool registry initialized")
    
    # 3. Subcommand router
    router = initialize_subcommand_handlers()
    logger.info("✓ Subcommand router initialized")
    
    # 4. Agent registry (register your agents here)
    agent_registry = get_agent_registry()
    logger.info("✓ Agent registry ready")
    
    # 5. Startup agents
    # await agent_registry.startup_all()
    # logger.info("✓ All agents started")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    agent_registry = get_agent_registry()
    await agent_registry.shutdown_all()
    logger.info("✓ All agents shutdown")
```

---

## 2. Create Your First Agent

```python
# src/app/agents/example_agent.py

from src.app.agents.base import BaseAgent
from src.app.services.agent_bus import get_agent_bus, AgentMessage, MessageType

class ExampleAgent(BaseAgent):
    """Example agent that responds to queries."""
    
    async def process_message(self, msg: AgentMessage):
        """Process incoming message."""
        if msg.message_type == MessageType.QUERY:
            response_text = f"Response to: {msg.content.get('question', '')}"
            return {
                "status": "success",
                "response": response_text,
                "confidence": 0.9,
            }
        return {"status": "unhandled"}
    
    async def startup(self):
        """Initialize agent."""
        self.state = "idle"
        logger.info(f"Agent {self.name} started")
    
    async def shutdown(self):
        """Cleanup agent."""
        logger.info(f"Agent {self.name} shutdown")

# Register in main.py startup:
# example_agent = ExampleAgent(name="example")
# agent_registry.register(example_agent, dependencies=[])
```

---

## 3. Use Agent Bus for Inter-Agent Communication

```python
# Send message from one agent to another

from src.app.services.agent_bus import get_agent_bus, AgentMessage, MessageType, MessagePriority

bus = get_agent_bus()

# Create message
msg = AgentMessage(
    source_agent="agent_1",
    target_agent="agent_2",  # Or None for broadcast
    message_type=MessageType.QUERY,
    content={"question": "What's the latest update?"},
    priority=MessagePriority.HIGH,
)

# Send
msg_id = bus.send(msg)

# Receive (in agent_2)
messages = bus.receive("agent_2")
for msg in messages:
    bus.mark_processing(msg.id)
    result = await agent_2.process_message(msg)
    bus.mark_completed(msg.id, result)
```

---

## 4. Use Tool Registry

```python
# Access available tools

from src.app.mcp.tool_registry import get_tool_registry, ToolCategory

registry = get_tool_registry()

# Get all data query tools
query_tools = registry.get_tools_by_category(ToolCategory.DATA_QUERY)
for tool in query_tools:
    print(f"{tool.name}: {tool.description}")

# Get specific tool
tool = registry.get_tool("query_data")
if tool:
    subcommands = tool.subcommands  # ["list", "search", "filter", "aggregate"]

# Get tools for an agent
agent_tools = registry.get_tools_for_agent("arjuna")

# Check if tool is available
if registry.get_tool("semantic_search") and registry.get_tool("semantic_search").enabled:
    # Use semantic search
    pass
```

---

## 5. Use Subcommand Router

```python
# Route commands to handlers

from src.app.mcp.subcommand_router import get_subcommand_router

router = get_subcommand_router()

# Route a command
result = router.route(
    tool_name="query_data",
    subcommand="list",
    args={"entity_type": "meetings", "limit": 50}
)

# Get available subcommands
subcommands = router.list_subcommands("query_data")
# Returns: ["list", "search", "filter", "aggregate"]

# Get detailed info
info = router.get_subcommand_info("query_data", "search")
print(f"Description: {info.description}")
print(f"Expected args: {info.arg_names}")
```

---

## 6. Integrate with LLM Function Calling

```python
# In llm.py or a tool caller

from src.app.mcp.tool_registry import get_tool_registry

def prepare_tools_for_llm():
    """Convert tools to OpenAI function format."""
    registry = get_tool_registry()
    
    enabled_tools = registry.list_enabled_tools()
    functions = []
    
    for tool_name in enabled_tools:
        tool = registry.get_tool(tool_name)
        functions.append(tool.to_openai_function())
    
    return functions

# Use in OpenAI function calling
response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=messages,
    functions=prepare_tools_for_llm(),
    function_call="auto",
)

# Handle function calls
for choice in response.choices:
    if choice.message.get("function_call"):
        func_call = choice.message["function_call"]
        tool_name = func_call["name"]
        args = json.loads(func_call["arguments"])
        
        # If tool has subcommands
        if "_" in tool_name and "." in tool_name:
            # Format: tool_name.subcommand
            parts = tool_name.split(".")
            result = router.route(parts[0], parts[1], args)
        else:
            # Direct tool call
            tool = registry.get_tool(tool_name)
            result = tool.func(**args)
```

---

## 7. Add Health Checks

```python
# In src/app/api/health.py (create if not exists)

from fastapi import APIRouter, HTTPException
from datetime import datetime
from src.app.services.agent_bus import get_agent_bus
from src.app.mcp.tool_registry import get_tool_registry

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")
async def health_check():
    """Basic health check for load balancers."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@router.get("/ready")
async def readiness_check():
    """Readiness check - are we ready to serve?"""
    checks = {}
    
    try:
        # Check database
        from src.app.db import connect
        with connect() as conn:
            conn.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        checks["database"] = False
        logger.error(f"Database check failed: {e}")
    
    try:
        # Check agent bus
        bus = get_agent_bus()
        checks["agent_bus"] = True
    except Exception as e:
        checks["agent_bus"] = False
        logger.error(f"Agent bus check failed: {e}")
    
    try:
        # Check tool registry
        registry = get_tool_registry()
        checks["tool_registry"] = len(registry.list_all_tools()) > 0
    except Exception as e:
        checks["tool_registry"] = False
        logger.error(f"Tool registry check failed: {e}")
    
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return {
        "status": "ready",
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }

@router.get("/metrics")
async def metrics():
    """Get system metrics."""
    import psutil
    
    bus = get_agent_bus()
    registry = get_tool_registry()
    
    return {
        "memory_percent": psutil.virtual_memory().percent,
        "cpu_percent": psutil.cpu_percent(interval=1),
        "agent_messages": bus.get_message_stats(),
        "tool_registry": registry.get_registry_stats(),
        "timestamp": datetime.now().isoformat(),
    }

# Include in main.py
# app.include_router(health_router)
```

---

## 8. Testing Integration

```python
# tests/test_integration_multi_agent.py

import pytest
from src.app.services.agent_bus import get_agent_bus, AgentMessage, MessageType
from src.app.mcp.tool_registry import get_tool_registry

@pytest.mark.integration
def test_agent_bus_integration(db_connection):
    """Test agent bus integration."""
    bus = get_agent_bus()
    
    msg = AgentMessage(
        source_agent="test_agent",
        target_agent="other_agent",
        message_type=MessageType.QUERY,
        content={"test": "data"}
    )
    
    msg_id = bus.send(msg)
    messages = bus.receive("other_agent")
    
    assert len(messages) > 0
    assert messages[0].id == msg_id

@pytest.mark.integration
def test_tool_registry_integration():
    """Test tool registry integration."""
    registry = get_tool_registry()
    
    # Should have default tools
    assert len(registry.list_all_tools()) > 0
    
    # Tools should be available
    query_tool = registry.get_tool("query_data")
    assert query_tool is not None
    assert query_tool.enabled
    
    # Subcommands should be defined
    assert len(query_tool.subcommands) > 0
```

---

## 9. Configuration (YAML)

```yaml
# config/multi_agent.yaml

enabled: true

agents:
  arjuna:
    enabled: true
    auto_start: true
  
  career_coach:
    enabled: true
    auto_start: true
  
  meeting_analyzer:
    enabled: true
    auto_start: false

mcp_servers:
  notion:
    enabled: false
    endpoint: "http://localhost:3000"
  
  github:
    enabled: false
    credentials:
      token: "${GITHUB_TOKEN}"

tool_access:
  default_policy: "deny"
  per_agent:
    arjuna:
      allowed_tools:
        - "query_data"
        - "semantic_search"
        - "query_agent"
```

---

## 10. Docker Integration

Run the provided Docker setup:

```bash
# Build
make build

# Run
make run

# Test
make test

# View logs
make logs
```

---

## Key Entry Points

| Component | File | Key Functions |
|-----------|------|---|
| Agent Bus | `src/app/services/agent_bus.py` | `get_agent_bus()`, `send()`, `receive()` |
| Tool Registry | `src/app/mcp/tool_registry.py` | `get_tool_registry()`, `get_tool()`, `get_tools_by_category()` |
| Subcommand Router | `src/app/mcp/subcommand_router.py` | `get_subcommand_router()`, `route()`, `list_subcommands()` |
| Agent Registry | `src/app/services/agent_lifecycle.py` | `get_agent_registry()`, `register()`, `startup_all()` |

---

## Common Patterns

### Pattern 1: Agent Sends Query to Another Agent

```python
# In agent_1
bus = get_agent_bus()
msg = AgentMessage(
    source_agent="agent_1",
    target_agent="agent_2",
    message_type=MessageType.QUERY,
    content={"question": "..."},
    priority=MessagePriority.HIGH,
)
bus.send(msg)

# In agent_2
messages = bus.receive("agent_2")
for msg in messages:
    response = await process_message(msg)
    bus.mark_completed(msg.id)
```

### Pattern 2: LLM Uses Tools

```python
# Get available tools
tools = prepare_tools_for_llm()

# Call LLM with functions
response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=messages,
    functions=tools,
)

# Handle response
if "function_call" in response.choices[0].message:
    call = response.choices[0].message.function_call"
    result = router.route(call["name"], call["subcommand"], call["args"])
```

### Pattern 3: Register Custom Tool

```python
from src.app.mcp.tool_registry import get_tool_registry, Tool, ToolCategory

registry = get_tool_registry()

# Create tool
custom_tool = Tool(
    name="my_custom_tool",
    category=ToolCategory.ANALYSIS,
    description="My custom tool",
    input_schema={"type": "object", "properties": {...}},
    output_schema={"type": "object", "properties": {...}},
    subcommands=["action1", "action2"],
)

# Register
registry.register_tool(custom_tool)

# Register handlers
router = get_subcommand_router()
router.register("my_custom_tool", "action1", handler_func)
router.register("my_custom_tool", "action2", handler_func)
```

---

## Troubleshooting

### Agent Bus Not Initialized

```python
# Make sure to call in startup:
from src.app.services.agent_bus import initialize_agent_bus
bus = initialize_agent_bus()
```

### Tool Not Found

```python
# Check if tool is registered and enabled
registry = get_tool_registry()
tool = registry.get_tool("tool_name")
if tool and tool.enabled:
    # Use tool
    pass
else:
    logger.warning("Tool not available")
```

### Subcommand Not Routed

```python
# Check available subcommands
router = get_subcommand_router()
available = router.list_subcommands("tool_name")
if subcommand in available:
    result = router.route("tool_name", subcommand, args)
else:
    raise ValueError(f"Unknown subcommand: {subcommand}")
```

---

## Next Steps

1. Register your agents in `src/app/agents/`
2. Create handlers for your tools in `src/app/mcp/handlers/`
3. Add tests in `tests/integration/`
4. Hook into LLM function calling
5. Deploy with Docker Compose

See MULTI_AGENT_ARCHITECTURE.md and TESTING_STRATEGY.md for detailed patterns.

