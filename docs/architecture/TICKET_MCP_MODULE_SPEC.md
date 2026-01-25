# Ticket-Linked MCP Module Specification

> **Module**: Ticket Task Context System  
> **Status**: SPECIFICATION  
> **Version**: 1.1.0  
> **Date**: January 25, 2026

## Overview

This module creates a bridge between ticket decomposition checklists and AI agents, enabling:
1. **CLI access** to detailed context for specific ticket checklist items (classes, objects, methods)
2. **MCP server integration** for VS Code agents to receive ticket task details directly
3. **Agent Bus integration** for multi-agent coordination on ticket tasks
4. **External MCP tool orchestration** for code execution, testing, and pipeline management

---

## Problem Statement

Currently, ticket task decomposition exists as checklist items in `task_decomposition` JSON, but:
- No way to get detailed context for a specific checklist item
- AI agents in VS Code cannot directly access ticket task context
- No connection between task items and the actual code/classes they reference
- No automated test execution or validation tied to ticket acceptance criteria

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
│   │ (v0agent)   │     │  (message queue) │     │  (Copilot/Claude)   │     │
│   └─────────────┘     └──────────────────┘     └─────────────────────┘     │
│         │                                                │                  │
│         │         ┌──────────────────────────────────────┘                  │
│         │         │                                                         │
│         ▼         ▼                                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │              External MCP Tools (Code Execution & Testing)           │  │
│   ├─────────────────────────────────────────────────────────────────────┤  │
│   │  dmp-dev-tools      │  airflow-mcp       │  quote2contract-mcp      │  │
│   │  • run_pytest       │  • trigger_dag     │  • q2c_build             │  │
│   │  • run_transform    │  • run_e2e_test    │  • q2c_query_database    │  │
│   │  • generate_mock    │  • get_task_logs   │  • q2c_seed_test_data    │  │
│   │  • check_env        │  • verify_output   │  • q2c_reset_database    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
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
    # Ticket Context Tools
    "get_ticket_context": get_ticket_context,
    "get_task_details": get_task_details,
    "list_ticket_tasks": list_ticket_tasks,
    "get_code_references": get_code_references,
    "update_task_status": update_task_status,
    
    # Test Plan Tools
    "get_test_plan": get_test_plan,
    "list_test_cases": list_test_cases,
    "get_acceptance_criteria": get_acceptance_criteria,
    "update_test_status": update_test_status,
    "generate_test_scaffold": generate_test_scaffold,
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
    ],
    "test_plan": {
      "acceptance_criteria": ["string"],
      "test_cases": ["object"],
      "coverage_target": "number"
    }
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
    "implementation_hints": ["string"],
    "test_requirements": ["string"]
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

### Test Plan Tools

#### 4. `get_test_plan`
```json
{
  "name": "get_test_plan",
  "description": "Get the complete test plan for a ticket including all test cases and acceptance criteria",
  "parameters": {
    "ticket_id": "string (required) - The ticket ID"
  },
  "returns": {
    "ticket_id": "string",
    "title": "string",
    "acceptance_criteria": [
      {
        "id": "string",
        "description": "string",
        "status": "pending|passed|failed",
        "test_case_ids": ["string"]
      }
    ],
    "test_cases": [
      {
        "id": "string",
        "name": "string",
        "type": "unit|integration|e2e|manual",
        "status": "not_run|passed|failed|skipped",
        "file_path": "string",
        "linked_tasks": ["number"],
        "last_run": "datetime"
      }
    ],
    "coverage": {
      "target": "number",
      "current": "number",
      "uncovered_areas": ["string"]
    }
  }
}
```

#### 5. `list_test_cases`
```json
{
  "name": "list_test_cases",
  "description": "List all test cases for a ticket, optionally filtered by status or type",
  "parameters": {
    "ticket_id": "string (required)",
    "status": "string (optional) - Filter by: not_run, passed, failed, skipped",
    "type": "string (optional) - Filter by: unit, integration, e2e, manual"
  },
  "returns": {
    "test_cases": [
      {
        "id": "string",
        "name": "string",
        "type": "string",
        "status": "string",
        "task_index": "number"
      }
    ],
    "summary": {
      "total": "number",
      "passed": "number",
      "failed": "number",
      "not_run": "number"
    }
  }
}
```

#### 6. `get_acceptance_criteria`
```json
{
  "name": "get_acceptance_criteria",
  "description": "Get acceptance criteria for a ticket with linked test cases",
  "parameters": {
    "ticket_id": "string (required)"
  },
  "returns": {
    "criteria": [
      {
        "id": "string",
        "description": "string",
        "priority": "must|should|could",
        "status": "pending|verified|blocked",
        "verification_method": "automated|manual|review",
        "linked_tests": ["string"]
      }
    ]
  }
}
```

#### 7. `update_test_status`
```json
{
  "name": "update_test_status",
  "description": "Update the status of a test case after running",
  "parameters": {
    "ticket_id": "string (required)",
    "test_case_id": "string (required)",
    "status": "string (required) - passed, failed, skipped",
    "details": "string (optional) - Error message or notes"
  },
  "returns": {
    "success": "boolean",
    "test_case": "object",
    "acceptance_criteria_updated": ["string"]
  }
}
```

#### 8. `generate_test_scaffold`
```json
{
  "name": "generate_test_scaffold",
  "description": "Generate test file scaffolding for a ticket task based on code references",
  "parameters": {
    "ticket_id": "string (required)",
    "task_index": "number (required)",
    "test_type": "string (optional) - unit, integration, e2e (default: unit)"
  },
  "returns": {
    "file_path": "string",
    "content": "string",
    "test_functions": [
      {
        "name": "string",
        "description": "string",
        "linked_criteria": "string"
      }
    ],
    "imports_needed": ["string"]
  }
}
```

---

## Component 2.5: External MCP Tool Integration

### Overview

Integrate with external MCP servers (dmp-dev-tools, airflow-mcp, quote2contract-mcp) to enable:
- **Code execution** in isolated environments
- **Test running** with pytest and pipeline validation
- **Environment management** (Docker, venv, dependencies)
- **Pipeline orchestration** (DAG triggering, monitoring, debugging)

### External MCP Server Registry

```json
{
  "external_mcp_servers": {
    "dmp-dev-tools": {
      "description": "Developer experience tools for testing and debugging",
      "capabilities": ["code_execution", "testing", "schema_discovery", "debugging"],
      "env_vars": ["DMP_WORKSPACE_ROOT", "AIRFLOW_URL", "AIRFLOW_USER", "AIRFLOW_PASSWORD"]
    },
    "airflow-mcp": {
      "description": "Airflow DAG management and E2E testing",
      "capabilities": ["pipeline_orchestration", "e2e_testing", "s3_operations"],
      "env_vars": ["AIRFLOW_URL", "AIRFLOW_USER", "AIRFLOW_PASSWORD", "S3_ENDPOINT", "S3_BUCKET"]
    },
    "quote2contract-mcp": {
      "description": "Q2C application lifecycle and database management",
      "capabilities": ["build", "database_management", "test_data"],
      "env_vars": ["Q2C_DIR", "JAVA_HOME"]
    }
  }
}
```

### External Tool Categories

#### Code Execution Tools (from dmp-dev-tools)

| Tool | Purpose | Use in Ticket Workflow |
|------|---------|------------------------|
| `run_transform_isolated` | Run single transform in isolation | Validate task implementation |
| `run_pytest_for_transform` | Run pytest for specific transform | Automated unit testing |
| `generate_mock_context` | Generate mock Airflow context | TDD for pipeline tasks |
| `setup_local_venv` | Create/configure Python environment | Environment setup phase |
| `check_local_environment` | Verify required packages | Pre-implementation validation |

#### Testing & Validation Tools

| Tool | Source | Purpose | Use in Ticket Workflow |
|------|--------|---------|------------------------|
| `run_e2e_rxclaims_test` | airflow-mcp | Full pipeline validation | Integration testing phase |
| `compare_pipeline_runs` | dmp-dev-tools | Regression testing | QA validation |
| `verify_e2e_test_output` | airflow-mcp | Check S3 outputs exist | Acceptance criteria validation |
| `q2c_seed_test_data` | quote2contract-mcp | Create test fixtures | Test data setup |
| `q2c_verify_test_data` | quote2contract-mcp | Verify test data exists | Pre-test validation |

#### Debugging Tools

| Tool | Source | Purpose | Use in Ticket Workflow |
|------|--------|---------|------------------------|
| `explain_dag_error` | dmp-dev-tools | Parse error logs, suggest fixes | Debug failed tests |
| `get_task_logs` | airflow-mcp | Retrieve task execution logs | Investigate failures |
| `create_dag_debug_notebook` | dmp-dev-tools | Generate Jupyter notebook | Interactive debugging |
| `inspect_parquet_file` | dmp-dev-tools | Examine intermediate outputs | Data validation |

#### Pipeline Orchestration Tools

| Tool | Source | Purpose | Use in Ticket Workflow |
|------|--------|---------|------------------------|
| `trigger_dag` | airflow-mcp | Start DAG execution | Run integration tests |
| `get_dag_run_status` | airflow-mcp | Monitor execution | Track test progress |
| `list_dag_runs` | airflow-mcp | View run history | Compare with previous |
| `clear_task_instances` | airflow-mcp | Re-run failed tasks | Retry failed tests |

#### Schema Discovery Tools

| Tool | Source | Purpose | Use in Ticket Workflow |
|------|--------|---------|------------------------|
| `discover_pipeline_schema` | dmp-dev-tools | Get input/output schemas | Understand requirements |
| `discover_dag_config_from_code` | dmp-dev-tools | Extract config requirements | Auto-generate test configs |
| `visualize_dag_dependencies` | dmp-dev-tools | Show task graph | Document task flow |

### Orchestration Tool: `execute_test_plan`

This high-level tool orchestrates external MCP tools to execute a complete test plan:

```json
{
  "name": "execute_test_plan",
  "description": "Execute all tests in a ticket's test plan using appropriate external MCP tools",
  "parameters": {
    "ticket_id": "string (required)",
    "test_types": "array (optional) - Filter by: unit, integration, e2e, manual",
    "stop_on_failure": "boolean (optional, default: false)",
    "parallel": "boolean (optional, default: true for unit tests)"
  },
  "workflow": [
    "1. Get test plan from ticket",
    "2. Check environment (check_local_environment)",
    "3. Setup test data if needed (q2c_seed_test_data)",
    "4. For each test case:",
    "   - unit: run_pytest_for_transform",
    "   - integration: create_integration_test → run_pytest",
    "   - e2e: run_e2e_rxclaims_test → verify_e2e_test_output",
    "5. Update test_cases table with results",
    "6. Update acceptance_criteria status",
    "7. Return summary report"
  ],
  "returns": {
    "ticket_id": "string",
    "summary": {
      "total": "number",
      "passed": "number",
      "failed": "number",
      "skipped": "number",
      "duration_seconds": "number"
    },
    "test_results": [
      {
        "test_id": "string",
        "name": "string",
        "status": "passed|failed|skipped",
        "duration_ms": "number",
        "error": "string (if failed)",
        "external_tool_used": "string"
      }
    ],
    "acceptance_criteria_status": [
      {
        "id": "string",
        "description": "string",
        "status": "pending|verified|blocked"
      }
    ]
  }
}
```

### Orchestration Tool: `debug_failed_test`

```json
{
  "name": "debug_failed_test",
  "description": "Analyze a failed test and provide debugging context",
  "parameters": {
    "ticket_id": "string (required)",
    "test_case_id": "string (required)"
  },
  "workflow": [
    "1. Get test case details from ticket",
    "2. If pipeline test: get_task_logs → explain_dag_error",
    "3. If unit test: inspect error output",
    "4. Optionally create_dag_debug_notebook for interactive debugging",
    "5. Return analysis with suggested fixes"
  ],
  "returns": {
    "test_case": "object",
    "error_analysis": {
      "error_type": "string",
      "root_cause": "string",
      "stack_trace": "string",
      "suggested_fixes": ["string"]
    },
    "debug_notebook_path": "string (optional)",
    "related_code_references": ["string"]
  }
}
```

### Orchestration Tool: `setup_ticket_environment`

```json
{
  "name": "setup_ticket_environment",
  "description": "Setup local development environment for working on a ticket",
  "parameters": {
    "ticket_id": "string (required)",
    "include_test_data": "boolean (optional, default: true)"
  },
  "workflow": [
    "1. Get ticket task details and code references",
    "2. check_local_environment → setup_local_venv if needed",
    "3. If pipeline ticket: discover_pipeline_schema",
    "4. If include_test_data: q2c_seed_test_data or generate_test_data",
    "5. Return environment status and next steps"
  ],
  "returns": {
    "environment_ready": "boolean",
    "venv_path": "string",
    "missing_packages": ["string"],
    "test_data_loaded": "boolean",
    "schema_discovered": "object (optional)",
    "next_steps": ["string"]
  }
}
```

---

## Component 3: VS Code Agent Integration

### MCP Server Configuration

The MCP server will expose these tools to VS Code agents via the standard MCP protocol.

> **Note**: The `v0agent-local` server is currently in the backlog pending local server stability fixes.
> See [GIGA_PLAN.md](../../GIGA_PLAN.md#backlog) for status.

```json
// .vscode/mcp.json - Target configuration (when v0agent-local is ready)
{
  "servers": {
    "v0agent-local": {
      "type": "http",
      "url": "http://localhost:8001/mcp/call",
      "description": "Local v0agent for ticket context and test plans",
      "status": "BACKLOG - pending server stability",
      "tools": [
        "get_ticket_context",
        "get_task_details",
        "list_ticket_tasks",
        "get_code_references",
        "update_task_status",
        "get_test_plan",
        "list_test_cases",
        "get_acceptance_criteria",
        "update_test_status",
        "generate_test_scaffold",
        "execute_test_plan",
        "debug_failed_test",
        "setup_ticket_environment"
      ]
    }
  }
}
```

### External MCP Servers (ringlinq-mcp)

These external MCP servers provide code execution and testing capabilities:

```json
// ringlinq-mcp/mcp.json - External tools configuration
{
  "servers": {
    "dmp-dev-tools": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "${DMP_DEV_TOOLS_PATH}", "run", "dmp-dev-tools"],
      "description": "Developer tools for code execution and testing",
      "env": {
        "DMP_WORKSPACE_ROOT": "${workspaceFolder}",
        "AIRFLOW_URL": "http://localhost:8080",
        "AIRFLOW_USER": "airflow",
        "AIRFLOW_PASSWORD": "airflow"
      }
    },
    "airflow-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "${AIRFLOW_MCP_PATH}", "run", "airflow-mcp"],
      "description": "Airflow DAG management and E2E testing",
      "env": {
        "AIRFLOW_URL": "http://localhost:8080",
        "AIRFLOW_USER": "airflow",
        "AIRFLOW_PASSWORD": "airflow",
        "S3_ENDPOINT": "http://localhost:4566",
        "S3_BUCKET": "dmp-data"
      }
    },
    "quote2contract-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "${Q2C_MCP_PATH}", "run", "quote2contract-mcp"],
      "description": "Q2C application lifecycle and database management",
      "env": {
        "Q2C_DIR": "${Q2C_PROJECT_PATH}",
        "JAVA_HOME": "${JAVA_HOME}"
      }
    }
  }
}
```

### Agent Workflow: Implementation

```
1. User says: "Help me implement task 2 of TICKET-123"

2. Agent calls MCP: get_task_details(TICKET-123, 2)

3. MCP returns:
   - Task: "Create SignalDeduplicator class"
   - Code refs: signal_processor.py, signal.py
   - Implementation hints from ticket description

4. Agent proceeds with full context awareness
```

### Agent Workflow: Test Execution

```
1. User says: "Run the tests for TICKET-123"

2. Agent calls v0agent: get_test_plan(TICKET-123)
   Returns: 3 unit tests, 1 integration test, acceptance criteria

3. Agent calls v0agent: execute_test_plan(TICKET-123)
   Internally orchestrates:
   - dmp-dev-tools: run_pytest_for_transform (unit tests)
   - airflow-mcp: run_e2e_rxclaims_test (integration test)
   - airflow-mcp: verify_e2e_test_output (validation)

4. Agent receives aggregated results:
   - 2 passed, 1 failed, 1 skipped
   - Acceptance criteria: 2/3 verified

5. User says: "Debug the failed test"

6. Agent calls v0agent: debug_failed_test(TICKET-123, test_id)
   Internally orchestrates:
   - airflow-mcp: get_task_logs
   - dmp-dev-tools: explain_dag_error
   
7. Agent returns:
   - Root cause: "Column 'member_id' not found in input"
   - Suggested fix: "Add member_id to column_mapping config"
   - Debug notebook created at: tests/debug_ticket_123.ipynb
```

### Agent Workflow: Environment Setup

```
1. User says: "Setup my environment for TICKET-456"

2. Agent calls v0agent: setup_ticket_environment(TICKET-456)
   Internally orchestrates:
   - dmp-dev-tools: check_local_environment
   - dmp-dev-tools: setup_local_venv (if needed)
   - dmp-dev-tools: discover_pipeline_schema
   - quote2contract-mcp: q2c_seed_test_data

3. Agent returns:
   - Environment ready: true
   - Venv: /path/to/.venv
   - Test data loaded: 1000 records
   - Schema: {input_columns: [...], output_columns: [...]}
   - Next steps:
     1. Run `source .venv/bin/activate`
     2. Start with task 1: "Implement column mapping"
     3. Test data available in Q2C database
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

### New Table: `test_cases`

```sql
CREATE TABLE test_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT CHECK (type IN ('unit', 'integration', 'e2e', 'manual')),
    status TEXT DEFAULT 'not_run' CHECK (status IN ('not_run', 'passed', 'failed', 'skipped')),
    file_path TEXT,
    linked_tasks INTEGER[],  -- Array of task indices
    linked_criteria UUID[],  -- Array of acceptance criteria IDs
    last_run TIMESTAMP,
    run_details JSONB,  -- Error messages, duration, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_test_cases_ticket ON test_cases(ticket_id);
CREATE INDEX idx_test_cases_status ON test_cases(status);
```

### New Table: `acceptance_criteria`

```sql
CREATE TABLE acceptance_criteria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT DEFAULT 'should' CHECK (priority IN ('must', 'should', 'could')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'blocked')),
    verification_method TEXT CHECK (verification_method IN ('automated', 'manual', 'review')),
    created_at TIMESTAMP DEFAULT NOW(),
    verified_at TIMESTAMP
);

CREATE INDEX idx_acceptance_criteria_ticket ON acceptance_criteria(ticket_id);
```

### New Column on `tickets`

```sql
ALTER TABLE tickets ADD COLUMN task_metadata JSONB DEFAULT '{}';
-- Stores AI-extracted metadata per task

ALTER TABLE tickets ADD COLUMN test_plan JSONB DEFAULT '{}';
-- Stores test plan configuration (coverage target, etc.)
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

### Phase 4: Test Plan Integration (Week 4)
- [ ] Create `test_cases` and `acceptance_criteria` tables
- [ ] Implement `get_test_plan` MCP tool
- [ ] Implement `list_test_cases` MCP tool
- [ ] Implement `get_acceptance_criteria` MCP tool
- [ ] Implement `update_test_status` MCP tool
- [ ] Implement `generate_test_scaffold` MCP tool
- [ ] Add test case <-> acceptance criteria linking

### Phase 5: External MCP Tool Integration (Week 5)
- [ ] Configure external MCP server connections (dmp-dev-tools, airflow-mcp, quote2contract-mcp)
- [ ] Implement `execute_test_plan` orchestration tool
  - [ ] Route unit tests to `run_pytest_for_transform`
  - [ ] Route integration tests to `run_e2e_rxclaims_test`
  - [ ] Aggregate results and update test_cases table
- [ ] Implement `debug_failed_test` orchestration tool
  - [ ] Call `get_task_logs` and `explain_dag_error`
  - [ ] Generate debug notebooks
- [ ] Implement `setup_ticket_environment` orchestration tool
  - [ ] Check/setup Python environment
  - [ ] Seed test data via quote2contract-mcp
  - [ ] Discover pipeline schemas
- [ ] Add external tool health checks to v0agent startup

### Phase 6: Agent Bus Integration (Week 6)
- [ ] Define `TicketTaskMessage` type
- [ ] Define `TestExecutionMessage` type for test orchestration
- [ ] Create task executor agent skeleton
- [ ] Wire up MCP → Agent Bus communication
- [ ] Add task status updates via bus
- [ ] Add test result notifications via bus

### Phase 7: VS Code Integration (Week 7)
- [ ] Create MCP server manifest with all servers
- [ ] Test with Copilot/Claude agents
- [ ] Document agent workflows
- [ ] Test plan workflow: agent can generate, run, and report test status
- [ ] Debug workflow: agent can investigate and fix failed tests
- [ ] Environment setup workflow: agent can prepare workspace for ticket

---

## API Endpoints

### REST API

```
# Ticket Context
GET  /api/tickets/{ticket_id}/context
     Returns full ticket with task details

GET  /api/tickets/{ticket_id}/tasks/{index}
     Returns specific task with code references

POST /api/tickets/{ticket_id}/tasks/{index}/refs
     AI extracts and stores code references

PUT  /api/tickets/{ticket_id}/tasks/{index}/status
     Update task completion status

# Test Plan
GET  /api/tickets/{ticket_id}/test-plan
     Returns complete test plan with all test cases

GET  /api/tickets/{ticket_id}/test-cases
     List all test cases (supports ?status=failed&type=unit filters)

POST /api/tickets/{ticket_id}/test-cases
     Create a new test case for the ticket

PUT  /api/tickets/{ticket_id}/test-cases/{case_id}
     Update test case (status, details)

GET  /api/tickets/{ticket_id}/acceptance-criteria
     List acceptance criteria with linked tests

POST /api/tickets/{ticket_id}/acceptance-criteria
     Create new acceptance criteria

POST /api/tickets/{ticket_id}/generate-tests
     AI generates test scaffold for ticket tasks

# MCP
POST /api/mcp/call
     MCP tool invocation endpoint (existing)
```

---

## Security Considerations

1. **MCP Authentication**: Use existing bypass token or session auth
2. **Code Reference Access**: Only return file paths, not actual code content
3. **Task Updates**: Audit log all status changes
4. **External MCP Tools**: Validate tool names before routing to external servers
5. **Environment Variables**: Never expose credentials through MCP responses

---

## Success Metrics

1. CLI: User can get task context in < 2 seconds
2. MCP: Agents can retrieve task details in single call
3. Code Refs: 80%+ accuracy on class/method extraction
4. Test Plan: Agents can generate test scaffolds from tickets
5. Test Status: 95%+ of test runs update status automatically
6. Integration: End-to-end flow works in VS Code
7. External Tools: Successfully route 90%+ of test executions to appropriate MCP server
8. Debug Flow: Agents can analyze failures and suggest fixes in < 30 seconds
9. Environment Setup: Full environment ready in < 2 minutes

---

## Test Plan Workflow Example

```
1. User creates ticket with acceptance criteria in description
   "Must handle empty input gracefully"
   "Should process within 100ms"

2. AI extracts acceptance criteria → acceptance_criteria table

3. User says: "Generate tests for TICKET-123"

4. Agent calls: get_acceptance_criteria(TICKET-123)
   → Returns criteria needing test coverage

5. Agent calls: generate_test_scaffold(TICKET-123, task_index=0, type="unit")
   → Returns pytest scaffold with test functions for each criterion

6. User runs tests: pytest tests/test_ticket_123.py

7. Agent calls: update_test_status(TICKET-123, test_id, "passed")
   → Updates test case and linked acceptance criteria status

8. Agent calls: get_test_plan(TICKET-123)
   → Shows coverage: 2/3 criteria verified, 1 test failing
```

## Automated Test Execution Example

```
1. User says: "Run all tests for TICKET-456"

2. Agent calls: execute_test_plan(TICKET-456)
   
3. v0agent orchestrates:
   a. get_test_plan(TICKET-456) → 2 unit, 1 integration test
   b. check_local_environment → all packages available
   c. For unit tests: dmp-dev-tools.run_pytest_for_transform
   d. For integration: airflow-mcp.run_e2e_rxclaims_test
   e. Verify outputs: airflow-mcp.verify_e2e_test_output
   f. Update test_cases table with results

4. Agent returns summary:
   {
     "passed": 2,
     "failed": 1,
     "acceptance_criteria": {
       "verified": 2,
       "pending": 1
     }
   }

5. User says: "Why did test_column_mapping fail?"

6. Agent calls: debug_failed_test(TICKET-456, "test_column_mapping")

7. v0agent orchestrates:
   a. Get test details from test_cases table
   b. airflow-mcp.get_task_logs(dag_id, run_id, task_id)
   c. dmp-dev-tools.explain_dag_error(dag_id, run_id)

8. Agent returns:
   {
     "error_type": "KeyError",
     "root_cause": "Column 'member_id' missing from mapping",
     "suggested_fixes": [
       "Add 'member_id': 'MemberID' to column_mapping config",
       "Check source file header row for column names"
     ],
     "debug_notebook": "tests/debug_ticket_456.ipynb"
   }
```

---

## Related Files

- `scripts/dev_cli.py` - CLI implementation
- `src/app/mcp/tools.py` - MCP tool definitions
- `src/app/mcp/registry.py` - Tool registration
- `src/app/infrastructure/agent_bus.py` - Message bus
- `src/app/services/tickets_supabase.py` - Ticket service
- `src/app/services/test_plan_service.py` - Test plan service (new)
- `src/app/services/external_mcp_orchestrator.py` - External MCP tool routing (new)

## External MCP Tool Configuration

### ringlinq-mcp Setup

The external MCP tools are located in the `ringlinq-mcp` repository:

```
ringlinq-mcp/
├── mcp.json                 # Combined MCP configuration
├── SETUP-GUIDE.md           # Installation instructions
├── PIPELINE-GUIDE.md        # Pipeline testing guide
├── dmp-dev-tools/           # Developer tools server
│   ├── server.py
│   └── pyproject.toml
├── airflow-mcp/             # Airflow DAG management
│   ├── server.py
│   └── pyproject.toml
└── quote2contract-mcp/      # Q2C application tools
    ├── server.py
    └── pyproject.toml
```

### Environment Variables Required

```bash
# dmp-dev-tools
export DMP_WORKSPACE_ROOT="/path/to/dmp"
export AIRFLOW_URL="http://localhost:8080"
export AIRFLOW_USER="airflow"
export AIRFLOW_PASSWORD="airflow"

# airflow-mcp
export S3_ENDPOINT="http://localhost:4566"
export S3_BUCKET="dmp-data"
export WORKSPACE_ROOT="/path/to/dmp"

# quote2contract-mcp
export Q2C_DIR="/path/to/quote2contract"
export JAVA_HOME="/path/to/java"
```
