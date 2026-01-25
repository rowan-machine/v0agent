# Architecture Hardening Plan: Hexagonal DDD Transition

**Date:** January 25, 2026  
**Status:** Planning Phase  
**Goal:** Decouple the system using Hexagonal Architecture + Domain-Driven Design

---

## 📊 Completed Work Summary

### Migration Phases Complete ✅

| Phase | Description | Status | Key Deliverables |
|-------|-------------|--------|------------------|
| **Phase 1** | Foundation Infrastructure | ✅ COMPLETE | Agent Registry, Base Classes, YAML Config, ChromaDB, Encryption |
| **Phase 1.5** | Refactoring Foundation | ✅ COMPLETE | Best Practices docs, Phased Rollout plan |
| **Phase 2** | Agent Extraction | ✅ COMPLETE | Arjuna, Career Coach, DIKW, Meeting Analyzer agents + adapters |
| **Phase 3** | API Extraction | ✅ COMPLETE | /api/v1/ endpoints, /api/mobile/, backward compat |
| **Phase 4** | Multi-Agent Queues | ✅ COMPLETE | Agent Bus, mDNS discovery, DualWrite adapter |
| **Phase 5** | Embeddings & Search | ✅ COMPLETE | Supabase pgvector (28 tables), hybrid search, knowledge graph |
| **Phase 6** | React Native Mobile | ✅ COMPLETE | Expo SDK 50, offline-first, APK config |
| **Phase 7** | Testing & Docs | ✅ COMPLETE | 358+ tests passing, LangSmith tracing |

### Feature Sprints Complete ✅

| Feature | Tests | Description |
|---------|-------|-------------|
| **F1: Import Pipeline** | 112 | Markdown/PDF/DOCX import, Pocket bundle amend, Mindmap OCR |
| **F2: Enhanced Search** | 42 | Full-text search, @Rowan mentions, highlight matches |
| **F3: Notifications** | 22 | 8 notification types, badge counts, action approval workflow |
| **F4: Background Jobs** | 70 | Scheduler, grooming-to-ticket match, stale ticket alerts |
| **F5: Unified Search** | ✅ | Expandable panel, filters, recent searches |

### Database Status

- **28 Supabase tables** fully migrated
- **SQLite** retained for local development/offline
- **pgvector** embeddings operational
- **Hybrid search** (semantic + keyword) working

---

## 🔴 Current Pain Points

### 1. Tight Coupling Issues

```
PROBLEM: Services directly import infrastructure
─────────────────────────────────────────────────
services/meetings_supabase.py
  └─► infrastructure/supabase_client.py  (direct import)
      └─► Creates tight coupling to Supabase specifics
      
services/documents_supabase.py  
  └─► repositories/documents.py (better!)
  └─► But still has get_supabase_client() method  (leaky abstraction)
```

### 2. Inconsistent Repository Usage

```
PROBLEM: Some services use repository, some don't
──────────────────────────────────────────────────
✅ documents_supabase.py → Uses _get_repo() pattern
❌ meetings_supabase.py → Mixed: some repo, some direct client
❌ tickets_supabase.py → Direct client calls in _format_ticket()
```

### 3. Domain Logic Scattered

```
PROBLEM: Business logic mixed with data access
──────────────────────────────────────────────
tickets.py (route)
  └─► tickets_supabase.py (service)  
      └─► Contains _format_ticket() with business rules
      └─► Should be in domain layer
```

### 4. Import Chain Fragility

```
PROBLEM: Circular/deep import chains cause startup failures
───────────────────────────────────────────────────────────
main.py
  └─► documents.py
      └─► services/__init__.py
          └─► meetings_supabase.py (syntax error breaks EVERYTHING)
          └─► documents_supabase.py (same issue)
```

---

## 🏗️ Hexagonal Architecture Target

### Proposed Layer Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    ADAPTERS (Driving)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  FastAPI    │ │  CLI        │ │  Message    │           │
│  │  Routes     │ │  Commands   │ │  Handlers   │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
│         │               │               │                   │
│         └───────────────┼───────────────┘                   │
│                         ▼                                   │
├─────────────────────────────────────────────────────────────┤
│                    PORTS (Interfaces)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  UseCase Interfaces (Application Layer Commands)    │   │
│  │  • MeetingUseCases                                  │   │
│  │  • TicketUseCases                                   │   │
│  │  • DocumentUseCases                                 │   │
│  │  • SignalUseCases                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                         ▼                                   │
├─────────────────────────────────────────────────────────────┤
│                    DOMAIN (Core)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  Entities   │ │  Value      │ │  Domain     │           │
│  │  • Meeting  │ │  Objects    │ │  Services   │           │
│  │  • Ticket   │ │  • Signal   │ │  • Synth    │           │
│  │  • Document │ │  • Tag      │ │  • Match    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                         ▲                                   │
├─────────────────────────────────────────────────────────────┤
│                    PORTS (Interfaces)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Repository Interfaces (already started!)           │   │
│  │  • MeetingRepository                                │   │
│  │  • TicketRepository                                 │   │
│  │  • DocumentRepository                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                         ▼                                   │
├─────────────────────────────────────────────────────────────┤
│                    ADAPTERS (Driven)                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  Supabase   │ │  SQLite     │ │  ChromaDB   │           │
│  │  Adapter    │ │  Adapter    │ │  Adapter    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  OpenAI     │ │  LangSmith  │ │  Notion     │           │
│  │  Adapter    │ │  Adapter    │ │  MCP Adapter│           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Proposed Directory Structure

```
src/app/
├── domain/                    # 🆕 CORE DOMAIN (no external deps)
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── meeting.py        # Meeting entity with business rules
│   │   ├── ticket.py         # Ticket entity with validation
│   │   ├── document.py       # Document entity
│   │   ├── signal.py         # Signal value object
│   │   └── dikw.py           # DIKW item entity
│   ├── value_objects/
│   │   ├── __init__.py
│   │   ├── tags.py           # Tag handling (list↔string conversion)
│   │   ├── embedding.py      # Embedding vector wrapper
│   │   └── priority.py       # Priority enum
│   └── services/
│       ├── __init__.py
│       ├── signal_extractor.py   # Signal extraction logic
│       ├── dikw_promoter.py      # DIKW promotion rules
│       └── ticket_matcher.py     # Grooming→Ticket matching
│
├── application/               # 🆕 USE CASES (orchestration)
│   ├── __init__.py
│   ├── commands/             # Write operations
│   │   ├── __init__.py
│   │   ├── create_meeting.py
│   │   ├── update_ticket.py
│   │   └── extract_signals.py
│   ├── queries/              # Read operations
│   │   ├── __init__.py
│   │   ├── get_meeting.py
│   │   ├── search_meetings.py
│   │   └── get_dashboard_stats.py
│   └── facades/              # 🆕 CONVENIENCE FACADES
│       ├── __init__.py
│       ├── meeting_facade.py     # One-stop meeting operations
│       ├── ticket_facade.py      # One-stop ticket operations
│       └── search_facade.py      # Unified search across entities
│
├── ports/                     # INTERFACES (contracts)
│   ├── __init__.py
│   ├── repositories/         # Already have this!
│   │   ├── __init__.py
│   │   ├── base.py           # ✅ Already exists
│   │   ├── meeting_repo.py   # Interface for meetings
│   │   └── ticket_repo.py    # Interface for tickets
│   └── services/             # External service interfaces
│       ├── __init__.py
│       ├── llm_port.py       # LLM abstraction
│       ├── embedding_port.py # Embedding abstraction
│       └── notification_port.py
│
├── adapters/                  # IMPLEMENTATIONS
│   ├── __init__.py
│   ├── driven/               # Called by domain
│   │   ├── __init__.py
│   │   ├── supabase/
│   │   │   ├── __init__.py
│   │   │   ├── meeting_adapter.py
│   │   │   ├── ticket_adapter.py
│   │   │   └── document_adapter.py
│   │   ├── sqlite/
│   │   │   └── meeting_adapter.py
│   │   └── openai/
│   │       └── llm_adapter.py
│   └── driving/              # Calls domain
│       ├── __init__.py
│       ├── fastapi/          # HTTP routes (current routes/)
│       │   └── meetings.py
│       └── cli/              # Command line interface
│           └── commands.py
│
├── infrastructure/           # ✅ Already exists (keep as-is for now)
│   ├── supabase_client.py
│   ├── cache.py
│   └── rate_limiter.py
│
└── services/                 # 🔄 LEGACY → Migrate to application/
    ├── __init__.py           # Keep for backward compat
    ├── meetings_supabase.py  # → application/facades/meeting_facade.py
    └── tickets_supabase.py   # → application/facades/ticket_facade.py
```

---

## 🛠️ Implementation Plan

### Phase H1: Domain Entities (Week 1)

**Goal:** Extract domain logic into pure Python classes with no external deps.

```python
# src/app/domain/entities/ticket.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from ..value_objects.tags import Tags

@dataclass
class Ticket:
    """Pure domain entity - no database or framework dependencies."""
    id: str
    title: str
    description: str
    status: str = "backlog"
    priority: int = 3
    tags: Tags = field(default_factory=Tags)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_overdue(self, reference_date: datetime = None) -> bool:
        """Domain logic: check if ticket is overdue."""
        if not self.due_date:
            return False
        ref = reference_date or datetime.utcnow()
        return ref > self.due_date and self.status != "done"
    
    def can_transition_to(self, new_status: str) -> bool:
        """Domain logic: valid status transitions."""
        valid_transitions = {
            "backlog": ["in_progress", "cancelled"],
            "in_progress": ["review", "blocked", "backlog"],
            "review": ["done", "in_progress"],
            "blocked": ["in_progress", "cancelled"],
        }
        return new_status in valid_transitions.get(self.status, [])
```

```python
# src/app/domain/value_objects/tags.py
from dataclasses import dataclass
from typing import List, Union

@dataclass(frozen=True)
class Tags:
    """Value object handling tags in both formats."""
    _tags: tuple
    
    @classmethod
    def from_list(cls, tags: List[str]) -> "Tags":
        return cls(tuple(t.strip() for t in tags if t.strip()))
    
    @classmethod
    def from_string(cls, tags_str: str) -> "Tags":
        if not tags_str:
            return cls(())
        return cls(tuple(t.strip() for t in tags_str.split(",") if t.strip()))
    
    @classmethod
    def from_any(cls, value: Union[List, str, None]) -> "Tags":
        """Factory that handles Supabase array OR legacy string format."""
        if value is None:
            return cls(())
        if isinstance(value, list):
            return cls.from_list(value)
        return cls.from_string(value)
    
    def to_list(self) -> List[str]:
        return list(self._tags)
    
    def to_string(self) -> str:
        return ", ".join(self._tags)
    
    def __iter__(self):
        return iter(self._tags)
```

### Phase H2: Facade Pattern (Week 2)

**Goal:** Create convenience classes that provide a clean API.

```python
# src/app/application/facades/meeting_facade.py
"""
MeetingFacade - One-stop shop for all meeting operations.

This facade hides the complexity of:
- Repository selection (Supabase vs SQLite)
- Signal extraction
- Embedding generation
- DIKW synthesis

Usage:
    from src.app.application.facades import MeetingFacade
    
    facade = MeetingFacade()
    
    # Simple operations
    meeting = facade.get_by_id("uuid")
    meetings = facade.search("quarterly review")
    
    # Complex operations (orchestrated internally)
    meeting = facade.import_from_pocket(transcript, mindmap_image)
"""

from typing import Any, Dict, List, Optional
import logging

from ...domain.entities.meeting import Meeting
from ...ports.repositories.meeting_repo import MeetingRepository

logger = logging.getLogger(__name__)


class MeetingFacade:
    """Convenience facade for meeting operations."""
    
    def __init__(
        self,
        repository: Optional[MeetingRepository] = None,
        signal_extractor = None,
        embedding_service = None,
    ):
        # Dependency injection with sensible defaults
        self._repo = repository or self._get_default_repo()
        self._signal_extractor = signal_extractor
        self._embedding_service = embedding_service
    
    def _get_default_repo(self) -> MeetingRepository:
        """Get default repository based on environment."""
        from ...adapters.driven.supabase import SupabaseMeetingAdapter
        return SupabaseMeetingAdapter()
    
    def get_by_id(self, meeting_id: str) -> Optional[Meeting]:
        """Get a meeting by ID."""
        data = self._repo.get_by_id(meeting_id)
        return Meeting.from_dict(data) if data else None
    
    def get_all(self, limit: int = 100) -> List[Meeting]:
        """Get all meetings."""
        return [Meeting.from_dict(d) for d in self._repo.get_all(limit=limit)]
    
    def search(self, query: str, limit: int = 20) -> List[Meeting]:
        """Search meetings by text."""
        # Could orchestrate hybrid search here
        return [Meeting.from_dict(d) for d in self._repo.search(query, limit)]
    
    def import_from_pocket(
        self,
        transcript: str,
        mindmap_image: Optional[bytes] = None,
        template_type: str = "general",
    ) -> Meeting:
        """
        High-level operation: Import a meeting from Pocket.
        
        This orchestrates:
        1. Parse transcript
        2. Extract signals (if extractor available)
        3. Process mindmap image (if provided)
        4. Create meeting record
        5. Generate embeddings
        """
        # Domain logic stays in domain layer
        from ...domain.services.signal_extractor import extract_signals
        
        meeting_data = {
            "raw_text": transcript,
            "template_type": template_type,
        }
        
        # Extract signals
        if self._signal_extractor:
            signals = self._signal_extractor.extract(transcript)
            meeting_data["signals_json"] = signals
        
        # Create via repository
        created = self._repo.create(meeting_data)
        
        # Generate embeddings asynchronously
        if self._embedding_service and created:
            self._embedding_service.embed_async("meeting", created["id"], transcript)
        
        return Meeting.from_dict(created)
```

### Phase H3: Port Interfaces (Week 3)

**Goal:** Define clear contracts for all external dependencies.

```python
# src/app/ports/services/llm_port.py
"""
LLM Port - Interface for language model operations.

This is the contract that any LLM adapter must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    model: str
    tokens_used: int
    finish_reason: str


class LLMPort(ABC):
    """Abstract interface for LLM operations."""
    
    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """Generate a completion."""
        pass
    
    @abstractmethod
    def complete_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a structured (JSON) response."""
        pass
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding vector."""
        pass
```

### Phase H4: Adapter Migration (Week 4)

**Goal:** Move existing implementations to adapter layer.

```python
# src/app/adapters/driven/supabase/meeting_adapter.py
"""
Supabase Meeting Adapter

Implements MeetingRepository interface using Supabase.
"""

from typing import Any, Dict, List, Optional
import logging

from ....ports.repositories.meeting_repo import MeetingRepository
from ....infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class SupabaseMeetingAdapter(MeetingRepository):
    """Supabase implementation of MeetingRepository."""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client
    
    def get_by_id(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        
        try:
            result = self.client.table("meetings").select("*").eq("id", meeting_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get meeting {meeting_id}: {e}")
            return None
    
    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.client:
            return []
        
        try:
            result = self.client.table("meetings").select("*").order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get meetings: {e}")
            return []
    
    # ... implement all interface methods
```

---

## 🔧 Backward Compatibility Strategy

### Keep Legacy Imports Working

```python
# src/app/services/meetings_supabase.py
"""
DEPRECATED: Use application.facades.meeting_facade instead.

This module is maintained for backward compatibility only.
"""

import warnings
from ..application.facades.meeting_facade import MeetingFacade

# Emit deprecation warning on import
warnings.warn(
    "meetings_supabase is deprecated. Use application.facades.meeting_facade instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Create facade singleton for legacy function calls
_facade = None

def _get_facade():
    global _facade
    if _facade is None:
        _facade = MeetingFacade()
    return _facade

# Legacy function signatures preserved
def get_all_meetings(limit: int = 100):
    """DEPRECATED: Use MeetingFacade.get_all()"""
    return [m.to_dict() for m in _get_facade().get_all(limit)]

def get_meeting_by_id(meeting_id: str):
    """DEPRECATED: Use MeetingFacade.get_by_id()"""
    meeting = _get_facade().get_by_id(meeting_id)
    return meeting.to_dict() if meeting else None
```

---

## 📋 Migration Checklist

### Phase H1: Domain Layer
- [ ] Create `src/app/domain/` directory structure
- [ ] Implement `Tags` value object (fixes current tags array issue!)
- [ ] Implement `Meeting` entity
- [ ] Implement `Ticket` entity  
- [ ] Implement `Document` entity
- [ ] Add domain service for signal extraction
- [ ] Add unit tests for all domain objects

### Phase H2: Application Layer
- [ ] Create `src/app/application/` directory structure
- [ ] Implement `MeetingFacade`
- [ ] Implement `TicketFacade`
- [ ] Implement `DocumentFacade`
- [ ] Implement `SearchFacade` (unified search)
- [ ] Add integration tests for facades

### Phase H3: Ports Layer
- [ ] Define `LLMPort` interface
- [ ] Define `EmbeddingPort` interface
- [ ] Define `NotificationPort` interface
- [ ] Extend existing repository interfaces

### Phase H4: Adapters Layer
- [ ] Move Supabase implementations to `adapters/driven/supabase/`
- [ ] Move SQLite implementations to `adapters/driven/sqlite/`
- [ ] Create OpenAI adapter implementing `LLMPort`
- [ ] Create deprecation wrappers in `services/`

### Phase H5: Cleanup
- [ ] Update all route files to use facades
- [ ] Add deprecation warnings to old imports
- [ ] Update documentation
- [ ] Remove dead code after verification period

---

## 🎯 Success Metrics

| Metric | Current | Target | Why |
|--------|---------|--------|-----|
| Import chain depth | 5+ levels | ≤3 levels | Faster startup, easier debugging |
| Service-to-infrastructure coupling | Direct | Via ports | Swappable backends |
| Domain logic location | Scattered | `domain/` | Single source of truth |
| Test isolation | Mixed | Unit tests 100% isolated | Faster, more reliable tests |
| Startup time | Variable | <2s | No import errors |

---

## 📚 References

- **Hexagonal Architecture:** Alistair Cockburn's original pattern
- **Ports & Adapters:** Same pattern, different name
- **Clean Architecture:** Uncle Bob's application
- **Domain-Driven Design:** Eric Evans, tactical patterns
- **Facade Pattern:** GoF design pattern for simplified interfaces

---

*Document created: January 25, 2026*  
*Next review: After Phase H1 completion*
