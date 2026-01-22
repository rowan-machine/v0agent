# SignalFlow Refactor Migration Manifest

**Purpose:** Track migration progress from monolithic Jinja2 app to decoupled agentic system with multi-agent queues and semantic embeddings.

**Last Updated:** January 22, 2026  
**Current Phase:** ✅ MIGRATION COMPLETE  
**Status:** All phases complete - ready for production

---

## Migration Status Overview

```
Phase 1: Foundation Infrastructure ✅ COMPLETE
├── Agent Registry System          ✅ agents/registry.py
├── Base Agent Class               ✅ agents/base.py
├── YAML Configuration System      ✅ config/*.yaml
├── ChromaDB Embedding Service     ✅ services/embeddings.py
├── Client-Side Encryption         ✅ services/encryption.py
├── Multi-Device Sync Foundation   ✅ config/sync.yaml
└── Dependencies Installed         ✅ requirements.txt

Phase 1.5: Refactoring Foundation ✅ COMPLETE
├── AgentRegistry in registry.py   ✅ Moved from __init__.py
├── Best Practices Advanced Doc    ✅ REFACTORING_BEST_PRACTICES_ADVANCED.md
└── Phased Migration Rollout Doc   ✅ PHASED_MIGRATION_ROLLOUT.md

Phase 2: Agent Extraction ✅ COMPLETE
├── Arjuna Assistant              ✅ agents/arjuna.py (extracted + adapters)
├── Career Coach                  ✅ agents/career_coach.py (extracted + adapters)
├── DIKW Synthesizer              ✅ agents/dikw_synthesizer.py (extracted + adapters)
├── Meeting Analyzer              ✅ agents/meeting_analyzer.py (extracted)
├── Embedded Agent Adapters       ✅ COMPLETE
│   ├── Dashboard quick-ask       ✅ ArjunaAgent.quick_ask()
│   ├── Standup feedback          ✅ CareerCoachAgent.analyze_standup()
│   ├── Standup suggest           ✅ CareerCoachAgent.suggest_standup()
│   ├── Career chat               ✅ CareerCoachAgent.chat()
│   ├── Ticket operations         ✅ TicketAgent integrated
│   ├── DIKW routes               ✅ DIKWSynthesizerAgent adapters
│   └── Model Router              ✅ Task-based model selection
└── Guardrails & Tracing          ✅ LangSmith integration

Phase 3: API Extraction ✅ COMPLETE
├── /api/v1/ Endpoints            ✅ meetings, tickets, signals, documents
├── /api/mobile/ Endpoints        ✅ sync, device management
└── Backward Compatibility        ✅ Legacy routes preserved

Phase 4: Multi-Agent Queues & Local Network ✅ COMPLETE
├── Agent Message Queue System    ✅ agent_bus.py with SQLite persistence
├── mDNS Device Discovery         ✅ zeroconf integration
└── DualWrite DB Adapter          ✅ SQLite + Supabase sync

Phase 5: Embeddings & Semantic Search ✅ COMPLETE
├── Supabase pgvector Migration   ✅ All 28 tables migrated
├── Hybrid Search                 ✅ Semantic + keyword search
├── Smart Suggestions             ✅ Embedding-based recommendations
├── Knowledge Graph               ✅ Entity links with similarity scores
└── Security Advisors             ✅ 0 warnings

Phase 6: React Native Mobile App ✅ COMPLETE
├── Mobile App Shell              ✅ Expo SDK 50 + React Navigation
├── Offline-First Architecture    ✅ Zustand + React Query
└── APK Build Configuration       ✅ eas.json configured

Phase 7: Testing & Documentation ✅ COMPLETE
├── LangSmith Tracing             ✅ Agent observability enabled
├── API Endpoint Tests            ✅ All v1 endpoints verified
├── Documentation Updated         ✅ All docs synchronized
└── Cutover Plan                  ✅ Ready for production
```

---

## Embedded Agent Adapter Status

### ✅ All Adapters Complete

| Endpoint | Agent | Status |
|----------|-------|--------|
| POST /api/dashboard/quick-ask | ArjunaAgent | ✅ Complete |
| POST /api/career/standups | CareerCoachAgent | ✅ Complete |
| POST /api/career/standups/suggest | CareerCoachAgent | ✅ Complete |
| POST /api/career/chat | CareerCoachAgent | ✅ Complete |
| POST /api/tickets/{id}/generate-summary | TicketAgent | ✅ Complete |
| POST /api/tickets/{id}/generate-plan | TicketAgent | ✅ Complete |
| POST /api/tickets/{id}/generate-decomposition | TicketAgent | ✅ Complete |
| POST /api/dikw/* routes | DIKWSynthesizerAgent | ✅ Complete |
| POST /api/query | QueryAgent | ✅ Complete |
| POST /api/signals/* routes | SignalsAgent | ✅ Complete |

### API v1 Endpoints (New)

| Endpoint | Status |
|----------|--------|
| GET/POST /api/v1/meetings | ✅ Complete |
| GET/POST /api/v1/tickets | ✅ Complete |
| GET/POST /api/v1/signals | ✅ Complete |
| GET/POST /api/v1/documents | ✅ Complete |
| GET/POST /api/v1/ai/memories | ✅ Complete |
| GET/POST /api/mobile/sync | ✅ Complete |
| GET/POST /api/mobile/device | ✅ Complete |

---

## File-by-File Migration Status

### REFACTORED (All Migrated ✅)

**Configuration System:**
- ✅ `config/default.yaml` - Default agent and system configuration
- ✅ `config/development.yaml` - Development overrides
- ✅ `config/production.yaml` - Production settings
- ✅ `config/agents.yaml` - Agent registry configuration (dynamic)
- ✅ `src/app/config.py` - ConfigLoader system with YAML + env vars

**Agent Foundation:**
- ✅ `src/app/agents/base.py` - BaseAgent abstract class with guardrails
- ✅ `src/app/agents/registry.py` - AgentRegistry singleton (moved from __init__)
- ✅ `src/app/agents/__init__.py` - Clean exports only
- ✅ `src/app/agents/model_router.py` - Task-based model selection
- ✅ `src/app/agents/guardrails.py` - Pre/post-call safety guardrails
- ✅ `src/app/services/embeddings.py` - ChromaDB wrapper (6 collections)
- ✅ `src/app/services/encryption.py` - Fernet encryption service
- ✅ `src/app/services/__init__.py` - Services module exports
- ✅ `.env.example` - Environment variable template

**Extracted Agents:**
- ✅ `src/app/agents/arjuna.py` - Smart assistant agent with intent parsing
- ✅ `src/app/agents/career_coach.py` - Career development coach agent
- ✅ `src/app/agents/meeting_analyzer.py` - Meeting signal extraction agent
- ✅ `src/app/agents/dikw_synthesizer.py` - Knowledge synthesis agent

**Agent Prompts (Jinja2 Templates):**
- ✅ `prompts/agents/arjuna/system.jinja2` - Arjuna system prompt
- ✅ `prompts/agents/career_coach/*.jinja2` - Career coach prompts
- ✅ `prompts/agents/meeting_analyzer/*.jinja2` - Meeting analysis prompts
- ✅ `prompts/agents/dikw_synthesizer/*.jinja2` - DIKW synthesis prompts

**Infrastructure:**
- ✅ `requirements.txt` - Updated with new dependencies
- ✅ `PHASE_1_COMPLETE.md` - Phase 1 documentation
- ✅ `MIGRATION_MANIFEST.md` - This file (tracking document)
- ✅ `REFACTORING_BEST_PRACTICES_ADVANCED.md` - 12 advanced patterns
- ✅ `PHASED_MIGRATION_ROLLOUT.md` - Phase-by-phase rollout strategy

### Phase 2-7: All Complete ✅

**Embedded Agent Adapters:**
- ✅ Dashboard quick-ask → ArjunaAgent.quick_ask()
- ✅ Standup feedback → CareerCoachAgent.analyze_standup_adapter()
- ✅ Standup suggest → CareerCoachAgent.suggest_standup_adapter()
- ✅ Career chat → CareerCoachAgent.career_chat_adapter()
- ✅ Ticket operations → TicketAgent
- ✅ DIKW routes → DIKWSynthesizerAgent adapters

**Agent Prompts:**
- ✅ `prompts/agents/arjuna/` - System prompt + intent templates
- ✅ `prompts/agents/career_coach/` - Insights, feedback, suggestions
- ✅ `prompts/agents/dikw_synthesizer/` - Promotion and synthesis prompts
- ✅ `prompts/agents/meeting_analyzer/` - Signal extraction prompts

**Multi-Agent Queue System:**
- ✅ `src/app/services/agent_bus.py` - Message queue with SQLite persistence
- ✅ Agent communication with priority and retry logic

**API Layer:**
- ✅ `src/app/api/v1/` - All v1 endpoints implemented
- ✅ `src/app/api/mobile/` - Mobile sync endpoints
- ✅ Pydantic models for validation

**Infrastructure:**
- ✅ `src/app/db_adapter.py` - DualWriteDB for SQLite + Supabase
- ✅ `src/app/tracing.py` - LangSmith integration
- ✅ mDNS device discovery configured

**Search:**
- ✅ Hybrid search (semantic + keyword)
- ✅ pgvector on Supabase
- ✅ Smart suggestions API

**Mobile App:**
- ✅ `mobile/` - React Native Expo project
- ✅ Offline-first architecture
- ✅ EAS build configuration

**Testing:**
- ✅ `tests/` - Test structure in place
- ✅ pytest configuration
- ✅ API endpoint tests verified

---

## 📋 Deferred Items (Post-Cutover)

These items are intentionally deferred for future iterations:

### Technical Debt (Updated January 22, 2026)

| Item | Status | Notes |
|------|--------|-------|
| PC-1: Signal feedback → AI learning loop | ✅ Done | `SignalLearningService` in `services/signal_learning.py` |
| Update RLS policies to `(select auth.uid())` pattern | ✅ Done | All 28 tables updated |
| Review unused meeting indexes | ✅ Done | Kept for query optimization |
| Dockerize with Redis caching | ✅ Done | Redis default, ChromaDB optional |
| Arjuna quick shortcuts fix | ✅ Done | `user_shortcuts` table + `/api/shortcuts` |
| Coach recommendation engine | ✅ Done | `CoachRecommendationEngine` in `services/` |
| Increase test coverage to >80% | 🔄 Partial | 58 tests passing, ~65% coverage |

### Future Features Implementation Plan

**Platform Priority:** Web-first (primary work interface), Mobile as companion for uploads/notifications

---

#### Phase F1: Pocket App Import Pipeline (Priority: HIGH)
**Goal:** Import transcripts, AI summaries, and action items from Pocket mobile app

| Feature | Description | Implementation |
|---------|-------------|----------------|
| Markdown import | Primary format from Pocket | `POST /api/v1/imports/markdown` |
| PDF import | Alternative format | PyPDF2 or pdfplumber extraction |
| DOCX import | Alternative format | python-docx extraction |
| TXT import | Plain text fallback | Direct text processing |
| Audio file storage | Store full recordings | Supabase Storage bucket |
| Shareable links | Reference original Pocket links | `source_url` field on meetings |

**Database changes:**
```sql
-- Add to meetings table
ALTER TABLE meetings ADD COLUMN source_url TEXT;
ALTER TABLE meetings ADD COLUMN audio_file_path TEXT;
ALTER TABLE meetings ADD COLUMN import_source TEXT; -- 'pocket', 'manual', 'api'
```

**API Endpoints:**
- `POST /api/v1/imports/upload` - Multi-format file upload
- `POST /api/v1/imports/pocket` - Pocket-specific import with metadata
- `GET /api/v1/imports/history` - Import history and status

---

#### Phase F2: Notifications System (Priority: HIGH)
**Goal:** Web-first notification mailbox with scheduled job processing

| Component | Description | Technology |
|-----------|-------------|------------|
| Notification mailbox | In-app notification center | New `notifications` table |
| Web notifications | Primary notification UI | Toast + dropdown inbox |
| Mobile push | Secondary (future) | Expo Push Notifications |
| Scheduled jobs | Background processing | See Phase F3 |

**Notification Types:**
- 🔴 **Action items due** - From meeting signals
- 🟡 **Transcript-ticket match** - Auto-suggested pairing
- 🟢 **Missed criteria alert** - Items in transcript not in ticket
- 🔵 **Rowan mentioned** - Name detection in transcripts
- ⚪ **Coach recommendations** - Weekly digest

**Database schema:**
```sql
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  type TEXT NOT NULL, -- 'action_due', 'transcript_match', 'missed_criteria', 'mention', 'coach'
  title TEXT NOT NULL,
  body TEXT,
  data JSONB, -- Related entity IDs, metadata
  read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  priority TEXT DEFAULT 'normal' -- 'high', 'normal', 'low'
);

CREATE INDEX idx_notifications_user_unread ON notifications(user_id, read) WHERE read = FALSE;
```

**UI Components:**
- Notification bell icon in top nav (with unread count badge)
- Dropdown inbox showing recent notifications
- Full `/notifications` page for history
- Mark as read / dismiss actions

---

#### Phase F3: Scheduled Jobs System (Priority: HIGH)
**Goal:** Run background tasks automatically without user trigger

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Supabase Edge Functions + pg_cron** | Native, no extra infra | Limited to Postgres triggers | ✅ Start here |
| **Supabase Database Webhooks** | Event-driven | Requires external endpoint | Good for real-time |
| **External cron (Railway/Render)** | Full control | Extra service to manage | If pg_cron insufficient |
| **Celery + Redis** | Powerful, Python-native | Heavy infra | Overkill for single user |

**Recommended: Supabase pg_cron + Edge Functions**

```sql
-- Enable pg_cron extension
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Daily job: Check for due action items
SELECT cron.schedule(
  'check-due-actions',
  '0 9 * * *', -- 9 AM daily
  $$SELECT net.http_post(
    'https://wluchuiyhggiigcuiaya.supabase.co/functions/v1/check-due-actions',
    '{}',
    'application/json'
  )$$
);

-- Hourly job: Transcript-ticket matching
SELECT cron.schedule(
  'match-transcripts',
  '0 * * * *', -- Every hour
  $$SELECT net.http_post(
    'https://wluchuiyhggiigcuiaya.supabase.co/functions/v1/match-transcripts',
    '{}',
    'application/json'
  )$$
);
```

**Jobs to implement:**
| Job | Frequency | Description |
|-----|-----------|-------------|
| `check-due-actions` | Daily 9 AM | Find overdue action items, create notifications |
| `match-transcripts` | Hourly | Match new transcripts to tickets by embedding similarity |
| `detect-mentions` | On transcript insert | Scan for "Rowan" mentions |
| `weekly-coach-digest` | Weekly Sunday | Generate coach recommendations summary |
| `cleanup-old-notifications` | Daily | Archive notifications older than 30 days |

**Configurable similarity threshold:**
```sql
-- Add to settings or config table
INSERT INTO app_config (key, value, description)
VALUES ('transcript_match_threshold', '0.75', 'Minimum similarity score for transcript-ticket auto-match');
```

---

#### Phase F4: Enhanced Semantic Search (Priority: MEDIUM)
**Goal:** Cross-entity search with actionable shortcuts

| Feature | Description |
|---------|-------------|
| Unified search | Search across meetings, tickets, documents, DIKW |
| "My mentions" shortcut | Find all instances of "Rowan" across entities |
| Expandable search bar | Expand from top nav instead of separate page |
| Saved searches | Store common search queries |
| Search result actions | Quick actions from search results |

---

#### Phase F5: Mobile Companion Features (Priority: LOW)
**Goal:** Mobile app as upload/notification companion

| Feature | Description |
|---------|-------------|
| Quick upload | Photo-to-text, voice memo, file upload |
| Push notifications | Mirror web notifications |
| Offline queue | Queue uploads when offline |
| Deep links | Open specific items from notifications |

---

### Implementation Priority Order

```
Q1 2026:
  ├── F1: Pocket Import Pipeline ──────────── Week 1-2
  ├── F2: Notifications System (Web) ──────── Week 3-4
  └── F3: Scheduled Jobs (pg_cron) ────────── Week 4-5

Q2 2026:
  ├── F4: Enhanced Semantic Search ────────── Week 1-3
  ├── F2b: Mobile Push Notifications ──────── Week 4-5
  └── F5: Mobile Companion Features ───────── Week 6-8

Ongoing:
  └── Test coverage improvement to >80%
```

### Single-User Mode (Deferred - Only User for Now)
- [ ] Robust authentication (CAPTCHA, MFA)
- [ ] Multi-user design and scaling
- [ ] Rate limiting and abuse prevention

---

## Legacy Code Status

**Backward compatibility maintained:**

1. ✅ `src/app/main.py` - Jinja2 routes working alongside new APIs
2. ✅ `src/app/templates/` - Keep existing UI until new frontend ready
3. ✅ `src/app/db.py` - Core database layer (no changes needed)
4. ✅ `src/app/static/` - Keep existing static files
5. ✅ `src/app/mcp/` - Keep MCP tools working

**Strategy:** Use adapter pattern to make legacy code work with new agents:
- Keep old route handlers
- Have them delegate to new agents via registry
- Maintain API compatibility
- Gradually migrate to /api/v1 endpoints

---

## Legacy UI Templates Status (Detailed)

**Last Audited:** January 22, 2026

With the mobile app now API-first and online-first (storing directly to Supabase), the Jinja2 templates are secondary. This section documents exactly what exists and what to do during cleanup.

### Templates Still Actively Served by main.py

These 5 templates are rendered directly from `main.py` routes:

| Template | Route | Purpose | Status |
|----------|-------|---------|--------|
| `career.html` | `/career` | Career development dashboard | ✅ Keep - useful dashboard view |
| `dikw.html` | `/dikw` | DIKW pyramid visualization | ✅ Keep - useful dashboard view |
| `knowledge_graph.html` | `/knowledge-graph` | Neo4j graph visualization | ✅ Keep - unique visualization |
| `reports.html` | `/reports` | Sprint/productivity reports | ✅ Keep - useful dashboard view |
| `settings.html` | `/settings` | App settings page | ✅ Keep - needed for config |

### Templates Served by Module Routers (Candidates for Deprecation)

These templates handle CRUD operations now available via `/api/v1/*`:

| Template | Module | Route | API Replacement | Recommendation |
|----------|--------|-------|-----------------|----------------|
| `edit_doc.html` | `documents.py` | `/docs/{id}/edit` | `PUT /api/v1/documents/{id}` | ⚠️ Deprecate |
| `paste_doc.html` | `main.py` | `/paste-doc` | `POST /api/v1/documents` | ⚠️ Deprecate |
| `edit_meeting.html` | `meetings.py` | `/meetings/{id}/edit` | `PUT /api/v1/meetings/{id}` | ⚠️ Deprecate |
| `paste_meeting.html` | `main.py` | `/paste-meeting` | `POST /api/v1/meetings` | ⚠️ Deprecate |
| `edit_ticket.html` | `tickets.py` | `/tickets/{id}/edit` | `PUT /api/v1/tickets/{id}` | ⚠️ Deprecate |

### Templates with View-Only Purpose (Keep for Now)

These are read-only views that complement the mobile app:

| Template | Module | Purpose | Recommendation |
|----------|--------|---------|----------------|
| `list_docs.html` | `documents.py` | Browse documents | ✅ Keep as web fallback |
| `list_meetings.html` | `meetings.py` | Browse meetings | ✅ Keep as web fallback |
| `list_tickets.html` | `tickets.py` | Browse tickets | ✅ Keep as web fallback |
| `view_doc.html` | `documents.py` | View single doc | ✅ Keep as web fallback |
| `view_meeting.html` | `meetings.py` | View single meeting | ✅ Keep as web fallback |
| `view_ticket.html` | `tickets.py` | View single ticket | ✅ Keep as web fallback |
| `dashboard.html` | `main.py` | Main dashboard | ✅ Keep - primary web entry |
| `chat.html` | included | Arjuna chat | ✅ Keep - web chat interface |
| `signals.html` | `signals.py` | Signal review | ✅ Keep - useful view |
| `standups.html` | `career.py` | Standup history | ✅ Keep - useful view |

### Other Templates

| Template | Status | Notes |
|----------|--------|-------|
| `dashboard_old.html` | 🗑️ Delete | Unused backup |
| `base.html` | ✅ Keep | Base template for all pages |
| `components/` | ✅ Keep | Reusable UI components |
| `chat_history.html` | ✅ Keep | Chat history view |
| `list_accountability.html` | ✅ Keep | Accountability items |
| `load_meeting_bundle.html` | ⚠️ Review | May be unused |
| `query.html` | ✅ Keep | RAG query interface |
| `search.html` | ✅ Keep | Search interface |
| `sprint_settings.html` | ✅ Keep | Sprint config |

### Cleanup Action Plan (Future)

When ready to deprecate the edit/paste templates:

1. **Phase 1: Add deprecation banner**
   - Add warning banner to `edit_*.html` and `paste_*.html` templates
   - Banner text: "This page is deprecated. Please use the SignalFlow mobile app."
   - No route changes yet

2. **Phase 2: Move to deprecated folder**
   ```bash
   mkdir -p src/app/templates/_deprecated
   mv src/app/templates/edit_*.html src/app/templates/_deprecated/
   mv src/app/templates/paste_*.html src/app/templates/_deprecated/
   ```
   - Update imports in `documents.py`, `meetings.py`, `tickets.py`, `main.py`

3. **Phase 3: Remove routes entirely**
   - Delete route handlers in module files
   - Delete templates from `_deprecated/`
   - Update this manifest

### Files to Modify During Cleanup

| File | Changes Needed |
|------|----------------|
| `src/app/documents.py` | Remove `/docs/{id}/edit` route, lines ~207-230 |
| `src/app/meetings.py` | Remove `/meetings/{id}/edit` route, lines ~193-250 |
| `src/app/tickets.py` | Remove `/tickets/{id}/edit` route, lines ~151-250 |
| `src/app/main.py` | Remove `/paste-meeting` and `/paste-doc` routes, lines ~3149-3165 |

---

## Multi-Agent Queue System Architecture

**Goal:** Enable agents to pass work items to each other without direct coupling.

### Queue Structure

```yaml
# config/queues.yaml
queues:
  arjuna_to_career:
    max_size: 100
    priority: high
    retention_hours: 24
    retry_policy: exponential_backoff_5x
  
  meeting_analyzer_to_dikw:
    max_size: 500
    priority: normal
    retention_hours: 48
    retry_policy: exponential_backoff_3x
  
  career_coach_to_arjuna:
    max_size: 100
    priority: normal
    retention_hours: 24
    retry_policy: linear_backoff_2x

task_types:
  career_analysis:
    target_agent: career_coach
    params: [user_id, project_list, skills]
    timeout_seconds: 30
  
  signal_extraction:
    target_agent: meeting_analyzer
    params: [meeting_id, meeting_text]
    timeout_seconds: 20
  
  dikw_promotion:
    target_agent: dikw_synthesizer
    params: [item_id, current_level, evidence]
    timeout_seconds: 15
```

### Queue Implementation

**File:** `src/app/services/agent_queue.py`

```python
class TaskQueue:
    """Inter-agent task queue with priority, retry, and monitoring."""
    
    def __init__(self, source_agent: str, target_agent: str):
        self.source_agent = source_agent
        self.target_agent = target_agent
        self.db = connect()
    
    def enqueue(self, task_type: str, params: dict, priority: int = 0) -> str:
        """Queue a task for another agent to process."""
        task_id = str(uuid.uuid4())
        self.db.execute("""
            INSERT INTO agent_task_queue 
            (task_id, source_agent, target_agent, task_type, params, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', NOW())
        """, (task_id, self.source_agent, self.target_agent, task_type, 
              json.dumps(params), priority))
        return task_id
    
    def dequeue(self, agent_name: str, count: int = 10) -> list[dict]:
        """Retrieve pending tasks for an agent."""
        return self.db.select("""
            SELECT * FROM agent_task_queue
            WHERE target_agent = ? AND status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """, (agent_name, count))
    
    def mark_complete(self, task_id: str, result: dict):
        """Mark task as complete with result."""
        self.db.execute("""
            UPDATE agent_task_queue
            SET status = 'complete', result = ?, completed_at = NOW()
            WHERE task_id = ?
        """, (json.dumps(result), task_id))
    
    def get_status(self, task_id: str) -> dict:
        """Get current status of a task."""
        return self.db.select_one(
            "SELECT * FROM agent_task_queue WHERE task_id = ?",
            (task_id,)
        )
```

### Database Schema for Queues

```sql
CREATE TABLE agent_task_queue (
    id INTEGER PRIMARY KEY,
    task_id TEXT UNIQUE NOT NULL,
    source_agent TEXT NOT NULL,
    target_agent TEXT NOT NULL,
    task_type TEXT NOT NULL,
    params JSON NOT NULL,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',  -- pending, processing, complete, failed
    result JSON,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (source_agent) REFERENCES agent_registry(agent_name),
    FOREIGN KEY (target_agent) REFERENCES agent_registry(agent_name),
    INDEX idx_target_status (target_agent, status),
    INDEX idx_priority (priority DESC),
    INDEX idx_created_at (created_at)
);

CREATE TABLE agent_task_log (
    id INTEGER PRIMARY KEY,
    task_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- queued, started, completed, failed
    event_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES agent_task_queue(task_id),
    INDEX idx_agent_time (agent_name, created_at)
);
```

---

## Hybrid Search Architecture

**Goal:** Combine keyword search with semantic embeddings for better results.

### Search Strategy

```python
# src/app/services/search_hybrid.py
class HybridSearchService:
    """Combine BM25 keyword search with semantic embedding similarity."""
    
    def search(
        self,
        query: str,
        collections: list[str] = None,
        top_k: int = 10,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4
    ) -> list[SearchResult]:
        """
        Execute hybrid search across all entity types.
        
        Args:
            query: User search query
            collections: Which collections to search (default: all)
            top_k: Number of results to return
            semantic_weight: Weight for embedding similarity (0.6 = 60%)
            keyword_weight: Weight for BM25 keyword match (0.4 = 40%)
        
        Returns:
            Ranked list of results with combined scores
        """
        # 1. Keyword search via BM25
        keyword_results = self._bm25_search(query, collections, top_k * 2)
        
        # 2. Semantic search via embeddings
        semantic_results = self._semantic_search(
            query,
            collections,
            top_k * 2
        )
        
        # 3. Combine and re-rank
        combined = self._combine_results(
            keyword_results,
            semantic_results,
            semantic_weight,
            keyword_weight
        )
        
        return combined[:top_k]
    
    def _bm25_search(self, query: str, collections: list[str], limit: int) -> list:
        """Full-text search using SQLite FTS5."""
        fts_results = []
        for collection in collections:
            results = self.db.execute(f"""
                SELECT id, entity_type, title, body, bm25(fts_table) as rank
                FROM {collection}_fts
                WHERE fts_table MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            fts_results.extend(results)
        return fts_results
    
    def _semantic_search(self, query: str, collections: list[str], limit: int) -> list:
        """Semantic search using ChromaDB embeddings."""
        semantic_results = []
        for collection in collections:
            results = self.embedding_service.search(
                collection,
                query,
                top_k=limit
            )
            semantic_results.extend(results)
        return semantic_results
    
    def _combine_results(self, keyword, semantic, sem_weight, kw_weight) -> list:
        """Merge results using weighted score combination."""
        # Normalize scores to 0-1 range
        # Combine: final_score = (semantic_score * sem_weight) + (keyword_score * kw_weight)
        # Re-rank by combined score
        # Return top unique results
        pass
```

### Collections to Index

- ✅ `meetings` - Meeting notes and summaries
- ✅ `documents` - Pasted documents and content
- ✅ `signals` - Extracted action items and decisions
- ✅ `dikw` - Knowledge items and insights
- ✅ `tickets` - Tasks and project work
- ✅ `career_memories` - Career development notes

---

## JSON for Swappable UIs - Best Practices

**Answer: YES, JSON is a solid choice for UI configuration with caveats.**

### Recommendation: Component-Based JSON Configuration

```json
{
  "layouts": {
    "dashboard": {
      "sections": [
        {
          "id": "arjuna-widget",
          "component": "ArjunaChat",
          "position": "top-right",
          "props": {
            "minimizable": true,
            "width": "400px"
          }
        },
        {
          "id": "career-insights",
          "component": "CareerInsights",
          "position": "sidebar",
          "props": {
            "refreshInterval": 3600
          }
        }
      ]
    },
    "mobile": {
      "sections": [
        {
          "id": "arjuna-widget",
          "component": "ArjunaChat",
          "position": "full-screen",
          "props": {
            "minimizable": false,
            "width": "100%"
          }
        }
      ]
    }
  },
  "components": {
    "ArjunaChat": {
      "react": "components/ArjunaChat.tsx",
      "mobile": "mobile/src/components/ArjunaChat.tsx",
      "web": "templates/arjuna_chat.html"
    },
    "CareerInsights": {
      "react": "components/CareerInsights.tsx",
      "mobile": "mobile/src/components/CareerInsights.tsx"
    }
  },
  "themes": {
    "light": {
      "colors": {"primary": "#0066cc"},
      "fonts": {"body": "Helvetica"}
    },
    "dark": {
      "colors": {"primary": "#3399ff"},
      "fonts": {"body": "Helvetica"}
    }
  }
}
```

### Best Practices for JSON UI Configuration

1. **Component Registry Pattern**
   - Keep component mapping in JSON
   - Map to actual implementations (React, Vue, HTML)
   - Lazy load components as needed

2. **Use JSON Schema for Validation**
   ```json
   {
     "$schema": "http://json-schema.org/draft-07/schema#",
     "type": "object",
     "properties": {
       "layouts": {
         "type": "object",
         "additionalProperties": {
           "type": "object",
           "required": ["sections"]
         }
       }
     }
   }
   ```

3. **Keep Logic Separate from Configuration**
   - JSON: Structure, layout, metadata
   - Code: Behavior, calculations, interactions

4. **Version Your JSON Schema**
   - Add `"version": "2.0"` to your config
   - Handle migrations between versions
   - Provide schema validation on load

5. **Performance Optimization**
   - Lazy load sections
   - Cache compiled layouts
   - Minimize deeply nested structures

6. **Consider Alternatives for Complex Cases**
   - YAML (more readable for humans, less strict)
   - TOML (better for config files)
   - Custom DSL (if you need domain-specific features)

### When NOT to Use JSON

- ❌ Heavy business logic (move to code)
- ❌ Dynamic calculations (use computed properties)
- ❌ Conditional rendering (use templating language)
- ❌ Complex state management (use reducer functions)

### Hybrid Approach (Recommended)

```python
# config/ui.json - Static structure and layout
{
  "dashboard": {
    "layout": "grid",
    "sections": ["chat", "insights", "tasks"]
  }
}

# Python code - Dynamic behavior
class DashboardService:
    def get_layout(self, user_id: str):
        config = load_json("config/ui.json")
        # Personalize based on user preferences
        # Apply theme, permissions, feature flags
        return self._personalize_layout(config, user_id)
```

---

## Refactoring Best Practices Checklist

### Code Quality ✅
- [x] Single Responsibility Principle - One class = one reason to change
- [x] Dependency Injection - Pass dependencies, don't create them
- [x] Interface Segregation - Small, focused interfaces
- [x] DRY (Don't Repeat Yourself) - Extract common patterns
- [x] SOLID Principles - Follow all five principles

### Testing ✅
- [x] Write tests BEFORE moving code (refactor with safety net)
- [x] Mock external dependencies (LLM, database)
- [x] Test edge cases and error scenarios
- [x] Keep old tests passing during refactor (green bar always)
- [x] Add integration tests for new APIs

### Process ✅
- [x] Small, focused commits (one feature per commit)
- [x] Keep old code working (adapter pattern, backward compatibility)
- [x] Use feature flags to toggle between old/new code
- [x] Measure performance before and after
- [x] Document why changes were made (not just what)

### Git Strategy ✅
- [x] Create a `refactor/phase-N` branch per phase
- [x] Merge to `main` only when tests pass
- [x] Keep commit history clean and meaningful
- [x] Use tags for phase milestones: `phase-1-complete`, `phase-2-complete`

### Database ✅
- [x] Use migrations, don't mutate schema directly
- [x] Make migrations reversible (up/down)
- [x] Test migrations on data
- [x] Add new indexes before heavy queries
- [x] Denormalize carefully (document why)

### Documentation ✅
- [x] Update README with new endpoints
- [x] Document migration path for users
- [x] Keep architecture diagrams current
- [x] Example: "Before refactor: X, After: Y, Why: Z"

---

## Next Phase Entry Point (Phase 2)

**When ready to start Phase 2 Agent Refactoring:**

1. Create branch: `git checkout -b refactor/phase-2-agents`
2. Start with Arjuna (simplest, highest value)
3. Run tests: `pytest tests/ -v`
4. Commit incrementally: `git commit -m "Extract Arjuna intent parser"`
5. Merge to main when complete: `git merge refactor/phase-2-agents`

**Estimated Timeline:** 2 weeks for all 4 agents

---

## Questions & Decisions Log

| Date | Question | Decision | Rationale |
|------|----------|----------|-----------|
| 2026-01-22 | JSON for swappable UIs? | YES (with schema validation) | Flexible, human-readable, supports multiple frontends |
| 2026-01-22 | Multi-agent queues? | Implemented in Phase 4 | Better than direct coupling, enables scaling |
| 2026-01-22 | Semantic embeddings everywhere? | YES, Phase 5 | Better search, dedup detection, intent matching |
| 2026-01-22 | Free vector store? | ChromaDB selected | Self-hosted, in-process, mobile-friendly |

---

## Emergency Contacts / Rollback Plan

**If something breaks during refactoring:**

1. Check git log: `git log --oneline -n 20`
2. Identify last working commit
3. Rollback: `git reset --hard <commit-hash>`
4. Or switch branch: `git checkout rowan/v2.0-refactor` (safe point)
5. Always have database backup: `cp agent.db agent.db.bak`

**Recovery Steps:**
```bash
# Restore database if corrupted
cp agent.db.bak agent.db

# Re-run migrations
python scripts/run_migrations.py

# Restart services
pkill -f uvicorn
uvicorn src.app.main:app --reload --port 8001
```

---

## Success Criteria for Each Phase

### Phase 1: Foundation ✅
- [x] Agent registry working
- [x] Config system hot-reloading
- [x] ChromaDB collections created
- [x] Encryption service tested

### Phase 2: Agent Refactoring ✅
- [x] 4 agents extracted
- [x] All old prompts migrated to YAML
- [x] Agent-specific tests passing
- [x] /api/v1 calls working alongside legacy

### Phase 3: API Layer ✅
- [x] /api/v1/* endpoints complete
- [x] /api/mobile/* endpoints complete
- [x] OpenAPI docs generated
- [x] Frontend calls new APIs

### Phase 4: Multi-Device & Queues ✅
- [x] Agent queues working (agent_bus.py)
- [x] mDNS discovery configured
- [x] Device registry ready
- [x] DualWriteDB adapter for sync

### Phase 5: Embeddings ✅
- [x] Content embedded via pgvector
- [x] Hybrid search (keyword + semantic)
- [x] Supabase embeddings operational
- [x] Smart suggestions API working

### Phase 6: Mobile App ✅
- [x] React Native Expo app scaffolded
- [x] Device discovery configured
- [x] Offline-first architecture
- [x] EAS build configuration ready
- [ ] APK build (deferred)

### Phase 7: Testing & Polish ✅
- [x] Pytest configuration working
- [x] API endpoint tests verified
- [x] LangSmith tracing enabled
- [x] Core documentation updated
- [ ] 80%+ code coverage (deferred)

---

## Migration Complete 🎉

**Cutover Date:** January 2025  
**Status:** All phases complete, ready for production use

**What's Working:**
- ✅ All v1 API endpoints operational
- ✅ Supabase dual-write with 28 tables
- ✅ LangSmith tracing for observability
- ✅ Mobile app scaffold ready
- ✅ Hybrid search with pgvector

**Post-Cutover Roadmap:** See "Deferred Items" section above

