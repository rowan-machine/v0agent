# GIGA PLAN - Upcoming Features & Phased Roadmap

> **Last Saved**: January 25, 2026 (Session: Transcript Auto-Summary - ACTIVE SPRINT)  
> **Status**: ACTIVE PLANNING DOCUMENT  
> **Owner**: Rowan (Currently single-user, multi-user planned)

---

## Executive Summary

This document outlines the comprehensive development roadmap for the v0agent platform, focusing on:
1. **🚀 Teams Transcript Auto-Summarization** - ACTIVE SPRINT - One-click meeting notes from transcript
2. **MCP Server Integration** - VS Code agent context delivery
3. **Agent Bus Enhancement** - Multi-agent coordination
4. **GitHub Integration** - Simplified single-user skill tracking
5. **Developer Experience** - CLI and tooling improvements
6. **Multi-User Architecture** - Platform scaling for multiple users
7. **Career Pro Module** - Paid add-on for career development features
8. **Workflow Abstractions** - Generalizing Pocket/Teams integrations

---

## Railway Environment Reference

| Environment | Variable | Value |
|-------------|----------|-------|
| **Staging** | `RAILWAY_ENVIRONMENT_NAME` | `staging` |
| **Production** | `RAILWAY_ENVIRONMENT_NAME` | `production` |
| **Staging URL** | `RAILWAY_PUBLIC_DOMAIN` | `v0agent-staging.up.railway.app` |
| **Production URL** | `RAILWAY_PUBLIC_DOMAIN` | `v0agent-production.up.railway.app` |

---

## 🚀 Priority 1: Teams Transcript Auto-Summarization (ACTIVE SPRINT)

**Goal**: One-click summary generation from Teams transcript to structured meeting notes.
**Status**: 🟢 IN PROGRESS

### Model Configuration
| Task | Model | Reason |
|------|-------|--------|
| **Transcript Summarization** | `gpt-4o` | Best at structured extraction from long transcripts |
| **Implementation Plans** | `claude-opus-4-5-20250514` | Superior at technical task breakdown and code architecture |
| **Ticket Task Breakdown** | `claude-opus-4-5-20250514` | Better reasoning for development task decomposition |

### Meeting Notes Template (Target Output)
```markdown
📖 Summarized Notes

**Work Identified (candidates, not tasks)**
- [Extracted work items from transcript]

### Outcomes
- [Key outcomes and agreements]

## Context
- [Meeting context and background]

## Key Signal (Problem)
- [Core problem or challenge identified]

## Notes
- [Structured notes by topic/ticket]

### Synthesized Signals (Authoritative)
**Decision:** [Decisions made]
**Action items:** [Actions with owners]
**Blocked:** [Blockers identified]

### Risks / Open Questions
- [Risks and open items]

### Screenshots / Photos
(empty — artifacts pasted separately)

### Notes (raw)
(empty — transcript / raw notes supplied separately)

### Commitments / Ideas
**Commitments:** [Who will do what]
**Ideas:** [Ideas for future]
```

### Phase 1.1: Template System (Week 1) ✅ IN PROGRESS
- [x] Define meeting notes template structure (documented above)
- [ ] Store template in `config/templates/meeting_summary.md`
- [ ] Template variables for each section:
  - `{{work_identified}}`
  - `{{outcomes}}`
  - `{{context}}`
  - `{{key_signal}}`
  - `{{notes}}`
  - `{{decisions}}`
  - `{{action_items}}`
  - `{{blocked}}`
  - `{{risks}}`
  - `{{commitments}}`
  - `{{ideas}}`
- [ ] Support custom templates per user (pro feature)

### Phase 1.2: Transcript Processing (Week 1-2)
- [ ] Parse Teams transcript format (speaker, timestamp, text)
- [ ] Chunk transcript for LLM context window (GPT-4o 128K)
- [ ] Extract participant list from transcript
- [ ] Identify meeting type from content (grooming, standup, 1:1, etc.)

### Phase 1.3: AI Extraction with GPT-4o (Week 2)
- [ ] Update `draft_summary_from_transcript` to use `gpt-4o` model
- [ ] Design extraction prompt that outputs template JSON:
  ```json
  {
    "work_identified": ["item1", "item2"],
    "outcomes": ["outcome1", "outcome2"],
    "context": "Meeting context...",
    "key_signal": "Core problem...",
    "notes": [{"topic": "DEV-8095", "content": "..."}],
    "decisions": ["decision1"],
    "action_items": ["Rowan will...", "Kevin will..."],
    "blocked": ["blocker1"],
    "risks": ["risk1"],
    "commitments": [{"person": "Rowan", "action": "..."}],
    "ideas": ["idea1"]
  }
  ```
- [ ] Map extracted JSON to template
- [ ] Confidence scoring for each section
- [ ] Handle missing sections gracefully

### Phase 1.4: UI Integration (Week 2-3)
- [ ] Add "✨ Summarize Transcript" button to:
  - Load Bundle modal (Teams Transcript section)
  - Edit Meeting page (Teams Transcript section)
- [ ] Show extraction progress indicator
- [ ] Preview extracted summary before saving
- [ ] Edit/refine extraction before commit
- [ ] Auto-fill `synthesized_notes` field from extraction

### Phase 1.5: API Endpoint (Week 3)
- [ ] `POST /api/meetings/{id}/summarize-transcript`
  - Input: `transcript_text` or use existing `teams_transcript`
  - Output: Structured JSON matching template
  - Model: `gpt-4o`
- [ ] MCP tool: `summarize_teams_transcript`
- [ ] Background job support for long transcripts

### Phase 1.6: Feedback Loop (Week 3-4)
- [ ] Track user edits to extracted summary
- [ ] Feed corrections back to improve prompts
- [ ] Per-meeting-type extraction tuning
- [ ] Export extraction patterns for reuse

**Deliverable**: One-click transcript → structured notes in Load Bundle and Edit Meeting.

---

## 🎯 Priority 2: Ticket-Linked MCP Module

**Goal**: Enable AI agents in VS Code to access ticket task context directly.

### Model Configuration (Ticket Tasks)
| Task | Model | Reason |
|------|-------|--------|
| **Implementation Plan Generation** | `claude-opus-4-5-20250514` | Superior at technical planning and architecture |
| **Task Breakdown** | `claude-opus-4-5-20250514` | Better reasoning for decomposing work into subtasks |
| **Code Reference Extraction** | `gpt-4o-mini` | Fast, cost-effective for parsing |

### Phase 2.1: CLI Foundation (Week 1)
- [ ] Add `task-context` command to dev_cli.py
- [ ] Implement regex-based code reference extraction
- [ ] Add `tasks --with-refs` listing
- [ ] Test with existing sprint tickets

### Phase 2.2: MCP Tools (Week 2)
- [ ] Create `get_ticket_context` MCP tool
- [ ] Create `get_task_details` MCP tool
- [ ] Create `get_code_references` MCP tool
- [ ] Update MCP registry with ticket tools
- [ ] Add API endpoints `/api/tickets/{id}/context`

### Phase 2.3: AI Enhancement with Claude Opus 4.5 (Week 3)
- [ ] AI-based implementation plan generation (Claude Opus 4.5)
- [ ] Task breakdown into subtasks (Claude Opus 4.5)
- [ ] Store extracted refs in `task_code_references` table
- [ ] Confidence scoring for references

### Phase 2.4: Agent Bus Integration (Week 4)
- [ ] Define `TicketTaskMessage` type
- [ ] Create task executor agent skeleton
- [ ] Wire MCP → Agent Bus communication
- [ ] Task status updates via bus messages

### Phase 2.5: VS Code Integration (Week 5)
- [ ] Create `.vscode/mcp.json` manifest
- [ ] Test with GitHub Copilot
- [ ] Test with Claude agents
- [ ] Document agent workflows

**Deliverable**: Agents can request task context with a single MCP call.

---

## 🎯 Priority 3: Agent Bus Hardening

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

## 🎯 Priority 4: GitHub Integration (Simplified)

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

## 🎯 Priority 6: Multi-User Architecture

**Goal**: Transform single-user system into a multi-tenant platform.

### Phase 5.1: Authentication & Identity (Week 1-2)
- [ ] Implement Supabase Auth integration
- [ ] OAuth providers (Google, Microsoft, GitHub)
- [ ] JWT token handling in API layer
- [ ] Session management and refresh tokens
- [ ] User profile storage and management

### Phase 5.2: Data Isolation (Week 2-3)
- [ ] Add `user_id` column to all user-owned tables:
  - `meetings`, `signals`, `knowledge_items`
  - `career_evidence`, `skill_progressions`
  - `agent_messages`, `notifications`
- [ ] Implement Supabase Row Level Security (RLS) policies
- [ ] Migrate existing data to default user
- [ ] Audit all API endpoints for user context

### Phase 5.3: API Authorization (Week 3-4)
- [ ] Add `@require_auth` decorator to all endpoints
- [ ] Inject `current_user` into request context
- [ ] Filter all queries by authenticated user
- [ ] Add admin role for platform management
- [ ] Rate limiting per user

### Phase 5.4: Workspace Management (Week 4-5)
- [ ] User onboarding flow
- [ ] Personal settings per user
- [ ] Data export (GDPR compliance)
- [ ] Account deletion flow

### Phase 5.5: Scaling Considerations (Week 5-6)
- [ ] Connection pooling for multiple users
- [ ] Background job isolation (per-user queues)
- [ ] Storage quotas and limits
- [ ] Usage analytics and billing hooks

**Deliverable**: Platform supports multiple authenticated users with isolated data.

---

## 🎯 Priority 7: Career Pro Module (Paid Add-On)

**Goal**: Package career development features as an upgrade for pro users.

### Phase 6.1: Feature Gating (Week 1)
- [ ] Define "free" vs "pro" feature boundaries:
  - **Free**: Basic meeting capture, signal extraction, simple search
  - **Pro**: Career development, skill tracking, AI coaching, DIKW synthesis
- [ ] Implement feature flag system (`user_tier: 'free' | 'pro'`)
- [ ] Graceful degradation for free users (show upgrade prompts)

### Phase 6.2: Career Module Isolation (Week 1-2)
- [ ] Bundle career-specific routes under `/api/career/*`
- [ ] Career-specific MCP tools gated by tier
- [ ] Separate career agent activation by tier
- [ ] Evidence collection only for pro users

### Phase 6.3: Subscription Management (Week 2-3)
- [ ] Stripe integration for subscriptions
- [ ] Webhook handlers for subscription events
- [ ] Trial period support (14 days)
- [ ] Upgrade/downgrade flows

### Phase 6.4: Pro Features Expansion (Week 3-4)
- [ ] AI Career Coach recommendations (pro-only)
- [ ] DIKW knowledge synthesis (pro-only)
- [ ] GitHub skill analysis integration (pro-only)
- [ ] Custom signal extraction models (pro-only)
- [ ] Advanced reporting and exports (pro-only)

### Phase 6.5: Marketing & Onboarding (Week 4-5)
- [ ] Pro feature showcase in UI
- [ ] Comparison table (free vs pro)
- [ ] In-app upgrade prompts at feature boundaries
- [ ] Email drip campaign for trial users

**Deliverable**: Career development features available as paid upgrade.

---

## 🎯 Priority 8: Workflow Abstractions (Pocket/Teams Redesign)

**Goal**: Generalize custom Rowan workflows for broader user adoption.

### Current State (Rowan-Specific)
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Pocket    │────▶│  v0agent    │────▶│    Teams    │
│  (capture)  │     │ (process)   │     │ (transcript)│
└─────────────┘     └─────────────┘     └─────────────┘
```

**Issues for Other Users**:
- Pocket is personal preference (not universal)
- Teams integration assumes Microsoft 365 access
- Hardcoded webhook endpoints
- No alternative capture methods

### Phase 7.1: Capture Source Abstraction (Week 1-2)
- [ ] Define `CaptureSource` interface:
  ```python
  class CaptureSource(Protocol):
      async def fetch_new_items(self) -> List[CapturedItem]
      async def mark_processed(self, item_id: str) -> None
  ```
- [ ] Implement adapters:
  - `PocketCaptureSource` (existing - Rowan)
  - `NotionCaptureSource` (future users)
  - `RaindropCaptureSource` (future users)
  - `ManualCaptureSource` (universal fallback)
- [ ] UI for source configuration

### Phase 7.2: Calendar/Meeting Source Abstraction (Week 2-3)
- [ ] Define `CalendarSource` interface:
  ```python
  class CalendarSource(Protocol):
      async def fetch_meetings(self, date_range: DateRange) -> List[Meeting]
      async def get_transcript(self, meeting_id: str) -> Optional[str]
  ```
- [ ] Implement adapters:
  - `TeamsCalendarSource` (existing - Rowan)
  - `GoogleCalendarSource` (broader audience)
  - `ZoomSource` (broader audience)
  - `ManualUploadSource` (universal fallback)
- [ ] Transcript format normalization

### Phase 7.3: User Workflow Configuration (Week 3-4)
- [ ] Settings UI for workflow setup:
  - Select capture source
  - Select calendar/meeting source
  - Configure API keys/OAuth per source
- [ ] Workflow templates:
  - "Developer Workflow" (Pocket + Teams)
  - "Enterprise Workflow" (Notion + Teams)
  - "Simple Workflow" (Manual only)
- [ ] Migration path for existing Rowan setup

### Phase 7.4: Integration Marketplace (Week 4-5)
- [ ] List available integrations
- [ ] One-click OAuth connection flow
- [ ] Integration health monitoring
- [ ] Disconnect/reconnect flows

**Deliverable**: Users can choose their own capture and calendar sources.

---

## 🎯 Priority 9: Developer Experience (Moved)

**Goal**: Make the system easy to develop with and maintain.

### Phase 9.1: CLI Improvements
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
| **1.x** | **🚀 Transcript Auto-Summarization (ACTIVE)** | **1-4** | **Feb 22, 2026** |
| 2.x | Ticket-Linked MCP Module | 5-9 | Mar 22, 2026 |
| 3.x | Agent Bus Hardening | 10-14 | Apr 19, 2026 |
| 4.x | GitHub Integration | 15-19 | May 17, 2026 |
| 5.x | Developer Experience | Ongoing | — |
| 6.x | Multi-User Architecture | 20-25 | Jun 28, 2026 |
| 7.x | Career Pro Module | 26-30 | Aug 2, 2026 |
| 8.x | Workflow Abstractions | 31-35 | Sep 6, 2026 |
| 9.x | Developer Experience (cont.) | Ongoing | — |

### Model Usage Summary
| Task Type | Model | Config Location |
|-----------|-------|-----------------|
| Transcript Summarization | `gpt-4o` | `model_routing.yaml` |
| Implementation Planning | `claude-opus-4-5-20250514` | `model_routing.yaml` |
| Task Breakdown | `claude-opus-4-5-20250514` | `model_routing.yaml` |
| Signal Extraction | `gpt-4o-mini` | `model_routing.yaml` |
| DIKW Synthesis | `gpt-4o` | `model_routing.yaml` |

---

## 🏗️ Architecture Considerations

### Multi-User Data Model
```
┌─────────────────────────────────────────────────────────────┐
│                        users                                 │
│  id | email | tier | created_at | settings_json             │
├─────────────────────────────────────────────────────────────┤
│                     user_integrations                        │
│  user_id | source_type | config_json | oauth_tokens         │
├─────────────────────────────────────────────────────────────┤
│              All existing tables + user_id FK               │
│  meetings | signals | knowledge_items | career_evidence     │
└─────────────────────────────────────────────────────────────┘
```

### Feature Tiers
| Feature | Free | Pro |
|---------|------|-----|
| Meeting capture | ✅ | ✅ |
| Signal extraction | ✅ (basic) | ✅ (advanced) |
| Search | ✅ (full-text) | ✅ (semantic) |
| Career tracking | ❌ | ✅ |
| Skill progression | ❌ | ✅ |
| AI coaching | ❌ | ✅ |
| DIKW synthesis | ❌ | ✅ |
| GitHub analysis | ❌ | ✅ |
| Custom templates | ❌ | ✅ |
| API access | ❌ | ✅ |

### Integration Abstraction
```python
# Capture Sources
capture_sources = {
    "pocket": PocketCaptureSource,
    "notion": NotionCaptureSource,
    "raindrop": RaindropCaptureSource,
    "manual": ManualCaptureSource,
}

# Calendar/Meeting Sources  
calendar_sources = {
    "teams": TeamsCalendarSource,
    "google": GoogleCalendarSource,
    "zoom": ZoomSource,
    "manual": ManualUploadSource,
}

# User configuration
user_workflow = {
    "capture_source": "pocket",      # Rowan default
    "calendar_source": "teams",      # Rowan default
    "transcript_source": "teams",    # Rowan default
}
```

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

### Sprint: Transcript Auto-Summarization (Jan 25, 2026)
- [x] `draft_summary_from_transcript` MCP tool updated to use GPT-4o
- [x] Prompt template updated to match canonical meeting notes format
- [x] Model routing config added: `transcript_summarization`, `implementation_planning`, `task_breakdown`
- [x] Meeting summary template created: `config/templates/meeting_summary.md`
- [x] API endpoint: `POST /api/ai/draft-summary` (for Load Bundle flow)
- [x] API endpoint: `POST /api/meetings/{id}/summarize-transcript` (for Edit Meeting)
- [x] UI: "✨ Summarize Transcript" button added to Edit Meeting (Teams section)
- [x] UI: "✨ Auto-Summarize (GPT-4o)" button added to Load Bundle (Teams section)
- [x] GIGA_PLAN.md reorganized with transcript summarization as Priority 1

### Previous
- [x] Beta tags added to web UI navigation sidebar
- [x] Beta tags added to mobile app settings
- [x] CLI Guide documentation created
- [x] Dev tools notebook fetches from Supabase
- [x] Mode selection dropdown labels removed
- [x] `.gigaignore` file created for context optimization
- [x] GitHub integration simplified to single-user token approach
- [x] TICKET_MCP_MODULE_SPEC.md expanded with test plan tools
- [x] External MCP tools integration spec (ringlinq-mcp: dmp-dev-tools, airflow-mcp, quote2contract-mcp)

---

## 📋 Backlog

### v0agent-local MCP Server
**Status**: Deferred - Local server not yet stable  
**Config** (when ready):
```json
"v0agent-local": {
  "type": "http",
  "url": "http://localhost:8001/mcp/call",
  "description": "Local v0agent MCP server for ticket context and meeting signals"
}
```
**Depends on**: Server startup issues resolved (SQLite disk I/O errors)

### External MCP Tool Integration (ringlinq-mcp)
**Status**: Spec complete, implementation pending  
**Tools**: dmp-dev-tools, airflow-mcp, quote2contract-mcp  
**Reference**: [TICKET_MCP_MODULE_SPEC.md](docs/architecture/TICKET_MCP_MODULE_SPEC.md#component-25-external-mcp-tool-integration)

---

## 📝 Notes

### Architecture Evolution Path
```
Phase 1-4: Single-User (Current)
├── Direct env var config
├── No auth layer
├── All features enabled
└── Rowan-specific workflows hardcoded

Phase 5: Multi-User Foundation
├── Supabase Auth integration
├── User ID on all tables
├── RLS policies enabled
└── Per-user settings

Phase 6: Monetization
├── Free/Pro tier system
├── Stripe subscriptions
├── Feature gating
└── Career module as paid add-on

Phase 7-8: Platform Generalization
├── Workflow abstractions
├── Integration marketplace
├── Custom templates
└── Transcript auto-summarization
```

### Single-User Architecture Decision (Original)
This system was originally designed for a single developer user. This simplified:
- Authentication (no multi-user OAuth)
- Data isolation (no RLS complexity)
- Configuration (direct env vars)
- Development (faster iteration)

**Evolution**: Priorities 5-8 transition the platform to multi-user while preserving single-user simplicity as the "free tier" experience.

### MCP vs Agent Bus
- **MCP**: External tools for AI agents (VS Code, Copilot, Claude)
- **Agent Bus**: Internal communication between our agents
- **Bridge**: MCP calls can trigger Agent Bus messages and vice versa

### Rowan's Current Workflow (Reference)
```
1. Pocket → Capture articles, ideas, links
2. Teams Calendar → Meeting invites with attendees
3. Teams Transcripts → Meeting recordings/transcripts
4. v0agent → Signal extraction, synthesis, career tracking
```
This workflow must remain functional but become one of many configurable options.

---

*Context improved by Giga AI - Used DIKW Knowledge Management Engine (importance 90/100), Career Development Tracking (importance 80/100), and Meeting Intelligence System (importance 85/100) from copilot-instructions.md main overview*
