# Ticket-Linked MCP Module Specification

> **Module**: Ticket Task Context System  
> **Status**: SPECIFICATION  
> **Version**: 1.0.0  
> **Date**: January 25, 2026

## Overview

This module creates a bridge between ticket decomposition checklists and AI agents, enabling:
1. **CLI access** to detailed context for specific ticket checklist items (classes, objects, methods)
2. **MCP server integration** for VS Code agents to receive ticket task details directly
3. **Agent Bus integration** for multi-agent coordination on ticket tasks

---

## Problem Statement

Currently, ticket task decomposition exists as checklist items in `task_decomposition` JSON, but:
- No way to get detailed context for a specific checklist item
- AI agents in VS Code cannot directly access ticket task context
- No connection between task items and the actual code/classes they reference

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Ticket Task Context System                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐     │
│   │  CLI Tool   │────▶│ Task Context API │────▶│ Supabase (tickets)  │     │
│   │ (dev_cli)   │     │  /api/tickets/*  │     │                     │     │
│   └─────────────┘     └──────────────────┘     └─────────────────────┘     │
│         │                      │                         │                  │
│         │                      │                         │                  │
│         ▼                      ▼                         ▼                  │
│   ┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐     │
│   │  MCP Server │────▶│   Agent Bus      │────▶│  VS Code Agents     │     │
│   │ (ticket     │     │  (message queue) │     │  (Copilot/Claude)   │     │
│   │  context)   │     │                  │     │                     │     │
│   └─────────────┘     └──────────────────┘     └─────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component 1: CLI Commands

### New Commands in `dev_cli.py`

```python
# Get detailed context for a specific task item
dev task-context TICKET-123 --task 3

# List all tasks with code references
dev tasks --with-refs

# Pass task context to MCP for agents
dev push-task TICKET-123 --task 3
```

### Example Output

```
$ dev task-context TICKET-123 --task 2

📋 TICKET-123: Implement signal deduplication
   Task 2: Create SignalDeduplicator class
   
   📁 Referenced Code:
   ├── src/app/services/signal_processor.py (related)
   ├── src/app/models/signal.py (Signal class definition)
   └── tests/test_signal_processor.py (test patterns)
   
   📝 Task Details:
   - Create new class: SignalDeduplicator
   - Methods: dedupe_by_content(), dedupe_by_embedding()
   - Uses: Signal model, embedding_service
   
   🔗 Related Tickets:
   - TICKET-120: Signal extraction foundation (parent)
   - TICKET-125: Signal confidence scoring (depends)
   
   🤖 Agent Context Ready: Use 'dev push-task TICKET-123 --task 2'
```

---

## Component 2: MCP Server Tools

### New MCP Tools for Ticket Context

```python
# src/app/mcp/tools.py - New tools to add

TICKET_MCP_TOOLS = {
    "get_ticket_context": get_ticket_context,
    "get_task_details": get_task_details,
    "list_ticket_tasks": list_ticket_tasks,
    "get_code_references": get_code_references,
    "update_task_status": update_task_status,
}
```

### Tool Definitions

#### 1. `get_ticket_context`
```json
{
  "name": "get_ticket_context",
  "description": "Get full ticket context including all tasks and code references",
  "parameters": {
    "ticket_id": "string (required) - The ticket ID (e.g., TICKET-123)"
  },
  "returns": {
    "ticket_id": "string",
    "title": "string",
    "description": "string",
    "status": "string",
    "tasks": [
      {
        "index": "number",
        "name": "string",
        "done": "boolean",
        "code_refs": ["string"],
        "details": "string"
      }
    ]
  }
}
```

#### 2. `get_task_details`
```json
{
  "name": "get_task_details",
  "description": "Get detailed context for a specific task including AI-extracted code references",
  "parameters": {
    "ticket_id": "string (required)",
    "task_index": "number (required) - Zero-based index of task"
  },
  "returns": {
    "task": {
      "name": "string",
      "details": "string",
      "acceptance_criteria": ["string"]
    },
    "code_references": [
      {
        "file_path": "string",
        "class_name": "string",
        "method_name": "string",
        "relevance": "direct|related|test"
      }
    ],
    "related_signals": ["string"],
    "implementation_hints": ["string"]
  }
}
```

#### 3. `get_code_references`
```json
{
  "name": "get_code_references",
  "description": "Extract code references from a task name using AI analysis",
  "parameters": {
    "task_name": "string (required) - The task description to analyze"
  },
  "returns": {
    "classes": ["string"],
    "methods": ["string"],
    "files": ["string"],
    "modules": ["string"]
  }
}
```

---

## Component 3: VS Code Agent Integration

### MCP Server Configuration

The MCP server will expose these tools to VS Code agents via the standard MCP protocol.

```json
// .vscode/mcp.json (proposed)
{
  "servers": {
    "v0agent-tickets": {
      "type": "http",
      "url": "http://localhost:8001/mcp",
      "tools": [
        "get_ticket_context",
        "get_task_details",
        "list_ticket_tasks",
        "get_code_references",
        "update_task_status"
      ]
    }
  }
}
```

### Agent Workflow

```
1. User says: "Help me implement task 2 of TICKET-123"

2. Agent calls MCP: get_task_details(TICKET-123, 2)

3. MCP returns:
   - Task: "Create SignalDeduplicator class"
   - Code refs: signal_processor.py, signal.py
   - Implementation hints from ticket description

4. Agent proceeds with full context awareness
```

---

## Component 4: Agent Bus Integration

### Message Types for Ticket Tasks

```python
class TicketTaskMessage(AgentMessage):
    """Message type for ticket task coordination."""
    
    ticket_id: str
    task_index: int
    action: str  # "start", "complete", "blocked", "review_needed"
    context: Dict[str, Any]  # Task details from MCP
```

### Agent Coordination Flow

```
┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
│ VS Code User │────▶│ Orchestrator  │────▶│ Task Executor    │
│ "Implement   │     │ Agent         │     │ Agent            │
│  task 2"     │     │               │     │                  │
└──────────────┘     └───────────────┘     └──────────────────┘
                            │                      │
                            │ Bus: TASK_STARTED    │
                            ▼                      ▼
                     ┌───────────────┐     ┌──────────────────┐
                     │ Notification  │     │ Documentation    │
                     │ Agent         │     │ Agent            │
                     │ (log action)  │     │ (prep context)   │
                     └───────────────┘     └──────────────────┘
```

---

## Database Schema Extensions

### New Table: `task_code_references`

```sql
CREATE TABLE task_code_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id TEXT NOT NULL,
    task_index INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    class_name TEXT,
    method_name TEXT,
    relevance TEXT CHECK (relevance IN ('direct', 'related', 'test')),
    extracted_at TIMESTAMP DEFAULT NOW(),
    extracted_by TEXT,  -- 'ai' or 'manual'
    UNIQUE(ticket_id, task_index, file_path, class_name, method_name)
);

CREATE INDEX idx_task_refs_ticket ON task_code_references(ticket_id);
```

### New Column on `tickets`

```sql
ALTER TABLE tickets ADD COLUMN task_metadata JSONB DEFAULT '{}';
-- Stores AI-extracted metadata per task
```

---

## Implementation Phases

### Phase 1: CLI Foundation (Week 1)
- [ ] Add `task-context` command to dev_cli.py
- [ ] Implement basic code reference extraction (regex-based)
- [ ] Add `tasks --with-refs` listing

### Phase 2: MCP Tools (Week 2)
- [ ] Create `get_ticket_context` MCP tool
- [ ] Create `get_task_details` MCP tool
- [ ] Update MCP registry with ticket tools
- [ ] Test MCP endpoint with curl/Postman

### Phase 3: AI Enhancement (Week 3)
- [ ] Add AI-based code reference extraction
- [ ] Store extracted refs in `task_code_references` table
- [ ] Add implementation hint generation

### Phase 4: Agent Bus Integration (Week 4)
- [ ] Define `TicketTaskMessage` type
- [ ] Create task executor agent skeleton
- [ ] Wire up MCP → Agent Bus communication
- [ ] Add task status updates via bus

### Phase 5: VS Code Integration (Week 5)
- [ ] Create MCP server manifest
- [ ] Test with Copilot/Claude agents
- [ ] Document agent workflows

---

## API Endpoints

### REST API

```
GET  /api/tickets/{ticket_id}/context
     Returns full ticket with task details

GET  /api/tickets/{ticket_id}/tasks/{index}
     Returns specific task with code references

POST /api/tickets/{ticket_id}/tasks/{index}/refs
     AI extracts and stores code references

PUT  /api/tickets/{ticket_id}/tasks/{index}/status
     Update task completion status

POST /api/mcp/call
     MCP tool invocation endpoint (existing)
```

---

## Security Considerations

1. **MCP Authentication**: Use existing bypass token or session auth
2. **Code Reference Access**: Only return file paths, not actual code content
3. **Task Updates**: Audit log all status changes

---

## Success Metrics

1. CLI: User can get task context in < 2 seconds
2. MCP: Agents can retrieve task details in single call
3. Code Refs: 80%+ accuracy on class/method extraction
4. Integration: End-to-end flow works in VS Code

---

## Related Files

- `scripts/dev_cli.py` - CLI implementation
- `src/app/mcp/tools.py` - MCP tool definitions
- `src/app/mcp/registry.py` - Tool registration
- `src/app/infrastructure/agent_bus.py` - Message bus
- `src/app/services/tickets_supabase.py` - Ticket service
