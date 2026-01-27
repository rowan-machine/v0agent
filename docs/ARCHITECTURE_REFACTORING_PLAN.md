# Architecture Refactoring Plan

## Current State Analysis

The codebase has evolved organically with several pain points:

1. **Monolithic main.py** (~5000+ lines) with mixed concerns
2. **Direct database access** scattered throughout with `from ..db import connect`
3. **Tight coupling** between business logic and data access
4. **No abstraction** for swapping databases or embedding providers
5. **SQLite references** still present despite Supabase migration

## Target Architecture: Hexagonal (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ API Routers  │ │   Services   │ │  Background  │            │
│  │  (FastAPI)   │ │   (Logic)    │ │    Jobs      │            │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          v                v                v
┌─────────────────────────────────────────────────────────────────┐
│                       Domain Layer (Core)                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │    Ports     │ │    Models    │ │   Use Cases  │            │
│  │ (Interfaces) │ │  (Entities)  │ │   (Interactors)           │
│  └──────┬───────┘ └──────────────┘ └──────────────┘            │
└─────────┼───────────────────────────────────────────────────────┘
          │
          v
┌─────────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                       Adapters                            │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │  Supabase  │  │   SQLite   │  │   OpenAI   │         │  │
│  │  │  Database  │  │  Database  │  │ Embeddings │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │  Supabase  │  │   Local    │  │   Local    │         │  │
│  │  │  Storage   │  │  Storage   │  │ Embeddings │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure (Target)

```
src/app/
├── __init__.py
├── main.py                      # Minimal - just creates app & includes routers
│
├── core/                        # Domain layer - NO external dependencies
│   ├── __init__.py
│   ├── ports/                   # Abstract interfaces
│   │   ├── __init__.py
│   │   ├── database.py          # DatabasePort, Repository interfaces ✅
│   │   ├── embedding.py         # EmbeddingPort, VectorStorePort ✅
│   │   └── storage.py           # StoragePort ✅
│   │
│   ├── models/                  # Domain entities
│   │   ├── __init__.py          # Meeting, Document, Ticket, etc. ✅
│   │   ├── meeting.py           # Meeting-specific models
│   │   ├── dikw.py              # DIKW pyramid models
│   │   └── signal.py            # Signal models
│   │
│   └── use_cases/               # Business logic interactors
│       ├── __init__.py
│       ├── meetings.py          # Meeting operations
│       ├── knowledge.py         # DIKW operations
│       └── search.py            # Search operations
│
├── adapters/                    # Infrastructure layer
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── supabase.py          # SupabaseDatabaseAdapter ✅
│   │   └── sqlite.py            # SQLiteDatabaseAdapter ✅
│   │
│   ├── embedding/
│   │   ├── __init__.py
│   │   ├── openai.py            # OpenAIEmbeddingAdapter ✅
│   │   └── local.py             # LocalEmbeddingAdapter ✅
│   │
│   └── storage/
│       ├── __init__.py
│       ├── supabase.py          # SupabaseStorageAdapter ✅
│       └── local.py             # LocalStorageAdapter ✅
│
├── api/                         # API layer - organized by domain
│   ├── __init__.py
│   ├── router.py                # Main router combining all sub-routers
│   │
│   ├── meetings/                # Meeting endpoints
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   ├── knowledge/               # DIKW/Knowledge endpoints
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   ├── search/                  # Search endpoints
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   ├── settings/                # Settings endpoints
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   └── ... (other domains)
│
├── services/                    # Application services
│   ├── __init__.py
│   ├── meeting_service.py       # Meeting business logic
│   ├── knowledge_service.py     # DIKW business logic
│   ├── search_service.py        # Search orchestration
│   └── ...
│
└── container.py                 # DI container ✅
```

## Phase 1: Core Infrastructure (COMPLETE ✅)

Created the foundational ports and adapters:

- [x] `core/ports/database.py` - DatabasePort interface
- [x] `core/ports/embedding.py` - EmbeddingPort interface  
- [x] `core/ports/storage.py` - StoragePort interface
- [x] `core/models/__init__.py` - Domain models
- [x] `adapters/database/supabase.py` - Supabase implementation
- [x] `adapters/database/sqlite.py` - SQLite implementation
- [x] `adapters/embedding/openai.py` - OpenAI implementation
- [x] `adapters/embedding/local.py` - Local implementation
- [x] `adapters/storage/supabase.py` - Supabase Storage implementation
- [x] `adapters/storage/local.py` - Local filesystem implementation
- [x] `core/container.py` - Dependency injection container

## Phase 2: Convert Remaining SQLite Files (IN PROGRESS)

Files with `from ..db import connect` to convert:

### Services
- [ ] `services/agent_bus.py` (8 occurrences)
- [ ] `services/storage_supabase.py` (1 occurrence)
- [ ] `services/coach_recommendations.py` (1 occurrence)
- [ ] `services/mindmap_synthesis.py` (1 occurrence)
- [ ] `services/signal_learning.py` (1 occurrence)
- [ ] `services/background_jobs.py` (1 occurrence)

### API Modules
- [ ] `api/settings.py` (1 occurrence)
- [ ] `api/mcp.py` (1 occurrence)
- [ ] `api/search.py` (2 occurrences)
- [ ] `api/admin.py` (2 occurrences)
- [ ] `api/accountability.py` (1 occurrence)
- [ ] `api/shortcuts.py` (1 occurrence)
- [ ] `api/career.py` (1 occurrence)
- [ ] `api/assistant.py` (1 occurrence)
- [ ] `api/knowledge_graph.py` (1 occurrence)
- [ ] `api/mobile/device.py` (1 occurrence)
- [ ] `api/mobile/sync.py` (1 occurrence)
- [ ] `api/v1/ai_memory.py` (1 occurrence)
- [ ] `api/v1/imports.py` (1 occurrence)

### Root Level
- [ ] `search.py` (1 occurrence)
- [ ] `db_adapter.py` (can be removed after migration)
- [ ] `db_migrations.py` (needs review)

## Phase 3: Refactor main.py

Split ~5000 line main.py into modular packages:

1. **Extract API Routers**
   - Move each domain's endpoints to `api/{domain}/router.py`
   - Keep main.py minimal (~100 lines)

2. **Extract Services**
   - Business logic from endpoints → `services/{domain}_service.py`
   - Services use container for dependencies

3. **Extract Pydantic Models**
   - Request/response schemas → `api/{domain}/schemas.py`

## Phase 4: Documentation Updates

- [ ] Update README.md - remove SQLite setup instructions
- [ ] Update DEPLOYMENT_GUIDE.md - Supabase-only focus
- [ ] Update QUICK_REFERENCE.md - new architecture overview
- [ ] Update ADR docs - document architecture decisions
- [ ] Remove/archive obsolete SQLite docs

## Configuration

The system uses environment variables for adapter selection:

```bash
# Database
DATABASE_TYPE=supabase  # or "sqlite"

# Embeddings  
EMBEDDING_TYPE=openai   # or "local"

# Storage
STORAGE_TYPE=supabase   # or "local"

# Provider configs
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
OPENAI_API_KEY=xxx
```

## Usage Examples

### Getting Dependencies
```python
from src.app.core.container import container

# Get database adapter
db = container.database()

# Get specific repository
meetings = container.meetings_repository()

# Get embedding provider
embeddings = container.embedding_provider()

# Get storage provider
storage = container.storage_provider()
```

### Switching Providers at Runtime
```python
from src.app.core.container import container

# Switch to SQLite for testing
container.configure(database="sqlite")

# Switch to local embeddings
container.configure(embedding="local")
```

### In API Endpoints
```python
from fastapi import Depends
from src.app.core.container import get_meetings_repo
from src.app.core.ports.database import MeetingsRepository

@router.get("/meetings")
def get_meetings(
    repo: MeetingsRepository = Depends(get_meetings_repo)
):
    return repo.get_all()
```

## Benefits

1. **Easy Testing** - Mock adapters for unit tests
2. **Provider Flexibility** - Switch Supabase ↔ SQLite with one config change
3. **Privacy Mode** - Local-only deployment without cloud dependencies
4. **Clear Boundaries** - Domain logic separate from infrastructure
5. **Maintainability** - Smaller, focused files instead of monolithic main.py
