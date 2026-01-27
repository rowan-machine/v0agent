# Repository Pattern Refactor Plan

> **Last Updated**: 2026-01-27
> **Status**: DDD Enforcement Phase

## Overview

This document outlines the plan to migrate from direct SQLite/Supabase access throughout the codebase to a clean ports/adapters (hexagonal) architecture.

## DDD Compliance Status

### ✅ Compliant Files (Using Service Layer)
- `mcp/server.py` - Refactored to use `meetings_supabase`, `tickets_supabase`, `SupabaseDIKWRepository`
- `api/dikw.py` - Uses proper service layer
- `api/mindmap.py` - Uses proper service layer
- `services/meetings_supabase.py` - Clean service module
- `services/tickets_supabase.py` - Clean service module
- `adapters/database/supabase.py` - Repository implementations

### ⚠️ Temporary Exceptions (Documented)
- `mcp/server.py` career functions - Uses `career_supabase_helper` until CareerRepository extracted
- `api/career.py` - Large file pending decomposition

### ❌ Red Flags (Need Migration)
- Direct `supabase.table()` calls outside service/adapter layer
- Direct `from ..db import connect` SQLite calls
- Dual-write logic (write to both SQLite and Supabase)

## Current State

The codebase has **50+ files** with direct database imports:
- `from ..db import connect` (SQLite)
- `from ..infrastructure.supabase_client import get_supabase_client` (Supabase)

Many files have dual-write logic that writes to both databases.

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
│  - ConversationRepository                                 │
│  - NotificationRepository                                 │
│  - SettingsRepository                                     │
└────────────────────────┬─────────────────────────────────┘
                         │ implemented by
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   Adapter Layer                           │
│  (Concrete implementations)                               │
│  - SupabaseMeetingRepository                             │
│  - SupabaseDocumentRepository                            │
│  - etc.                                                   │
└──────────────────────────────────────────────────────────┘
```

## Files Requiring Migration

### Priority 1 - Core Data Access (Already Started)
- [x] `src/app/chat/models.py` - Conversations/Messages
- [x] `src/app/api/chat.py` - Chat API
- [x] `src/app/chat/turn.py` - Chat turns
- [x] `src/app/services/notification_queue.py` - Notifications

### Priority 2 - Repositories (Existing but mixed)
- [ ] `src/app/repositories/documents.py` - Has Supabase but SQLite fallback
- [ ] `src/app/repositories/meetings.py` - Has Supabase but SQLite fallback  
- [ ] `src/app/repositories/tickets.py` - Has Supabase but SQLite fallback

### Priority 3 - Services Layer
- [ ] `src/app/services/background_jobs.py`
- [ ] `src/app/services/agent_bus.py`
- [ ] `src/app/services/mindmap_synthesis.py`
- [ ] `src/app/services/coach_recommendations.py`
- [ ] `src/app/services/signal_learning.py`

### Priority 4 - API Layer
- [ ] `src/app/api/search.py`
- [ ] `src/app/api/career.py`
- [ ] `src/app/api/settings.py`
- [ ] `src/app/api/admin.py`
- [ ] `src/app/api/accountability.py`
- [ ] `src/app/api/knowledge_graph.py`
- [ ] `src/app/api/shortcuts.py`
- [ ] `src/app/api/assistant.py`
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
