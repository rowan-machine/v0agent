# V0Agent Refactoring Tracker

> **Last Updated**: 2026-01-27 (Phase 2.5 - Cleanup & Tests)
> **Status**: Phase 2.5 - Codebase Cleanup & Test Structure

## Current Focus

1. **Enforce DDD in MCP Server** ✅ - Refactored to use service layer instead of direct Supabase calls
2. **Remove pgAdmin from Docker** ✅ - Using Supabase Studio instead
3. **Consolidate Domain Models** ✅ - Single canonical source in `core/domain/models.py`
4. **Extract Analyst SDK** ✅ - Created sdk/signalflow/ with typed client
5. **Backend/Frontend Separation** ✅ - Uploads migrated to Supabase Storage
6. **Cleanup Scripts Folder** ✅ - Removed 31+ obsolete scripts
7. **Restructure Tests** ✅ - unit/integration/e2e folder structure

---

## Recent Accomplishments (2026-01-27)

### Cleanup Tasks Completed
| Task | Status | Details |
|------|--------|---------|
| Remove llm_new.py | ✅ DONE | Was unused (0 imports found) |
| Clean /scripts folder | ✅ DONE | Removed 31+ fix_*, check_*, sync_* scripts |
| Remove /src/app/scripts | ✅ DONE | Deleted entire folder (completed migrations) |
| Migrate uploads to Supabase | ✅ DONE | Updated tickets.py to use storage_supabase |
| Update templates for Supabase URLs | ✅ DONE | edit_meeting.html, edit_doc.html |
| Remove UPLOAD_DIR from main.py | ✅ DONE | No longer mounting local uploads |
| Add uploads/ to .gitignore | ✅ DONE | Local-only, not tracked |

### SDK & API Progress
| Component | Status | Details |
|-----------|--------|---------|
| SDK Package (sdk/signalflow/) | ✅ DONE | client.py, analyst.py, models.py |
| API v1 DIKW Endpoints | ✅ DONE | /api/v1/dikw with full CRUD |
| MCP Server | ✅ DONE | src/app/mcp/server.py with DDD patterns |
| Domain Models | ✅ DONE | core/domain/models.py with all entities |
| Protocol Interfaces | ✅ DONE | core/ports/protocols.py |

### Test Structure
| Folder | Status | Tests |
|--------|--------|-------|
| tests/unit/ | ✅ DONE | 27 tests passing |
| tests/integration/ | ✅ DONE | Structure created |
| tests/fixtures/ | ✅ DONE | data.py with factories |
| tests/e2e/ | ✅ DONE | Structure created |

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

### Target Architecture

```
src/
└── app/
    ├── core/                    # Domain layer (pure business logic)
    │   ├── domain/              # Domain models (dataclasses)
    │   │   ├── meeting.py
    │   │   ├── ticket.py
    │   │   ├── career.py
    │   │   └── signal.py
    │   ├── ports/               # Interfaces (Protocols)
    │   │   ├── repositories.py
    │   │   ├── services.py
    │   │   └── external.py
    │   └── services/            # Domain services (pure logic)
    │       ├── signal_extraction.py
    │       └── dikw_synthesis.py
    │
    ├── adapters/                # Infrastructure adapters
    │   ├── persistence/         # Database implementations
    │   │   ├── supabase/
    │   │   └── sqlite/
    │   ├── external/            # External API clients
    │   │   ├── pocket.py
    │   │   └── openai.py
    │   └── embedding/           # Vector store implementations
    │
    ├── application/             # Application layer (use cases)
    │   ├── meetings/            # Meeting use cases
    │   │   ├── load_bundle.py
    │   │   ├── extract_signals.py
    │   │   └── search.py
    │   ├── career/              # Career use cases
    │   └── tickets/             # Ticket use cases
    │
    ├── api/                     # API layer (HTTP handlers)
    │   ├── v1/                  # Versioned API routes
    │   └── internal/            # Internal/admin routes
    │
    ├── agents/                  # AI Agents (kept separate)
    │   ├── base.py
    │   ├── arjuna.py
    │   └── specialized/
    │
    ├── mcp/                     # MCP Server (for agent tools)
    │   ├── server.py
    │   ├── tools/
    │   └── resources/
    │
    └── config/                  # Configuration
        ├── settings.py
        └── dependencies.py
```

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
| `application/career/profile.py` | ⬜ TODO | ~400 | Profile management |
| `application/career/suggestions.py` | ⬜ TODO | ~500 | AI suggestions |
| `application/career/standup.py` | ⬜ TODO | ~400 | Standup analysis |
| `application/career/skills.py` | ⬜ TODO | ~400 | Skill tracking |
| `application/career/coaching.py` | ⬜ TODO | ~500 | Coaching features |
| `api/routes/career/` | ⬜ TODO | ~700 | HTTP handlers only |

### 2.3 arjuna.py (2573 lines) → Agent System
| Extract To | Status | Lines | Description |
|------------|--------|-------|-------------|
| `agents/arjuna/core.py` | ⬜ TODO | ~500 | Main agent logic |
| `agents/arjuna/memory.py` | ⬜ TODO | ~400 | Memory management |
| `agents/arjuna/tools.py` | ⬜ TODO | ~600 | Tool implementations |
| `agents/arjuna/prompts.py` | ⬜ TODO | ~300 | System prompts |
| `agents/arjuna/routing.py` | ⬜ TODO | ~300 | Request routing |

### 2.4 Other Large Files
| File | Lines | Target | Status |
|------|-------|--------|--------|
| `services/background_jobs.py` | 1425 | Split by job type | ⬜ TODO |
| `api/search.py` | 1285 | Extract to application layer | ⬜ TODO |
| `agents/dikw_synthesizer.py` | 1189 | Split stages | ⬜ TODO |
| `meetings.py` | 1102 | Move to application layer | ⬜ TODO |
| `api/assistant.py` | 987 | Split by feature | ⬜ TODO |
| `db.py` | 961 | Remove (use adapters) | ⬜ TODO |
| `api/v1/imports.py` | 960 | Split by import type | ⬜ TODO |
| `tickets.py` | 888 | Move to application layer | ⬜ TODO |

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
