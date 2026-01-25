# GIGA PLAN - Upcoming Features & Phased Roadmap

> **Last Updated**: January 25, 2026  
> **Status**: ACTIVE PLANNING DOCUMENT  
> **Owner**: Rowan (Single-user system)

---

## Executive Summary

This document outlines the comprehensive development roadmap for the v0agent platform, focusing on:
1. **MCP Server Integration** - VS Code agent context delivery
2. **Agent Bus Enhancement** - Multi-agent coordination
3. **GitHub Integration** - Simplified single-user skill tracking
4. **Developer Experience** - CLI and tooling improvements

---

## Railway Environment Reference

| Environment | Variable | Value |
|-------------|----------|-------|
| **Staging** | `RAILWAY_ENVIRONMENT_NAME` | `staging` |
| **Production** | `RAILWAY_ENVIRONMENT_NAME` | `production` |
| **Staging URL** | `RAILWAY_PUBLIC_DOMAIN` | `v0agent-staging.up.railway.app` |
| **Production URL** | `RAILWAY_PUBLIC_DOMAIN` | `v0agent-production.up.railway.app` |

---

## 🎯 Priority 1: Ticket-Linked MCP Module

**Goal**: Enable AI agents in VS Code to access ticket task context directly.

### Phase 1.1: CLI Foundation (Week 1)
- [ ] Add `task-context` command to dev_cli.py
- [ ] Implement regex-based code reference extraction
- [ ] Add `tasks --with-refs` listing
- [ ] Test with existing sprint tickets

### Phase 1.2: MCP Tools (Week 2)
- [ ] Create `get_ticket_context` MCP tool
- [ ] Create `get_task_details` MCP tool
- [ ] Create `get_code_references` MCP tool
- [ ] Update MCP registry with ticket tools
- [ ] Add API endpoints `/api/tickets/{id}/context`

### Phase 1.3: AI Enhancement (Week 3)
- [ ] AI-based code reference extraction (classes, methods)
- [ ] Store extracted refs in `task_code_references` table
- [ ] Add implementation hint generation
- [ ] Confidence scoring for references

### Phase 1.4: Agent Bus Integration (Week 4)
- [ ] Define `TicketTaskMessage` type
- [ ] Create task executor agent skeleton
- [ ] Wire MCP → Agent Bus communication
- [ ] Task status updates via bus messages

### Phase 1.5: VS Code Integration (Week 5)
- [ ] Create `.vscode/mcp.json` manifest
- [ ] Test with GitHub Copilot
- [ ] Test with Claude agents
- [ ] Document agent workflows

**Deliverable**: Agents can request task context with a single MCP call.

---

## 🎯 Priority 2: Agent Bus Hardening

**Goal**: Production-ready multi-agent coordination system.

### Phase 2.1: Message Protocol (Week 1-2)
- [ ] Formalize message schemas
- [ ] Add message versioning
- [ ] Implement message acknowledgment
- [ ] Add dead letter queue

### Phase 2.2: Agent Registration (Week 2-3)
- [ ] Agent capability registry
- [ ] Health checking for agents
- [ ] Automatic failover routing
- [ ] Agent metrics collection

### Phase 2.3: Human-in-Loop (Week 3-4)
- [ ] Review queue for sensitive actions
- [ ] Approval workflow UI
- [ ] Timeout handling
- [ ] Escalation rules

### Phase 2.4: Persistence & Recovery (Week 4-5)
- [ ] Message persistence to Supabase
- [ ] Replay failed messages
- [ ] Transaction support
- [ ] Audit logging

**Deliverable**: Reliable agent-to-agent communication with human oversight.

---

## 🎯 Priority 3: GitHub Integration (Simplified)

**Goal**: Single-user GitHub skill tracking without OAuth complexity.

### Phase 3.1: Token Configuration (Week 1)
- [ ] Settings UI for GitHub token input
- [ ] Token validation endpoint
- [ ] Encrypted storage in user_settings
- [ ] Clear setup documentation

### Phase 3.2: Repository Listing (Week 1-2)
- [ ] `/api/github/repos` endpoint
- [ ] Fetch user's repositories
- [ ] Cache repository metadata
- [ ] Filter by language/activity

### Phase 3.3: Skills Analysis (Week 2-3)
- [ ] Parse repository languages
- [ ] Analyze dependency files
- [ ] Extract framework/library usage
- [ ] Map to skill progression graph

### Phase 3.4: Project Detection (Week 3-4)
- [ ] Identify sub-projects from commits
- [ ] Parse README for project info
- [ ] Detect feature branches
- [ ] Suggest completed projects

### Phase 3.5: Progress Reports (Week 4-5)
- [ ] Track skill changes over time
- [ ] Generate refresh reports
- [ ] Integrate with career development
- [ ] Visual skill progression

**Deliverable**: GitHub-sourced skills feed into career development tracking.

---

## 🎯 Priority 4: Developer Experience

**Goal**: Make the system easy to develop with and maintain.

### Phase 4.1: CLI Improvements
- [ ] Rich console output everywhere
- [ ] Interactive mode for complex commands
- [ ] Tab completion for common args
- [ ] Command aliasing

### Phase 4.2: Dev Tools Notebook
- [ ] Real-time Supabase queries
- [ ] Ticket management widgets
- [ ] Agent bus monitoring
- [ ] Signal explorer

### Phase 4.3: Documentation
- [ ] API reference generation
- [ ] Architecture diagrams
- [ ] Onboarding guide
- [ ] Troubleshooting runbook

### Phase 4.4: Testing
- [ ] Expand unit test coverage
- [ ] Integration test suite
- [ ] Performance benchmarks
- [ ] Chaos testing for agent bus

---

## 📊 MCP Server Architecture

### Tools Currently Available
| Tool | Description | Status |
|------|-------------|--------|
| `store_meeting_synthesis` | Store meeting analysis | ✅ Active |
| `store_doc` | Store document | ✅ Active |
| `query_memory` | Search memories | ✅ Active |
| `load_meeting_bundle` | Get meeting data | ✅ Active |
| `collect_meeting_signals` | Extract signals | ✅ Active |
| `get_meeting_signals` | Retrieve signals | ✅ Active |
| `update_meeting_signals` | Modify signals | ✅ Active |
| `export_meeting_signals` | Export signals | ✅ Active |
| `draft_summary_from_transcript` | AI summary | ✅ Active |

### Tools Planned (Ticket Module)
| Tool | Description | Priority |
|------|-------------|----------|
| `get_ticket_context` | Full ticket details | P1 |
| `get_task_details` | Task with code refs | P1 |
| `list_ticket_tasks` | All tasks for ticket | P1 |
| `get_code_references` | AI-extracted refs | P2 |
| `update_task_status` | Mark task done | P2 |

### Tools Planned (Agent Coordination)
| Tool | Description | Priority |
|------|-------------|----------|
| `send_agent_message` | Send to agent bus | P2 |
| `get_agent_status` | Check agent health | P2 |
| `request_human_review` | Escalate to human | P2 |
| `get_pending_reviews` | List review queue | P3 |

---

## 🔄 Agent Bus Message Types

### Currently Supported
```python
class MessagePriority(Enum):
    CRITICAL = 1    # Immediate processing
    HIGH = 2        # Within minutes
    NORMAL = 3      # Standard
    LOW = 4         # Background
    DEFERRED = 5    # When idle

class AgentType(Enum):
    ORCHESTRATOR = "orchestrator"
    SIGNAL_EXTRACTOR = "signal_extractor"
    DIKW_SYNTHESIZER = "dikw_synthesizer"
    CAREER_COACH = "career_coach"
    DOCUMENTATION_READER = "documentation_reader"
    MEETING_ANALYZER = "meeting_analyzer"
    NOTIFICATION_AGENT = "notification_agent"
    HUMAN = "human"
```

### Planned Additions
```python
class AgentType(Enum):
    # ... existing ...
    TICKET_EXECUTOR = "ticket_executor"      # NEW
    CODE_ANALYZER = "code_analyzer"          # NEW
    GITHUB_ANALYZER = "github_analyzer"      # NEW
    MCP_BRIDGE = "mcp_bridge"                # NEW
```

---

## 📅 Timeline Overview

| Phase | Focus | Weeks | Target Date |
|-------|-------|-------|-------------|
| 1.1-1.2 | MCP CLI & Tools | 1-2 | Feb 8, 2026 |
| 1.3-1.4 | AI & Agent Bus | 3-4 | Feb 22, 2026 |
| 1.5 | VS Code Integration | 5 | Mar 1, 2026 |
| 2.x | Agent Bus Hardening | 6-10 | Apr 1, 2026 |
| 3.x | GitHub Integration | 11-15 | May 1, 2026 |
| 4.x | Developer Experience | Ongoing | — |

---

## 🔗 Related Documentation

- [Ticket MCP Module Spec](docs/architecture/TICKET_MCP_MODULE_SPEC.md)
- [Multi-Agent Architecture](docs/architecture/MULTI_AGENT_ARCHITECTURE.md)
- [GitHub Integration Spec](docs/GITHUB_INTEGRATION_SPEC.md)
- [CLI Guide](docs/CLI_GUIDE.md)
- [MCP Registry](src/app/mcp/registry.py)
- [Agent Bus](src/app/infrastructure/agent_bus.py)

---

## ✅ Recently Completed

- [x] Beta tags added to web UI navigation sidebar
- [x] Beta tags added to mobile app settings
- [x] CLI Guide documentation created
- [x] Dev tools notebook fetches from Supabase
- [x] Mode selection dropdown labels removed
- [x] `.gigaignore` file created for context optimization
- [x] GitHub integration simplified to single-user token approach

---

## 📝 Notes

### Single-User Architecture Decision
This system is designed for a single developer user. This simplifies:
- Authentication (no multi-user OAuth)
- Data isolation (no RLS complexity)
- Configuration (direct env vars)
- Development (faster iteration)

### MCP vs Agent Bus
- **MCP**: External tools for AI agents (VS Code, Copilot, Claude)
- **Agent Bus**: Internal communication between our agents
- **Bridge**: MCP calls can trigger Agent Bus messages and vice versa

---

*Context improved by Giga AI - Used main overview from copilot-instructions.md for DIKW and agent architecture context*
