# V0Agent Refactoring Tracker

> **Last Updated**: 2026-01-27 (Phase 2.4 Complete + Signals Domain)
> **Status**: 10 Domains with 189 total routes - Career, Signals fully migrated

## Current Focus

1. **Repository Pattern Implementation** ✅ - 11 repositories created
2. **Backward Compatibility Removed** ✅ - meetings_supabase, documents_supabase, tickets_supabase aliases removed
3. **Service Naming Migration** ✅ - All 62+ usages migrated to meeting_service, document_service, ticket_service
4. **Career Domain Decomposition** ✅ - 11 API modules (68 routes)
5. **DIKW Domain Decomposition** ✅ - Split into 4 API modules + services (20 routes)
6. **Meetings Domain** ✅ - 17 routes at /api/domains/meetings/*
7. **Tickets Domain** ✅ - 12 routes at /api/domains/tickets/*
8. **Documents Domain** ✅ - 9 routes at /api/domains/documents/*
9. **Arjuna Agent Decomposition** ✅ - 11 modules (~1900 lines)
10. **dikw_synthesizer Agent Package** ✅ - Full decomposition into 5 modules
11. **meeting_analyzer Agent Package** ✅ - Full decomposition into 5 modules
12. **Workflow Domain** ✅ - 18 routes (modes, progress, timer, jobs, tracing)
13. **Dashboard Domain** ✅ - 3 routes (quick_ask, highlights, context)
14. **Search Domain** ✅ - 10 routes (semantic, hybrid, unified, mindmap)
15. **Signals Domain** ✅ - 13 routes (browse, extraction, learning)
16. **Assistant Domain** ✅ - 19 routes

---

## Recent Accomplishments (2026-01-27 Phase 2.8)

### Agent Package Decomposition
Two major agents converted to modular package structure with full backward compatibility:

#### dikw_synthesizer Package (`agents/dikw_synthesizer/`)
| File | Lines | Purpose |
|------|-------|---------|
| `constants.py` | 101 | DIKW_LEVELS, prompts, level descriptions, mapping dicts |
| `agent.py` | 564 | DIKWSynthesizerAgent class with action handlers |
| `visualization.py` | 147 | build_mindmap_tree, build_graph_data, build_tag_clusters |
| `adapters.py` | 460 | Backward-compatible adapter functions for main.py |
| `__init__.py` | 92 | Re-exports all public API |

#### meeting_analyzer Package (`agents/meeting_analyzer/`)
| File | Lines | Purpose |
|------|-------|---------|
| `constants.py` | 133 | SIGNAL_TYPES, HEADING_PATTERNS, HEADING_TO_SIGNAL_TYPE |
| `parser.py` | 121 | parse_adaptive(), detect_heading() |
| `extractor.py` | 328 | extract_signals_from_sections(), merge_signals(), deduplicate_signals() |
| `agent.py` | 261 | MeetingAnalyzerAgent class with AI enhancement |
| `adapters.py` | 131 | get_meeting_analyzer(), parse_meeting_summary_adaptive() |
| `__init__.py` | 86 | Re-exports all public API |

### New Domain Extractions

#### Workflow Domain (`domains/workflow/`)
- **18 routes** extracted from main.py
- **5 sub-modules**: modes.py, progress.py, timer.py, jobs.py, tracing.py
- Handles: workflow mode settings, timer sessions, background jobs, tracing status

#### Dashboard Domain (`domains/dashboard/`)
- **4 routes** extracted from main.py (~250 lines removed)
- **3 sub-modules**: quick_ask.py, highlights.py, context.py
- Handles: AI quick questions, smart coaching highlights (8 sources), drill-down context

### App Route Summary (Post Phase 2.8)
- **Total routes**: 458
- **Domain routes**: 107 (career: 27, dikw: 20, meetings: 17, tickets: 12, documents: 9, workflow: 18, dashboard: 4)
- **Legacy main.py**: Significantly reduced

---

## Recent Accomplishments (2026-01-27)

### Major Milestone: main.py Route Extraction
- **Before**: 450 routes in main.py
- **After**: 32 routes in main.py (93% reduction!)
- **Route Distribution**:
  - Domain routers: 85 routes (career: 27, dikw: 20, meetings: 17, tickets: 12, documents: 9)
  - API routers: ~333 routes (career.py: 64, workflow.py: 18, dikw.py: 16, etc.)
  - Main.py remaining: 32 routes (health, auth, page renders, dashboard APIs)

### Service Naming Migration
| Old Name | New Name | Files Updated |
|----------|----------|---------------|
| meetings_supabase | meeting_service | main.py, search.py, routes.py, action_items.py, transcripts.py, background_jobs.py, reports.py, pocket.py |
| documents_supabase | document_service | main.py, search.py, routes.py, pocket.py |
| tickets_supabase | ticket_service | main.py, career.py, reports.py, background_jobs.py |

### Arjuna Agent Decomposition
- Created `agents/arjuna/` package with `__init__.py`
- Extracted `constants.py` (130 lines): AVAILABLE_MODELS, SYSTEM_PAGES, MODEL_ALIASES, FOCUS_KEYWORDS
- Renamed `arjuna.py` → `_arjuna_core.py` to avoid circular imports
- Core file reduced from 2573 → 2466 lines
- Full backward compatibility maintained through re-exports

### Domain-Driven Design Progress
| Task | Status | Details |
|------|--------|---------|
| Create shared/ folder | ✅ DONE | repositories/, infrastructure/, services/, config/, utils/ |
| Remove backward compat | ✅ DONE | Removed _supabase naming convention aliases |
| Career domain structure | ✅ DONE | domains/career/ with api/, services/, constants.py |
| DIKW domain structure | ✅ DONE | domains/dikw/ with api/, services/, constants.py |
| Meetings domain structure | ✅ DONE | domains/meetings/ with api/, services/ |
| Tickets domain structure | ✅ DONE | domains/tickets/ with api/, services/ |
| Documents domain structure | ✅ DONE | domains/documents/ with api/, services/ |

### Repository Pattern Status
| Repository | Status | Table Coverage |
|------------|--------|----------------|
| MeetingRepository | ✅ DONE | meetings |
| DocumentRepository | ✅ DONE | documents |
| TicketRepository | ✅ DONE | tickets |
| SignalRepository | ✅ DONE | signal_status |
| SettingsRepository | ✅ DONE | settings, shortcuts |
| AIMemoryRepository | ✅ DONE | ai_memory |
| AgentMessagesRepository | ✅ DONE | agent_messages |
| MindmapRepository | ✅ DONE | conversation_mindmaps |
| NotificationsRepository | ✅ DONE | notifications |
| CareerRepository | ✅ DONE | career_*, skills, standups |
| DIKWRepository | ✅ DONE | dikw_items, dikw_evolution |

---

## Guiding Principles

### Zen of Python Applied
- **Explicit is better than implicit** - Clear interfaces, no magic
- **Simple is better than complex** - Single responsibility per module
- **Flat is better than nested** - Shallow import hierarchies
- **Readability counts** - Self-documenting code with clear names
- **There should be one obvious way** - Consistent patterns throughout
- **Namespaces are a honking great idea** - Proper module boundaries

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| **Modules** | snake_case, singular nouns for entities | `meeting.py`, `ticket.py` |
| **Packages** | snake_case, plural or domain names | `meetings/`, `career/` |
| **Classes** | PascalCase | `MeetingService`, `TicketRepository` |
| **Interfaces/Protocols** | PascalCase with descriptive suffix | `MeetingRepository`, `EmbeddingProvider` |
| **Functions** | snake_case, verb_noun | `get_meeting()`, `create_ticket()` |
| **Constants** | SCREAMING_SNAKE_CASE | `DEFAULT_LIMIT`, `MAX_RETRIES` |
| **Private** | Leading underscore | `_parse_signals()`, `_client` |

### Target Architecture (Updated 2026-01-27)

```
src/
└── app/
    ├── core/                    # Domain layer (pure business logic)
    │   ├── domain/              # Domain models (dataclasses)
    │   │   └── models.py        # ✅ All domain models
    │   └── ports/               # Interfaces (Protocols)
    │       ├── protocols.py     # ✅ Repository/Service protocols
    │       └── __init__.py
    │
    ├── domains/                 # ✅ NEW: Bounded contexts (domain-driven)
    │   ├── career/              # Career bounded context
    │   │   ├── api/             # HTTP route handlers
    │   │   │   ├── __init__.py  # Aggregates sub-routers
    │   │   │   ├── profile.py
    │   │   │   ├── skills.py
    │   │   │   ├── standups.py
    │   │   │   ├── suggestions.py
    │   │   │   ├── memories.py
    │   │   │   ├── code_locker.py
    │   │   │   └── chat.py
    │   │   ├── services/        # Business logic
    │   │   │   ├── standup_service.py
    │   │   │   └── suggestion_service.py
    │   │   └── constants.py
    │   │
    │   └── dikw/                # DIKW bounded context
    │       ├── api/
    │       │   ├── __init__.py
    │       │   ├── items.py
    │       │   ├── relationships.py
    │       │   ├── synthesis.py
    │       │   └── promotion.py
    │       ├── services/
    │       │   ├── synthesis_service.py
    │       │   └── promotion_service.py
    │       └── constants.py
    │
    ├── repositories/            # ✅ Data access layer
    │   ├── __init__.py          # Factory functions (get_*_repository)
    │   ├── meeting_repository.py
    │   ├── document_repository.py
    │   ├── ticket_repository.py
    │   ├── signal_repository.py
    │   ├── settings_repository.py
    │   ├── ai_memory_repository.py
    │   ├── agent_messages_repository.py
    │   ├── mindmap_repository.py
    │   ├── notifications_repository.py
    │   ├── career_repository.py
    │   └── dikw_repository.py
    │
    ├── shared/                  # ✅ NEW: Cross-cutting concerns
    │   ├── repositories/        # Re-exports from repositories/
    │   ├── infrastructure/      # Clients (supabase, etc.)
    │   ├── services/            # Shared services
    │   ├── config/              # Configuration helpers
    │   └── utils/               # Utility functions
    │
    ├── services/                # Application services (legacy, migrating)
    │   ├── meeting_service.py
    │   ├── document_service.py
    │   ├── ticket_service.py
    │   └── signal_learning.py
    │
    ├── api/                     # API layer (HTTP handlers)
    │   ├── v1/                  # Versioned API routes
    │   ├── mobile/              # Mobile sync endpoints
    │   ├── career.py            # ⚠️ DEPRECATED → domains/career/
    │   ├── dikw.py              # ⚠️ DEPRECATED → domains/dikw/
    │   └── ...                  # Other routes (to be migrated)
    │
    ├── agents/                  # AI Agents
    │   ├── base.py
    │   ├── arjuna.py
    │   ├── career_coach.py
    │   ├── dikw_synthesizer.py
    │   └── ticket_agent.py
    │
    ├── infrastructure/          # External service clients
    │   ├── supabase_client.py
    │   └── ...
    │
    ├── mcp/                     # MCP Server (for agent tools)
    │   ├── server.py
    │   └── tools.py
    │
    └── main.py                  # FastAPI app entry point
```

**Route Mounting:**
- Legacy routes: `/api/*` (from api/*.py)
- Domain routes: `/api/domains/career/*`, `/api/domains/dikw/*`
- Versioned API: `/api/v1/*`
- Mobile API: `/api/mobile/*`

---

## Phase 1: Foundation (Current)

### 1.1 Create Domain Models with Dataclasses
| File | Status | Notes |
|------|--------|-------|
| `core/domain/models.py` | ✅ DONE | All models: Meeting, Signal, Document, Ticket, DIKWItem, Career*, Notification |
| `core/domain/__init__.py` | ✅ DONE | Clean exports for all domain models |

### 1.2 Create Protocol-based Interfaces
| File | Status | Notes |
|------|--------|-------|
| `core/ports/protocols.py` | ✅ DONE | All protocols: Database, Repositories, Services |
| `core/ports/__init__.py` | ✅ DONE | Exports both new Protocols and legacy ABC (deprecated) |
| `core/ports/external.py` | ⬜ TODO | PocketClient, StorageProvider |

### 1.3 Update Existing Adapters
| File | Status | Notes |
|------|--------|-------|
| `adapters/database/supabase.py` | ⬜ TODO | Implement repository protocols |
| `adapters/embedding/openai.py` | ⬜ TODO | Implement embedding protocol |
| `adapters/storage/supabase.py` | ⬜ TODO | Implement storage protocol |

**Note**: Phase 1.3 was skipped during initial development. The repository pattern was implemented directly in `repositories/` without the formal adapter layer. Consider consolidating infrastructure code into adapters/ folder in a future cleanup phase.

---

## Phase 2: Decompose Large Files

### 2.1 main.py (4858 lines) → Application Layer
| Extract To | Status | Lines | Description |
|------------|--------|-------|-------------|
| `api/dikw.py` | ✅ DONE | ~400 | DIKW CRUD, promotion, merge, validation |
| `api/mindmap.py` | ✅ DONE | ~350 | Mindmap visualization, synthesis |
| `api/notifications.py` | ✅ DONE | ~150 | Notification routes |
| `api/workflow.py` | ✅ DONE | ~600 | Workflow modes, timer, background jobs |
| `api/reports.py` | ✅ DONE | ~550 | Reports, analytics, burndown |
| `api/evaluations.py` | ✅ DONE | ~250 | LangSmith evaluations |
| `api/pocket.py` | ✅ DONE | ~400 | Pocket integration routes |
| `api/routes/dashboard.py` | ⬜ TODO | ~300 | Dashboard routes |
| `application/startup.py` | ⬜ TODO | ~100 | App initialization |

**Progress: ~2700 lines extracted (~55% of main.py)**

### 2.2 career.py (2947 lines) → Career Domain
| Extract To | Status | Lines | Description |
|------------|--------|-------|-------------|
| `domains/career/api/profile.py` | ✅ DONE | ~80 | Profile management |
| `domains/career/api/skills.py` | ✅ DONE | ~60 | Skill tracking |
| `domains/career/api/standups.py` | ✅ DONE | ~110 | Standup updates |
| `domains/career/api/suggestions.py` | ✅ DONE | ~80 | AI suggestions |
| `domains/career/api/memories.py` | ✅ DONE | ~90 | Career memories |
| `domains/career/api/code_locker.py` | ✅ DONE | ~80 | Code storage |
| `domains/career/api/chat.py` | ✅ DONE | ~70 | Chat/tweaks |
| `domains/career/services/standup_service.py` | ✅ DONE | ~50 | Standup analysis |
| `domains/career/services/suggestion_service.py` | ✅ DONE | ~80 | Suggestion generation |

**Note**: New domain structure uses CareerRepository. Original career.py is deprecated - new domains wired to main.py at `/api/domains/career/*`.

### 2.2b dikw.py (644 lines) → DIKW Domain  
| Extract To | Status | Lines | Description |
|------------|--------|-------|-------------|
| `domains/dikw/api/items.py` | ✅ DONE | ~170 | CRUD operations |
| `domains/dikw/api/relationships.py` | ✅ DONE | ~55 | Placeholder (needs repo support) |
| `domains/dikw/api/synthesis.py` | ✅ DONE | ~150 | AI synthesis operations |
| `domains/dikw/api/promotion.py` | ✅ DONE | ~290 | Level promotion, merge, validate |
| `domains/dikw/services/synthesis_service.py` | ✅ DONE | ~100 | Knowledge synthesis logic |
| `domains/dikw/services/promotion_service.py` | ✅ DONE | ~120 | Promotion readiness calculation |
| `domains/dikw/constants.py` | ✅ DONE | ~40 | Tiers, thresholds, types |

**Note**: Uses DIKWRepository. Original dikw.py is deprecated - new domains wired to main.py at `/api/domains/dikw/*`.

### 2.2c Domain Router Wiring ✅ COMPLETE
| Task | Status | Details |
|------|--------|---------|
| Career domain aggregator | ✅ DONE | `domains/career/api/__init__.py` combines all sub-routers |
| DIKW domain aggregator | ✅ DONE | `domains/dikw/api/__init__.py` combines all sub-routers |
| Meetings domain | ✅ DONE | `domains/meetings/api/__init__.py` - 17 routes |
| Tickets domain | ✅ DONE | `domains/tickets/api/__init__.py` - 12 routes |
| Documents domain | ✅ DONE | `domains/documents/api/__init__.py` - 9 routes |
| Import to main.py | ✅ DONE | All 5 domain routers imported |
| Mount domain routers | ✅ DONE | Mounted at `/api/domains/*` |
| Deprecate legacy files | ✅ DONE | Warnings added to `api/career.py` and `api/dikw.py` |

**Domain Summary (5 domains, 85 routes total):**
- `/api/domains/career/*` - 27 routes (profile, skills, standups, suggestions, memories, code_locker, chat)
- `/api/domains/dikw/*` - 20 routes (items, relationships, synthesis, promotion)
- `/api/domains/meetings/*` - 17 routes (crud, search, signals, transcripts)
- `/api/domains/tickets/*` - 12 routes (crud, sprints)
- `/api/domains/documents/*` - 9 routes (crud, search)

### 2.3 arjuna.py (2573 lines) → Agent System ✅ COMPLETE
| Extract To | Status | Lines | Description |
|------------|--------|-------|-------------|
| `agents/arjuna/constants.py` | ✅ DONE | ~130 | AVAILABLE_MODELS, SYSTEM_PAGES, MODEL_ALIASES, FOCUS_KEYWORDS |
| `agents/arjuna/context.py` | ✅ DONE | ~150 | ArjunaContextMixin - Context gathering |
| `agents/arjuna/focus.py` | ✅ DONE | ~120 | ArjunaFocusMixin - Focus recommendations |
| `agents/arjuna/standup.py` | ✅ DONE | ~100 | ArjunaStandupMixin - Standup operations |
| `agents/arjuna/tools.py` | ✅ DONE | ~80 | Helper functions for response formatting |
| `agents/arjuna/mcp_handler.py` | ✅ DONE | ~165 | ArjunaMCPMixin - MCP command handling |
| `agents/arjuna/chain_executor.py` | ✅ DONE | ~218 | ArjunaChainMixin + CHAIN_DEFINITIONS |
| `agents/arjuna/intents.py` | ✅ DONE | ~147 | ArjunaIntentMixin - Intent parsing/execution |
| `agents/arjuna/tickets.py` | ✅ DONE | ~186 | ArjunaTicketMixin - Ticket CRUD operations |
| `agents/arjuna/core.py` | ✅ DONE | ~350 | ArjunaAgentCore - Composition-based agent |
| `agents/arjuna/adapters.py` | ✅ DONE | ~280 | Module-level adapter functions |

**Total: 11 modules (~1900 lines) - Well-organized, single-responsibility code**

**Architecture**: Uses mixin composition pattern. ArjunaAgentCore inherits from all mixins for clean separation of concerns while maintaining a unified agent interface.

### 2.4 Other Large Files
| File | Lines | Target | Status | Notes |
|------|-------|--------|--------|-------|
| `api/career.py` | 2779 | domains/career/api/ | ✅ 100%+ Complete | 68 domain routes (exceeds 64 legacy) |
| `services/background_jobs.py` | 1417 | Split by job type | ⬜ TODO | |
| `api/search.py` | 1285 | domains/search/api/ | 🟡 Partial | Some routes migrated |
| `agents/dikw_synthesizer.py` | 1201 | agents/dikw_synthesizer/ | ✅ DONE | Package extracted |
| `main.py` | 1235 | Acceptable | ✅ OK | Application setup |
| `career_repository.py` | 1133 | Acceptable | ✅ OK | Repository pattern |
| `meetings.py` | 1102 | domains/meetings/api/ | ✅ DONE | 17 routes extracted |
| `api/assistant.py` | 987 | Split by feature | ⬜ TODO | |
| `db.py` | 961 | Remove (use adapters) | ⬜ TODO | Legacy, migrate to repositories |
| `api/v1/imports.py` | 960 | Split by import type | ⬜ TODO | |
| `tickets.py` | 888 | domains/tickets/api/ | ✅ DONE | 12 routes extracted |

### 2.4a Career Domain Migration Detail (Completed 2026-01-27)
| Domain File | Routes | Notes |
|-------------|--------|-------|
| `profile.py` | 3 | Profile CRUD |
| `skills.py` | 4 | Basic skill tracking |
| `skills_advanced.py` | 8 | AI-powered: initialize, reset, from-resume, assess-from-codebase, etc. |
| `standups.py` | 6 | Standup CRUD + AI suggest |
| `suggestions.py` | 7 | Suggestions + convert to ticket + compress |
| `memories.py` | 7 | AI + career memories |
| `code_locker.py` | 14 | Code storage + ticket files (fully expanded) |
| `chat.py` | 6 | Chat + tweaks |
| `insights.py` | 5 | AI insights |
| `projects.py` | 3 | Project tracking |
| `docs.py` | 6 | ADRs, AI implementations, backends |
| **Total** | **68** | ✅ Complete - exceeds 64 legacy routes |

**Note**: The 68 routes in domain files cover all career functionality. Legacy `api/career.py` can be deprecated.

---

## Phase 3: Tests Reorganization

### Target Structure ✅ IMPLEMENTED
```
tests/
├── unit/                       # Fast, isolated tests ✅
│   ├── test_domain_models.py   # Domain model tests (13 tests)
│   └── test_sdk_client.py      # SDK client tests (14 tests)
├── integration/                # Tests with real dependencies ✅
│   └── test_api_dikw.py        # DIKW API tests
├── e2e/                        # End-to-end scenarios ✅
│   └── __init__.py
├── fixtures/                   # Shared test data ✅
│   ├── data.py                 # Factory functions
│   └── __init__.py
└── conftest.py                 # Shared pytest config (existing)
```

| Task | Status | Notes |
|------|--------|-------|
| Create directory structure | ✅ DONE | unit/, integration/, fixtures/, e2e/ |
| Add domain model tests | ✅ DONE | 13 tests for Signal, Meeting, DIKW, etc. |
| Add SDK client tests | ✅ DONE | 14 tests for SignalFlowClient |
| Create fixtures module | ✅ DONE | data.py with make_* factories |
| Move existing tests | ⬜ TODO | Categorize by type |
| Add missing unit tests | ⬜ TODO | Target 80% coverage |

---

## Phase 4: MCP Server Setup

### 4.1 MCP Server Architecture
```
mcp/
├── server.py                   # FastMCP server entry point ✅
├── tools/                      # Tool implementations (inline in server.py)
├── Dockerfile.mcp              # MCP server container ✅
└── docker-compose.yaml         # MCP profile added ✅
```

| Task | Status | Notes |
|------|--------|-------|
| Create MCP server structure | ✅ DONE | Using FastMCP with fallback to mcp |
| Migrate existing tools | ✅ DONE | 11 tools: search, meetings, knowledge, tickets, career |
| Add Docker configuration | ✅ DONE | Dockerfile.mcp, compose profile |
| Document MCP endpoints | ⬜ TODO | API docs for agent usage |

### MCP Server Commands
```bash
# Local development (stdio mode)
make mcp

# Docker
make build-mcp
make run-mcp
# Or: docker-compose --profile mcp up
```

---

## Phase 5: Backend/Frontend Separation

### Target Architecture
```
v0agent/
├── src/
│   └── app/                    # BACKEND (Python FastAPI)
│       ├── api/                # HTTP handlers (versioned)
│       │   ├── v1/             # Stable public API
│       │   └── internal/       # Admin/internal endpoints
│       ├── core/               # Domain layer (business logic)
│       ├── adapters/           # Infrastructure adapters
│       ├── services/           # Application services
│       └── mcp/                # MCP server for AI agents
│
├── sdk/                        # CLIENT SDK (Python)
│   ├── signalflow/             # Package name
│   │   ├── __init__.py
│   │   ├── client.py           # Main client class
│   │   ├── analyst.py          # Analyst SDK (LangSmith, reports)
│   │   ├── meetings.py         # Meeting operations
│   │   ├── tickets.py          # Ticket operations
│   │   ├── career.py           # Career operations
│   │   └── models.py           # Shared Pydantic models
│   ├── setup.py                # Package setup
│   └── README.md               # SDK documentation
│
├── mobile/                     # MOBILE CLIENT (React Native)
│   └── src/
│       ├── services/           # API client (TypeScript)
│       ├── stores/             # State management
│       └── components/         # UI components
│
└── frontend/                   # WEB CLIENT (Future)
    └── src/
```

### 5.1 Extract Python SDK
| Task | Status | Notes |
|------|--------|-------|
| Move `src/app/sdk/` to `sdk/signalflow/` | ⬜ TODO | Standalone package |
| Extract LangSmith client wrapper | ⬜ TODO | `sdk/signalflow/analyst.py` |
| Create typed models with Pydantic | ⬜ TODO | `sdk/signalflow/models.py` |
| Add async support | ⬜ TODO | Both sync and async clients |
| Package for PyPI | ⬜ TODO | `pip install signalflow-sdk` |

### 5.2 Define API Contracts
| Task | Status | Notes |
|------|--------|-------|
| OpenAPI spec generation | ⬜ TODO | Auto-generate from FastAPI |
| Response model validation | ⬜ TODO | Consistent API responses |
| Error standardization | ⬜ TODO | Error codes and messages |
| Version headers | ⬜ TODO | API versioning support |

### 5.3 Mobile Client Updates
| Task | Status | Notes |
|------|--------|-------|
| Type generation from OpenAPI | ⬜ TODO | Auto-generate TypeScript types |
| Remove direct Supabase calls | ⬜ TODO | Use API endpoints only |
| Add offline support | ⬜ TODO | Queue operations when offline |

---

## Phase 6: Cleanup

| Task | Status | Notes |
|------|--------|-------|
| Remove lazy imports | ⬜ TODO | Replace with proper dependency injection |
| Remove dead code | ⬜ TODO | Unused functions, old migrations |
| Update all imports | ⬜ TODO | Use new module paths |
| Update documentation | ⬜ TODO | Architecture docs, API docs |

---

## Progress Log

### 2026-01-27 (Session 2 - DDD Enforcement & SDK)
- [x] Removed pgAdmin from docker-compose.yaml (use Supabase Studio)
- [x] Consolidated domain models - `core/models/__init__.py` re-exports from `core/domain/models.py`
- [x] Refactored MCP server to use service layer (DDD compliant)
  - Replaced direct `supabase.table()` calls with service functions
  - Now uses `meetings_supabase`, `tickets_supabase`, `SupabaseDIKWRepository`
  - Career functions documented as temporary until career repository extracted
- [x] Created standalone SDK package in `sdk/signalflow/`
  - `client.py` - Main API client with typed sub-clients
  - `analyst.py` - LangSmith integration for analytics/observability
  - `models.py` - Pydantic models for type safety
  - `setup.py` - Package configuration for pip install
  - `README.md` - SDK documentation
- [x] Created DDD-compliant API v1 DIKW endpoints (`api/v1/dikw.py`)
- [x] Updated REFACTORING_TRACKER.md with Phase 5 (Backend/Frontend)
- [x] Updated REPOSITORY_PATTERN_REFACTOR.md with DDD compliance notes

### 2026-01-27 (Session 1)
- [x] Created refactoring tracker document
- [x] Analyzed codebase structure
- [x] Updated Makefile (removed neo4j/chromadb)
- [x] Updated docker-compose (simplified services)
- [x] Created Protocol-based interfaces in `core/ports/protocols.py`
- [x] Created enhanced domain models in `core/domain/models.py`
- [x] Added career models: CareerProfile, CareerSuggestion, CareerMemory, StandupUpdate, Skill
- [x] Extracted DIKW routes to `api/dikw.py` (~400 lines)
- [x] Extracted mindmap routes to `api/mindmap.py` (~350 lines)
- [x] Extracted notification, workflow, reports, evaluations, pocket routes (~1900 lines)
- [x] Setup MCP server with 11 tools

---

## Notes

### Why Protocols over ABC?
- **Structural subtyping**: No need to inherit, just implement the methods
- **Better IDE support**: Type checkers understand protocols natively
- **Easier testing**: Mock objects work without explicit inheritance
- **Python 3.8+**: First-class support in typing module

### Lazy Import Decision
Current lazy imports exist because:
1. Circular dependency avoidance (main issue)
2. Startup performance optimization
3. Optional dependency handling

Solution: Proper dependency injection will eliminate need for most lazy imports.

### MCP Server Best Practices
- Run as separate service (not embedded in main app)
- Use Docker for isolation
- Share database through Supabase (no direct DB coupling)
- Version tools independently of main app
