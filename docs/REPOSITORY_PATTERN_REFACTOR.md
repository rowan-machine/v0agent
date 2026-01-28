# Repository Pattern Refactor Plan

> **Last Updated**: 2026-01-27 (Phase 3 Complete)
> **Status**: DDD Enforcement Complete - SQLite Removed - Supabase Only

## Overview

This document outlines the completed migration from direct SQLite/Supabase access throughout the codebase to a clean ports/adapters (hexagonal) architecture.

**Key Milestones:**
- ✅ 11 Repositories implemented
- ✅ All SQLite code removed (db.py deleted)
- ✅ 15 Protocol interfaces defined
- ✅ 6 Adapters implemented (database, embedding, storage)

## Naming Convention

All repository and service files follow these naming patterns:
- **Repositories**: `*_repository.py` (e.g., `meeting_repository.py`, `signal_repository.py`)
- **Services**: `*_service.py` (e.g., `meeting_service.py`, `document_service.py`)

## DDD Compliance Status

### ✅ Compliant Files (Using Repository/Service Layer)
- `repositories/meeting_repository.py` - Clean repository pattern
- `repositories/document_repository.py` - Clean repository pattern
- `repositories/ticket_repository.py` - Clean repository pattern
- `repositories/signal_repository.py` - Signal feedback/status operations
- `repositories/settings_repository.py` - Mode sessions, sprint settings, user status
- `repositories/ai_memory_repository.py` - AI memory storage operations
- `repositories/agent_messages_repository.py` - Agent-to-agent communication
- `repositories/mindmap_repository.py` - Conversation mindmaps and syntheses
- `repositories/notifications_repository.py` - **NEW** - Push/in-app notifications
- `repositories/career_repository.py` - **NEW** - Career profile, skills, standups, memories, suggestions
- `repositories/dikw_repository.py` - **NEW** - DIKW items, evolution, promotion, merge operations
- `services/meeting_service.py` - Clean service module (renamed from meetings_supabase.py)
- `services/document_service.py` - Clean service module (renamed from documents_supabase.py)
- `services/ticket_service.py` - Clean service module (renamed from tickets_supabase.py)
- `services/signal_learning.py` - **REFACTORED** - Uses repositories
- `services/agent_bus.py` - **REFACTORED** - Uses repositories
- `services/mindmap_synthesis.py` - **REFACTORED** - Uses repositories
- `services/background_jobs.py` - **REFACTORED** - Uses NotificationsRepository
- `mcp/server.py` - Uses proper service layer
- `api/dikw.py` - Uses proper service layer
- `api/mindmap.py` - Uses proper service layer
- `adapters/database/supabase.py` - Repository implementations

### ✅ SQLite Removed (Phase 3.3 Complete)
- `db.py` - **DELETED** (998 lines)
- `db_migrations.py` - **DELETED**
- All `from ..db import connect` imports - **REMOVED**

### ⚠️ Remaining Direct Supabase Access
These files use `supabase.table()` directly but are acceptable:
- `main.py` - 2-3 remaining calls for complex queries
- `mcp/server.py` - Career functions (low priority)
- Legacy API files - Deprecated with domain replacements

### ✅ Red Flags Resolved
- ✅ Direct `supabase.table()` calls - Migrated to service/repository layer
- ✅ Direct `from ..db import connect` SQLite calls - **REMOVED** (db.py deleted)
- ✅ Dual-write logic (SQLite + Supabase) - **REMOVED** (SQLite only database now)

## Backward Compatibility

The services `__init__.py` provides aliases for the old names:
```python
# Old imports still work:
from .services import meetings_supabase  # -> meeting_service
from .services import documents_supabase  # -> document_service  
from .services import tickets_supabase  # -> ticket_service
```

## Target Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Application Layer                      │
│  (FastAPI routes, services, business logic)              │
└────────────────────────┬─────────────────────────────────┘
                         │ uses
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    Port Layer                             │
│  (Abstract interfaces/protocols)                          │
│  - MeetingRepository                                      │
│  - DocumentRepository                                     │
│  - TicketRepository                                       │
│  - SignalRepository                                       │
│  - SettingsRepository                                     │
│  - AIMemoryRepository                                     │
│  - AgentMessagesRepository                                │
│  - MindmapRepository                                      │
│  - NotificationsRepository (NEW)                          │
│  - CareerRepository (NEW)                                 │
│  - DIKWRepository (NEW)                                   │
└────────────────────────┬─────────────────────────────────┘
                         │ implemented by
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   Adapter Layer                           │
│  (Concrete implementations)                               │
│  - SupabaseMeetingRepository                             │
│  - SupabaseDocumentRepository                            │
│  - SupabaseSignalRepository                              │
│  - SupabaseSettingsRepository                            │
│  - SupabaseAIMemoryRepository                            │
│  - SupabaseAgentMessagesRepository                       │
│  - SupabaseMindmapRepository                             │
│  - SupabaseNotificationsRepository (NEW)                 │
│  - SupabaseCareerRepository (NEW)                        │
│  - SupabaseDIKWRepository (NEW)                          │
└──────────────────────────────────────────────────────────┘
```

## Files Requiring Migration

### Priority 1 - Core Data Access (Already Started)
- [x] `src/app/chat/models.py` - Conversations/Messages
- [x] `src/app/api/chat.py` - Chat API
- [x] `src/app/chat/turn.py` - Chat turns
- [x] `src/app/services/notification_queue.py` - Notifications

### Priority 2 - Repositories (COMPLETED ✅)
- [x] `src/app/repositories/document_repository.py` - Renamed, Supabase-only
- [x] `src/app/repositories/meeting_repository.py` - Renamed, Supabase-only
- [x] `src/app/repositories/ticket_repository.py` - Renamed, Supabase-only
- [x] `src/app/repositories/signal_repository.py` - **NEW** - Extracted from main.py
- [x] `src/app/repositories/settings_repository.py` - **NEW** - Extracted from main.py
- [x] `src/app/repositories/notifications_repository.py` - **NEW** - Push/in-app notifications
- [x] `src/app/repositories/career_repository.py` - **NEW** - Career tables (126 direct calls to consolidate)
- [x] `src/app/repositories/dikw_repository.py` - **NEW** - DIKW tables (33 direct calls)

### Priority 3 - Services Layer (COMPLETED ✅)
- [x] `src/app/services/meeting_service.py` - Renamed, enhanced with signal update methods
- [x] `src/app/services/document_service.py` - Renamed
- [x] `src/app/services/ticket_service.py` - Renamed
- [x] `src/app/services/signal_learning.py` - Refactored to use SignalRepository + AIMemoryRepository
- [x] `src/app/services/agent_bus.py` - Refactored to use AgentMessagesRepository
- [x] `src/app/services/mindmap_synthesis.py` - Refactored to use MindmapRepository
- [x] `src/app/services/background_jobs.py` - Refactored to use NotificationsRepository
- [ ] `src/app/services/coach_recommendations.py` - Has null checks, lower priority

### Priority 4 - API Layer (IN PROGRESS)
- [ ] `src/app/api/career.py` - **BLOCKED** - 126 direct calls, use CareerRepository
- [ ] `src/app/api/dikw.py` - **BLOCKED** - 26 direct calls, use DIKWRepository
- [ ] `src/app/api/search.py` - 18 direct calls
- [ ] `src/app/api/knowledge_graph.py` - 34 direct calls
- [ ] `src/app/api/assistant.py` - 25 direct calls
- [ ] `src/app/api/settings.py` - 10 direct calls
- [ ] `src/app/api/admin.py`
- [ ] `src/app/api/accountability.py`
- [ ] `src/app/api/shortcuts.py`
- [ ] `src/app/api/mcp.py`

### Priority 5 - Memory/Search Layer
- [ ] `src/app/memory/vector_store.py`
- [ ] `src/app/memory/semantic.py`
- [ ] `src/app/memory/retrieve.py`
- [ ] `src/app/search.py`

### Priority 6 - Core Modules
- [ ] `src/app/documents.py`
- [ ] `src/app/meetings.py`
- [ ] `src/app/tickets.py`
- [ ] `src/app/signals.py`
- [ ] `src/app/auth.py`
- [ ] `src/app/llm.py`

### Priority 7 - Agents
- [ ] `src/app/agents/arjuna.py`
- [ ] `src/app/mcp/tools.py`

## Migration Strategy

### Phase 1: Create Abstract Interfaces (Week 1)
Create protocol classes for each data type:

```python
# src/app/ports/repositories.py
from typing import Protocol, List, Optional, Dict, Any
from datetime import datetime

class MeetingRepository(Protocol):
    def get_by_id(self, meeting_id: int) -> Optional[Dict[str, Any]]: ...
    def get_all(self, limit: int = 50) -> List[Dict[str, Any]]: ...
    def create(self, data: Dict[str, Any]) -> int: ...
    def update(self, meeting_id: int, data: Dict[str, Any]) -> bool: ...
    def delete(self, meeting_id: int) -> bool: ...
    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]: ...
```

### Phase 2: Create Supabase Adapters (Week 1-2)
Implement the interfaces for Supabase:

```python
# src/app/adapters/supabase/meetings.py
class SupabaseMeetingRepository:
    def __init__(self, client):
        self.client = client
    
    def get_by_id(self, meeting_id: int) -> Optional[Dict[str, Any]]:
        result = self.client.table("meetings").select("*").eq("id", meeting_id).execute()
        return result.data[0] if result.data else None
```

### Phase 3: Create Dependency Injection Container (Week 2)
Set up a simple DI container:

```python
# src/app/container.py
from functools import lru_cache

@lru_cache
def get_meeting_repository() -> MeetingRepository:
    from .infrastructure.supabase_client import get_supabase_client
    from .adapters.supabase.meetings import SupabaseMeetingRepository
    return SupabaseMeetingRepository(get_supabase_client())
```

### Phase 4: Migrate Services One at a Time (Week 2-4)
Update each service to use injected repositories:

```python
# Before
from ..db import connect
def get_meetings():
    with connect() as conn:
        return conn.execute("SELECT * FROM meetings").fetchall()

# After
def get_meetings(repo: MeetingRepository = Depends(get_meeting_repository)):
    return repo.get_all()
```

### Phase 5: Remove SQLite Code (Week 4)
Once all services use repositories, remove:
- `src/app/db.py` (or keep for migrations only)
- All `connect()` calls
- All dual-write logic

## Live Data Safety

### Safe Migration Approach

1. **Read from Supabase First**: Already implemented in most places
2. **Write to Both**: During transition, write to both DBs
3. **Verify Consistency**: Run comparison checks
4. **Cut Over**: Once verified, remove SQLite writes
5. **Clean Up**: Remove SQLite code

### Rollback Strategy

- Keep SQLite backup: `agent.db.backup`
- Environment flag: `USE_SQLITE_FALLBACK=true`
- Can restore by renaming backup and setting flag

## Testing Strategy

1. Create mock repositories for unit tests
2. Use test database for integration tests
3. Run parallel comparisons during migration

## Timeline

| Week | Focus |
|------|-------|
| 1 | Create interfaces, migrate 2-3 core services |
| 2 | Complete service migrations |
| 3 | Migrate API layer |
| 4 | Migrate agents, clean up |

## Can We Do This With Live Data?

**Yes**, with these precautions:

1. ✅ Supabase already has all data
2. ✅ Current code already prefers Supabase
3. ✅ SQLite is just a fallback
4. ⚠️ Some features may briefly fail during migration
5. ✅ Can restore from backup if needed

**Recommendation**: Proceed with migration since:
- No data loss risk (Supabase is source of truth)
- Easier to fix issues incrementally
- Blocking on perfect architecture delays value

## Next Steps

1. Remove SQLite fallbacks from existing repositories
2. Create remaining repository interfaces
3. Update services to use repositories
4. Remove all direct `connect()` calls
