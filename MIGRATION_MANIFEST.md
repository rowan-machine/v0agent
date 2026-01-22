# SignalFlow Refactor Migration Manifest

**Purpose:** Track migration progress from monolithic Jinja2 app to decoupled agentic system with multi-agent queues and semantic embeddings.

**Last Updated:** January 22, 2026  
**Current Phase:** 2 - Agent Refactoring (Embedded Agent Adapters)  
**Next Phase:** 2.5 - Complete Adapter Layer

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

Phase 2: Agent Extraction 🔄 IN PROGRESS
├── Arjuna Assistant              ✅ agents/arjuna.py (extracted + adapters)
├── Career Coach                  ✅ agents/career_coach.py (extracted + adapters)
├── DIKW Synthesizer              ✅ agents/dikw_synthesizer.py (extracted, partial adapters)
├── Meeting Analyzer              ✅ agents/meeting_analyzer.py (extracted)
├── Embedded Agent Adapters       🔄 IN PROGRESS
│   ├── Dashboard quick-ask       ✅ ArjunaAgent.quick_ask()
│   ├── Standup feedback          ✅ CareerCoachAgent.analyze_standup()
│   ├── Standup suggest           ✅ CareerCoachAgent.suggest_standup()
│   ├── Career chat               ✅ CareerCoachAgent.chat()
│   ├── Ticket summary            🔴 PENDING → TicketAgent
│   ├── Implementation plan       🔴 PENDING → PlanningAgent
│   ├── Task decomposition        🔴 PENDING → TaskDecompAgent
│   └── DIKW routes (14 calls)    🔴 PENDING → DIKWSynthesizerAgent
└── Modular Agent Design          🔴 PENDING

Phase 3: API Extraction
├── /api/v1/ Endpoints            ⏳ PENDING
└── /api/mobile/ Endpoints        ⏳ PENDING

Phase 4: Multi-Agent Queues & Local Network
├── Agent Message Queue System    ⏳ PENDING
├── mDNS Device Discovery        ⏳ PENDING
└── Local Sync Service           ⏳ PENDING

Phase 5: Embeddings & Semantic Search
├── Backfill Existing Embeddings  ⏳ PENDING
├── Hybrid Search (Keyword + Semantic) ⏳ PENDING
└── Multi-Collection Search      ⏳ PENDING

Phase 6: React Native Mobile App
├── Mobile App Shell              ⏳ PENDING
├── Device Discovery UI           ⏳ PENDING
└── APK Build & Distribution      ⏳ PENDING

Phase 7: Testing & Optimization
└── Full Test Coverage            ⏳ PENDING
```

---

## Embedded Agent Adapter Status

### ✅ Completed Adapters
| Endpoint | File:Line | Agent | Adapter Function |
|----------|-----------|-------|------------------|
| POST /api/dashboard/quick-ask | main.py:564 | ArjunaAgent | quick_ask() |
| POST /api/career/standups | career.py:782 | CareerCoachAgent | analyze_standup_adapter() |
| POST /api/career/standups/suggest | career.py:881 | CareerCoachAgent | suggest_standup_adapter() |
| POST /api/career/chat | career.py | CareerCoachAgent | career_chat_adapter() |

### 🔴 Pending Adapters
| Endpoint | File:Line | Current Implementation | Proposed Agent |
|----------|-----------|----------------------|----------------|
| POST /api/tickets/{id}/generate-summary | tickets.py:359 | ask(prompt) | TicketAgent |
| POST /api/tickets/{id}/generate-plan | tickets.py:404 | ask(prompt, claude-opus) | PlanningAgent |
| POST /api/tickets/{id}/generate-decomposition | tickets.py:473 | ask(prompt) + JSON parse | TaskDecompAgent |
| POST /api/dikw/{id}/promote | main.py:1924 | ask_llm(level_prompts) | DIKWSynthesizerAgent |
| POST /api/dikw/{id}/synthesize | main.py:1993 | ask_llm(synthesis_prompts) | DIKWSynthesizerAgent |
| POST /api/dikw/{id}/merge | main.py:2096 | ask_llm(merge_prompt) | DIKWSynthesizerAgent |
| POST /api/dikw/generate-tags | main.py:2335 | ask_llm(prompt) | DIKWSynthesizerAgent |
| POST /api/dikw/{id}/refine | main.py:2373 | ask_llm(prompt) | DIKWSynthesizerAgent |
| POST /api/dikw/summarize | main.py:2397 | ask_llm(level_prompts) | DIKWSynthesizerAgent |
| POST /api/dikw/{id}/auto-promote | main.py:2433 | ask_llm(promotion_prompts) | DIKWSynthesizerAgent |
| POST /api/query | main.py:2739 | ask_llm(prompt) | QueryAgent |
| POST /api/ai-review | main.py:2965 | ask_llm(prompt) | ReviewAgent |
| POST /api/signals/{id}/interpret | main.py:3016 | ask_llm(prompt) | SignalsAgent |
| POST /api/wisdom/generate | main.py:3098 | ask_llm(wisdom_prompt) | DIKWSynthesizerAgent |

---

## File-by-File Migration Status

### REFACTORED (Already Migrated ✅)

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

### IN PROGRESS (Currently Being Migrated 🔄)

**Embedded Agent Adapters - Phase 2:**
- ✅ Dashboard quick-ask → ArjunaAgent.quick_ask()
- ✅ Standup feedback → CareerCoachAgent.analyze_standup_adapter()
- ✅ Standup suggest → CareerCoachAgent.suggest_standup_adapter()
- ✅ Career chat → CareerCoachAgent.career_chat_adapter()
- 🔄 Ticket summary → TicketAgent (PENDING)
- 🔄 Implementation plan → PlanningAgent (PENDING)
- 🔄 Task decomposition → TaskDecompAgent (PENDING)
- 🔄 DIKW routes → DIKWSynthesizerAgent adapters (PENDING)

### NOT STARTED (Pending Migration 🔴)

**Agent-Specific Prompt Extraction:**
- 🔴 `prompts/agents/arjuna/` - System prompt + intent templates
- 🔴 `prompts/agents/career_coach/` - Insights, feedback, suggestions
- 🔴 `prompts/agents/dikw_synthesizer/` - Promotion and synthesis prompts
- 🔴 `prompts/agents/meeting_analyzer/` - Signal extraction prompts

**Multi-Agent Queue System (Phase 4):**
- 🔴 `src/app/services/agent_queue.py` - Message queue for inter-agent communication
- 🔴 `src/app/services/task_router.py` - Route tasks to appropriate agents
- 🔴 `config/queues.yaml` - Queue configuration (priority, max_size, retry_policy)

**API Layer (Phase 3):**
- 🔴 `src/app/api/v1/__init__.py` - /api/v1 router
- 🔴 `src/app/api/v1/meetings.py` - Meetings CRUD API
- 🔴 `src/app/api/v1/documents.py` - Documents CRUD API
- 🔴 `src/app/api/v1/tickets.py` - Tickets API
- 🔴 `src/app/api/v1/dikw.py` - DIKW API
- 🔴 `src/app/api/v1/signals.py` - Signals API
- 🔴 `src/app/api/v1/search.py` - Hybrid search API
- 🔴 `src/app/api/mobile/__init__.py` - /api/mobile router
- 🔴 `src/app/api/mobile/sync.py` - Device sync endpoints
- 🔴 `src/app/schemas/` - Pydantic request/response models

**Local Network & Multi-Device (Phase 4):**
- 🔴 `src/app/services/discovery_service.py` - mDNS registration
- 🔴 `src/app/services/device_registry.py` - Device tracking
- 🔴 `src/app/services/sync_service.py` - Multi-device sync orchestration
- 🔴 `src/app/services/sync_conflict.py` - Conflict resolution
- 🔴 `src/app/services/offline_queue.py` - Mobile offline writes

**Enhanced Search (Phase 5):**
- 🔴 `src/app/services/semantic_search.py` - Hybrid search implementation
- 🔴 `src/app/services/search_hybrid.py` - Keyword + embedding search
- 🔴 `src/app/mcp/embedding_backfill.py` - Bulk embedding generation

**Mobile App (Phase 6):**
- 🔴 `mobile/` - React Native Expo project
- 🔴 `mobile/src/App.tsx` - Main app shell
- 🔴 `mobile/src/services/discovery.ts` - mDNS discovery
- 🔴 `mobile/src/services/api.ts` - API client
- 🔴 `mobile/src/services/sync.ts` - Sync manager
- 🔴 `mobile/eas.json` - Expo Application Services config
- 🔴 `mobile/app.json` - Expo app configuration

**Testing (Phase 7):**
- 🔴 `tests/agents/` - Agent unit tests
- 🔴 `tests/api/` - API integration tests
- 🔴 `tests/services/` - Service tests
- 🔴 `tests/sync/` - Multi-device sync tests
- 🔴 `tests/mobile/` - Mobile integration tests

**Database Schema:**
- 🔴 `scripts/migrations/005_device_registry.sql` - Device tracking tables
- 🔴 `scripts/migrations/006_sync_queue.sql` - Sync queue tables
- 🔴 `scripts/migrations/007_agent_interactions.sql` - Agent logging tables
- 🔴 `scripts/migrations/008_database_indexes.sql` - Performance indexes

**Documentation:**
- 🔴 `docs/ARCHITECTURE.md` - System architecture overview
- 🔴 `docs/AGENT_GUIDE.md` - How to create new agents
- 🔴 `docs/API_REFERENCE.md` - REST API documentation
- 🔴 `docs/MULTI_DEVICE_SETUP.md` - Multi-device configuration guide
- 🔴 `docs/MOBILE_APP_GUIDE.md` - Mobile app installation and usage

---

## Legacy Code to Preserve During Refactoring

**These files should continue working during refactoring (maintain backward compatibility):**

1. ✅ `src/app/main.py` - Keep Jinja2 routes working alongside new APIs
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

### Code Quality
- [ ] Single Responsibility Principle - One class = one reason to change
- [ ] Dependency Injection - Pass dependencies, don't create them
- [ ] Interface Segregation - Small, focused interfaces
- [ ] DRY (Don't Repeat Yourself) - Extract common patterns
- [ ] SOLID Principles - Follow all five principles

### Testing
- [ ] Write tests BEFORE moving code (refactor with safety net)
- [ ] Mock external dependencies (LLM, database)
- [ ] Test edge cases and error scenarios
- [ ] Keep old tests passing during refactor (green bar always)
- [ ] Add integration tests for new APIs

### Process
- [ ] Small, focused commits (one feature per commit)
- [ ] Keep old code working (adapter pattern, backward compatibility)
- [ ] Use feature flags to toggle between old/new code
- [ ] Measure performance before and after
- [ ] Document why changes were made (not just what)

### Git Strategy
- [ ] Create a `refactor/phase-N` branch per phase
- [ ] Merge to `main` only when tests pass
- [ ] Keep commit history clean and meaningful
- [ ] Use tags for phase milestones: `phase-1-complete`, `phase-2-complete`

### Database
- [ ] Use migrations, don't mutate schema directly
- [ ] Make migrations reversible (up/down)
- [ ] Test migrations on data
- [ ] Add new indexes before heavy queries
- [ ] Denormalize carefully (document why)

### Documentation
- [ ] Update README with new endpoints
- [ ] Document migration path for users
- [ ] Keep architecture diagrams current
- [ ] Example: "Before refactor: X, After: Y, Why: Z"

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

### Phase 2: Agent Refactoring
- [ ] 4 agents extracted
- [ ] All old prompts migrated to YAML
- [ ] Agent-specific tests passing
- [ ] /api/v1 calls working alongside legacy

### Phase 3: API Layer
- [ ] /api/v1/* endpoints complete
- [ ] /api/mobile/* endpoints complete
- [ ] OpenAPI docs generated
- [ ] Frontend calls new APIs

### Phase 4: Multi-Device & Queues
- [ ] Agent queues working
- [ ] mDNS discovery operational
- [ ] Device registry populated
- [ ] Work ↔ Personal device sync

### Phase 5: Embeddings
- [ ] All existing content embedded
- [ ] Hybrid search (keyword + semantic)
- [ ] Dedup detection > 85% accuracy
- [ ] Mobile app can search offline

### Phase 6: Mobile App
- [ ] React Native app builds APK
- [ ] Device discovery works
- [ ] Offline mode + queue
- [ ] Sync conflict resolution

### Phase 7: Testing & Polish
- [ ] 80%+ code coverage
- [ ] Performance < 200ms API latency
- [ ] Zero data loss in sync
- [ ] User docs complete

