# Phased Migration Rollout Plan

**Purpose:** Define the specific order and checkpoints for migrating code, ensuring zero breaking changes and maximum safety.

**Key Principle:** Local refactoring first (agent extraction), then database evolution (new columns/tables), then sync logic, finally embeddings and mobile.

---

## 🔄 Current Migration Status

**Last Updated:** 2025-01-22

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 0: Setup | ✅ Complete | 100% |
| Phase 1: Local Refactoring | ✅ Complete | 100% |
| Phase 2: Database Evolution (Adapters) | ✅ Complete | 100% |
| Phase 3: API Modernization | ✅ Complete | 100% |
| Phase 4: Infrastructure | ✅ Complete | 100% |
| Phase 5: Embeddings & Smart Features | 🔄 In Progress | 60% |
| Phase 6: Mobile App | 🔲 Not Started | 0% |
| Phase 7: Testing & Documentation | 🔲 Not Started | 0% |

### Phase 5 Progress (Supabase Migration)
- [x] P5.1: Migrate to pgvector on Supabase
- [x] P5.2: Implement hybrid search (semantic + keyword)
- [x] P5.3: Verify encryption at rest and in transit (SSL/TDE confirmed)
- [x] P5.4: Fix Supabase security advisors (search_path for functions)
- [x] P5.5: Migrate signal_status table (42 records)
- [x] P5.6: Migrate sprint_settings table (1 record)
- [x] P5.7: Migrate career_chat_updates table (4 records)
- [x] P5.8: Verify data integrity (FK relationships)
- [ ] P5.9: Add smart suggestions based on embeddings
- [ ] P5.10: Knowledge graph connections
- [ ] P5.11: Intelligent document linking
- [ ] P5.12: Complete schema parity (37 SQLite → 14+ Supabase tables)

### Security Status ✅ (Verified 2025-01-22)
- **Encryption in Transit**: SSL/TLS enabled (`ssl_enabled: on`)
- **Encryption at Rest**: Supabase TDE (Transparent Data Encryption)
- **Secrets Storage**: Vault available (AEAD encryption)
- **Function Security**: search_path=public for all search functions
- **Security Advisors**: 0 warnings

---

## Executive Summary

```
Phase 0: Setup (0 days) - Directory structure, no code changes
├─ Checkpoint: src/app/agents/ directory structure ready
└─ Risk: None (purely setup)

Phase 1: Local Refactoring (10-14 days) - Extract agents, no database changes
├─ Checkpoint 1.1: AgentRegistry moved to agents/registry.py
├─ Checkpoint 1.2: ArjunaAgent extracted (agents/arjuna.py)
├─ Checkpoint 1.3: CareerCoachAgent extracted (agents/career_coach.py)
├─ Checkpoint 1.4: MeetingAnalyzerAgent extracted (agents/meeting_analyzer.py)
├─ Checkpoint 1.5: DIKWSynthesizerAgent extracted (agents/dikw_synthesizer.py)
├─ Checkpoint 1.6: Adapter layer working (old code → new agents)
├─ Checkpoint 1.7: Model auto-selection router + user override (per agent)
├─ Checkpoint 1.8: Guardrail and self-reflection scaffolding (hooks + flags)
└─ Risk: Medium (code refactoring) - MITIGATED by adapter pattern

Phase 2: Database Evolution (7-10 days) - Add new tables/columns, keep old
├─ Checkpoint 2.1: New schema (meeting_v2, device_registry, etc.)
├─ Checkpoint 2.2: Compatibility views created
├─ Checkpoint 2.3: Migration script for existing data
├─ Checkpoint 2.4: Old code still works with new tables
└─ Risk: High (database) - MITIGATED by views and old table preservation

Phase 3: API Modernization (7-10 days) - New /api/v1 endpoints
├─ Checkpoint 3.1: /api/v1/meetings, /api/v1/signals, etc. working
├─ Checkpoint 3.2: /api/mobile endpoints for sync
├─ Checkpoint 3.3: Old routes still work (backward compatible)
├─ Checkpoint 3.4: Mobile client can sync via new endpoints
└─ Risk: Medium (API changes) - MITIGATED by API versioning

Phase 4: Multi-Device & Queues (10-14 days) - mDNS, sync, queues
├─ Checkpoint 4.1: mDNS device discovery working
├─ Checkpoint 4.2: TaskQueue system operational
├─ Checkpoint 4.3: Device sync logic correct (no data loss)
├─ Checkpoint 4.4: Conflict resolution tested
└─ Risk: High (sync logic) - MITIGATED by extensive testing

Phase 5: Embeddings & Hybrid Search (7-10 days) - Add embeddings to all types
├─ Checkpoint 5.1: Embeddings generated for all 6 entity types
├─ Checkpoint 5.2: ChromaDB collections populated
├─ Checkpoint 5.3: Hybrid search (BM25 + semantic) working
├─ Checkpoint 5.4: No breaking changes to search API
├─ Checkpoint 5.5: Concept mindmaps (cross-meeting, tag-drillable) generated
└─ Risk: Low (additive only) - No existing data modified

Phase 6: Mobile App (14-21 days) - React Native build
├─ Checkpoint 6.1: React Native project initialized
├─ Checkpoint 6.2: Offline mode working
├─ Checkpoint 6.3: APK builds successfully
└─ Risk: Low (new code only) - No risk to server

Phase 7: Cutover (3-5 days) - Switch to new code, retire legacy
├─ Checkpoint 7.1: All tests passing
├─ Checkpoint 7.2: Old code completely unused (monitored)
├─ Checkpoint 7.3: Legacy code deleted
├─ Checkpoint 7.4: Documentation updated
└─ Risk: Low (well-tested) - Can rollback if needed

Total Time: 8-9 weeks
Risk Level: LOW (with mitigation strategies in place)
```

---

## Detailed Phase-by-Phase Rollout

### Phase 0: Setup (Parallel with Phase 1)
**Duration:** 0 days (happens immediately)
**Risk:** None

**Checkpoint 0.1: Reorganize agents/ directory**

```
Before:
src/app/agents/
├── __init__.py          (AgentRegistry code + imports)
└── base.py              (BaseAgent, AgentConfig)

After:
src/app/agents/
├── __init__.py          (Only imports, no code)
├── base.py              (BaseAgent, AgentConfig - UNCHANGED)
├── registry.py          (AgentRegistry - MOVED HERE)
├── arjuna.py            (Will be extracted here)
├── career_coach.py      (Will be extracted here)
├── meeting_analyzer.py  (Will be extracted here)
├── dikw_synthesizer.py  (Will be extracted here)
└── prompts/             (New directory for agent-specific prompts)
    ├── arjuna/
    │   ├── system.jinja2
    │   ├── parse_intent.jinja2
    │   └── clarify_intent.jinja2
    ├── career_coach/
    ├── meeting_analyzer/
    └── dikw_synthesizer/
```

**Action:** Create agents/registry.py by moving code from __init__.py

---

### Phase 1: Local Refactoring (Code Extraction)
**Duration:** 10-14 days
**Risk:** Medium (code refactoring, but no database changes)
**Mitigation:** Adapter pattern, comprehensive tests, feature flags

**Checkpoint 1.1: AgentRegistry Refactoring**

```python
# src/app/agents/registry.py (NEW FILE)

from typing import Dict, Type
import yaml
from .base import BaseAgent

class AgentRegistry:
    """Centralized agent management system."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.agents: Dict[str, BaseAgent] = {}
        self.config = self._load_config()
        self._initialized = True
    
    def _load_config(self) -> dict:
        """Load agent configuration from YAML."""
        with open("config/default.yaml") as f:
            return yaml.safe_load(f)
    
    def register(self, name: str, agent: BaseAgent):
        """Register an agent."""
        self.agents[name] = agent
    
    def get(self, name: str) -> BaseAgent:
        """Get agent by name."""
        if name not in self.agents:
            raise ValueError(f"Agent {name} not registered")
        return self.agents[name]
    
    def list_agents(self) -> list[str]:
        """List all registered agents."""
        return list(self.agents.keys())

# src/app/agents/__init__.py (SIMPLIFIED)

from .base import BaseAgent, AgentConfig
from .registry import AgentRegistry

_registry = None

def get_registry() -> AgentRegistry:
    """Get global registry singleton."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry

__all__ = ["BaseAgent", "AgentConfig", "AgentRegistry", "get_registry"]
```

**Verification:**
```python
# Test that old imports still work
from src.app.agents import get_registry

registry = get_registry()
registry.get("arjuna")  # Should work
```

**Checkpoint 1.2-1.5: Extract Agents (See MIGRATION_MANIFEST.md for details)**

Each agent extraction follows the same pattern:
1. Create agents/[agent_name].py with full agent class
2. Move prompts to prompts/agents/[agent_name]/
3. Update imports in main.py to use new agent
4. Register agent in AgentRegistry
5. Create adapter in old file for backward compatibility

**Example: Arjuna**

```python
# src/app/agents/arjuna.py (NEW FILE)

from typing import Optional, Dict
from .base import BaseAgent

class ArjunaAgent(BaseAgent):
    """Intelligence assistant for focus recommendations."""
    
    NAME = "arjuna"
    DESCRIPTION = "Arjuna: Focus & Priority Intelligence"
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.model = config.get("model", "gpt-4o-mini")
    
    async def parse_intent(self, message: str) -> dict:
        """Parse user intent from message."""
        prompt = self.load_prompt("parse_intent.jinja2")
        response = await self.ask_llm(prompt.format(message=message))
        return self.parse_json_response(response)
    
    # ... rest of agent methods

# src/app/api/assistant.py (ADAPTER - OLD FILE, MODIFIED)

from src.app.agents import get_registry

class Arjuna:
    """DEPRECATED: Use ArjunaAgent instead.
    
    This adapter maintains backward compatibility.
    All calls delegate to the new ArjunaAgent.
    """
    
    def __init__(self):
        self._agent = get_registry().get("arjuna")
    
    async def parse_intent(self, message: str):
        """Deprecated: Use _agent.parse_intent() instead."""
        return await self._agent.parse_intent(message)
    
    # ... other deprecated methods redirect to agent
```

**Checkpoint 1.6: Adapter Layer Verification**

```python
# Test backward compatibility

# OLD WAY (still works)
from src.app.api.assistant import Arjuna
arjuna = Arjuna()
result = arjuna.parse_intent("what should I focus on?")

# NEW WAY (preferred)
from src.app.agents import get_registry
agent = get_registry().get("arjuna")
result = await agent.parse_intent("what should I focus on?")

# Both return identical results
assert old_result == new_result
```

**Exit Criteria:**
- [ ] All 4 agents extracted (Arjuna, Career Coach, Meeting Analyzer, DIKW Synthesizer)
- [ ] Adapters in place for all agents
- [ ] All old tests passing
- [ ] New agent tests passing
- [ ] AgentRegistry moved to agents/registry.py
- [ ] Zero breaking changes to external API
- [ ] Feature flag ready (set use_new_arjuna: false for gradual rollout)

**Checkpoint 1.7: Model auto-selection router + user override**

- Add a lightweight model router per agent with clear defaults (small model for classification, larger for synthesis) and a deterministic fallback.
- Allow explicit overrides from user/config (`model` param or agent config) and log the chosen model for observability.
- Keep routing policy declarative (YAML/JSON) so we can later plug in LangChain/LangGraph/LangSmith without touching call sites.

**Checkpoint 1.8: Guardrail and self-reflection scaffolding**

- Add pre/post hook interfaces on BaseAgent to run guardrails (input filters, safety prompts) and self-reflection passes (critique/sanity check) with feature flags to keep them optional.
- Provide no-op default implementations plus stub prompts stored alongside each agent’s prompts directory.
- Emit metrics for when guardrails or reflection paths are invoked to inform later tuning.

**LangChain/LangGraph/LangSmith (optional sandbox in Phase 1)**
- Prototype the router/guardrail hooks against these libraries in isolation to validate fit; keep production path plain Python until stability is proven.

**Claude Opus 4.5 prompt pack (use Opus for these tasks)**
- Apply Opus on checkpoints 1.7 (model routing), 1.8 (guardrails/reflection), and 5.5 (concept mindmaps) instead of smaller models.
- Send these prompts verbatim to Opus:
    - Model routing policy review:
        ```
        You are reviewing an agent model-routing policy. Goal: small model for classification/routing; larger for synthesis/long-context; deterministic fallback. Input: YAML/JSON policy. Deliver: gaps, unsafe fallbacks, missing latency/$$ cost guards, and concrete thresholds (token length, latency budgets). Include a recommended default model map per task type and a rollback/fallback rule.
        ```
    - Guardrail + reflection critique:
        ```
        You are designing guardrails and self-reflection hooks for an agent. Input: pre/post hook descriptions + sample prompts. Deliver: adversarial test cases, safety prompt improvements, refusal patterns, and a minimal critique loop that catches hallucinations or policy violations. Highlight logging/telemetry needed (hit rates, bypass reasons, false positives).
        ```
    - Signal extraction QA (meetings/documents):
        ```
        You are QA’ing signal extraction for meetings/documents. Categories: decisions, actions, blockers, risks, ideas, context notes; sprint-aware; graph relationships. Input: sample extraction output. Deliver: precision/recall risks, category confusion, taxonomy tweaks, and 5 adversarial examples to test.
        ```
    - Concept mindmap schema review:
        ```
        You are reviewing a concept graph design for cross-meeting mindmaps with tag/meeting drill-down. Nodes: concepts, meetings; edges: mentions/co-occurrence. Input: proposed node/edge schema + filters. Deliver: clustering criteria, labeling guidance, pagination/drill-down UX constraints, and caching/persistence advice for repeated queries.
        ```

---

### Phase 2: Database Evolution
**Duration:** 7-10 days
**Risk:** High (database schema changes)
**Mitigation:** Views for compatibility, incremental migrations, rollback procedures

**Checkpoint 2.1: Create New Schema Alongside Old**

```sql
-- Keep old tables, add new ones for multi-device sync

-- EXISTING TABLE (unchanged)
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY,
    name TEXT,
    notes TEXT,
    date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NEW TABLE (with sync metadata)
CREATE TABLE meeting_v2 (
    id INTEGER PRIMARY KEY,
    name TEXT,
    notes TEXT,
    date TEXT,
    synced_from_device TEXT,              -- Which device created it
    last_modified_device TEXT,             -- Last device to modify
    last_modified_at TIMESTAMP,            -- When last modified
    embedding_status TEXT DEFAULT 'pending', -- 'pending', 'completed', 'failed'
    sync_version INTEGER DEFAULT 0,        -- For conflict detection
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for sync queries
CREATE INDEX idx_meeting_v2_synced_from_device ON meeting_v2(synced_from_device);
CREATE INDEX idx_meeting_v2_last_modified_device ON meeting_v2(last_modified_device);
CREATE INDEX idx_meeting_v2_embedding_status ON meeting_v2(embedding_status);

-- NEW TABLE for device registry
CREATE TABLE device_registry (
    id INTEGER PRIMARY KEY,
    device_id TEXT UNIQUE,
    device_name TEXT,
    device_type TEXT,  -- 'laptop', 'desktop', 'mobile'
    last_seen TIMESTAMP,
    ip_address TEXT,
    mdn_name TEXT,  -- e.g., "rowan-macbook.local"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NEW TABLE for task queue (agents passing tasks to each other)
CREATE TABLE agent_task_queue (
    id INTEGER PRIMARY KEY,
    task_id TEXT UNIQUE,
    source_agent TEXT,              -- which agent created this
    target_agent TEXT,              -- which agent should handle it
    priority INTEGER DEFAULT 0,     -- 0=low, 5=high
    status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'complete', 'failed'
    payload TEXT,                   -- JSON payload
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_agent_task_queue_status ON agent_task_queue(status);
CREATE INDEX idx_agent_task_queue_target_agent ON agent_task_queue(target_agent);
```

**Checkpoint 2.2: Create Compatibility Views**

```sql
-- Views allow OLD code to work with NEW tables

-- For old code querying meetings:
CREATE VIEW meetings_unified AS
SELECT 
    id, name, notes, date, created_at,
    'local' as synced_from_device,      -- Default for migrated data
    'unknown' as last_modified_device,
    created_at as last_modified_at,
    'pending' as embedding_status,
    0 as sync_version
FROM meetings
UNION ALL
SELECT 
    id, name, notes, date, created_at,
    synced_from_device,
    last_modified_device,
    last_modified_at,
    embedding_status,
    sync_version
FROM meeting_v2;

-- Same for documents, signals, etc.
-- OLD CODE: SELECT * FROM meetings WHERE id = ?
--   ↓ redirects to:
-- NEW VIEW: SELECT * FROM meetings_unified WHERE id = ?
```

**Migration Strategy:**

```sql
-- Step 1: Create new tables (zero data yet)
-- Step 2: Populate new tables from old data (gradual copy)
-- Step 3: Create views for backward compatibility
-- Step 4: Update code to use new tables (gradual)
-- Step 5: Retire old tables (when code is updated)

-- Example migration for meetings:
BEGIN TRANSACTION;

-- Insert old meetings into new table
INSERT INTO meeting_v2 (id, name, notes, date, synced_from_device, 
                       last_modified_device, last_modified_at, created_at)
SELECT id, name, notes, date, 
       'migrated_from_v1' as synced_from_device,
       'migrated_from_v1' as last_modified_device,
       COALESCE(updated_at, created_at) as last_modified_at,
       created_at
FROM meetings;

COMMIT;
```

**Checkpoint 2.3: Migration Rollback Plan**

```bash
# If Phase 2 fails, rollback is simple:

# Option 1: Feature flag (instant)
set use_new_database: false  # In config/development.yaml

# Option 2: Database rollback
# All old tables still exist, queries revert to views

# Option 3: Full revert
git revert <phase-2-commit>
# Old code still works because adapters are in place
```

**Checkpoint 2.4: Data Sync Verification**

```python
# Verify old and new tables have matching data

def verify_sync():
    old_meetings = db.select("SELECT COUNT(*) FROM meetings")
    new_meetings = db.select("SELECT COUNT(*) FROM meeting_v2")
    
    assert old_meetings == new_meetings, \
        f"Data mismatch: old={old_meetings}, new={new_meetings}"
    
    # Spot-check random records
    for old_id in random.sample(range(1, old_meetings + 1), 10):
        old = db.select("SELECT * FROM meetings WHERE id = ?", (old_id,))
        new = db.select("SELECT * FROM meeting_v2 WHERE id = ?", (old_id,))
        
        assert old.name == new.name
        assert old.notes == new.notes
        assert old.date == new.date
    
    print("✓ Data sync verified")
```

**Exit Criteria:**
- [ ] New tables created (meeting_v2, device_registry, agent_task_queue, etc.)
- [ ] Old data migrated to new tables
- [ ] Compatibility views created
- [ ] Old code still works (tested via adapter layer)
- [ ] New code can read from new tables
- [ ] No data loss
- [ ] Rollback procedure documented and tested

---

### Phase 3: API Modernization
**Duration:** 7-10 days
**Risk:** Medium (API changes)
**Mitigation:** API versioning, backward compatible endpoints

**Checkpoint 3.1: Create /api/v1 Endpoints**

```python
# src/app/api/v1/__init__.py (NEW DIRECTORY)
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json

router = APIRouter(prefix="/api/v1", tags=["v1"])

# src/app/api/v1/meetings.py
@router.get("/meetings")
async def list_meetings(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    device_id: Optional[str] = None
):
    """List meetings with pagination and device filtering."""
    query = "SELECT * FROM meeting_v2"
    params = []
    
    if device_id:
        query += " WHERE synced_from_device = ?"
        params.append(device_id)
    
    query += f" ORDER BY last_modified_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, skip])
    
    meetings = db.select(query, tuple(params))
    return {
        "items": meetings,
        "skip": skip,
        "limit": limit,
        "total": db.select_one("SELECT COUNT(*) as count FROM meeting_v2")["count"]
    }

@router.get("/meetings/{id}")
async def get_meeting(id: int):
    """Get single meeting."""
    meeting = db.select_one("SELECT * FROM meeting_v2 WHERE id = ?", (id,))
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return meeting

@router.post("/meetings")
async def create_meeting(
    name: str,
    notes: str,
    date: str,
    device_id: str,
):
    """Create new meeting."""
    result = db.execute(
        """INSERT INTO meeting_v2 (name, notes, date, synced_from_device, 
           last_modified_device) VALUES (?, ?, ?, ?, ?)""",
        (name, notes, date, device_id, device_id)
    )
    
    return {"id": result.lastrowid, "created": True}

# src/app/main.py (REGISTER ROUTERS)
from src.app.api import v1

app.include_router(v1.router)
```

**Checkpoint 3.2: Mobile Sync Endpoints**

```python
# src/app/api/mobile/__init__.py (NEW)
from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/api/mobile", tags=["mobile"])

# src/app/api/mobile/sync.py
@router.post("/sync")
async def sync_changes(
    device_id: str,
    changes: dict,  # {meetings: [{id, ...}], documents: [...]}
    last_sync_timestamp: Optional[float] = None
):
    """
    Handle multi-device sync.
    
    Device sends its changes, receives what changed on server.
    """
    
    # Get server changes since last sync
    server_changes = get_server_changes(device_id, last_sync_timestamp)
    
    # Apply device changes to server
    apply_device_changes(device_id, changes)
    
    return {
        "success": True,
        "device_id": device_id,
        "server_changes": server_changes,
        "sync_timestamp": time.time(),
        "conflicts": []  # List of conflicts if any
    }

@router.post("/device/register")
async def register_device(
    device_id: str,
    device_name: str,
    device_type: str  # 'laptop', 'mobile', 'desktop'
):
    """Register device for multi-device sync."""
    
    db.execute(
        """INSERT OR REPLACE INTO device_registry 
           (device_id, device_name, device_type, last_seen) 
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
        (device_id, device_name, device_type)
    )
    
    return {"device_id": device_id, "registered": True}

@router.get("/sync-status")
async def get_sync_status(device_id: str):
    """Get sync status for device."""
    
    queue_count = db.select_one(
        "SELECT COUNT(*) as count FROM agent_task_queue WHERE status = 'pending'"
    )
    
    return {
        "device_id": device_id,
        "online": True,
        "pending_tasks": queue_count["count"],
        "last_sync": datetime.now().isoformat()
    }

# src/app/main.py (REGISTER ROUTERS)
from src.app.api import mobile

app.include_router(mobile.router)
```

**Checkpoint 3.3: Backward Compatibility**

```python
# OLD ROUTES (keep working)

# src/app/api/assistant.py
@app.get("/assistant/intent")
async def old_get_intent():
    """Old route. Redirects to new API."""
    # Internally calls new v1 endpoints
    result = await get_meeting(id)
    return result  # Same response format

# test
curl http://localhost:8001/api/v1/meetings  # NEW ✓
curl http://localhost:8001/assistant/meetings  # OLD (still works via adapter) ✓
```

**Exit Criteria:**
- [ ] /api/v1 endpoints for all entities (meetings, documents, signals, dikw)
- [ ] /api/mobile endpoints for sync
- [ ] Old routes still work (backward compatible)
- [ ] OpenAPI docs generated
- [ ] Mobile client can sync via /api/mobile endpoints
- [ ] Pydantic schemas defined for all responses

---

### Phase 4: Multi-Device & Queues
**Duration:** 10-14 days
**Risk:** High (complex distributed logic)
**Mitigation:** Extensive testing, monitoring, rollback procedures

**Checkpoint 4.1: mDNS Device Discovery**

```python
# src/app/services/discovery_service.py (NEW)

from zeroconf import Zeroconf, ServiceInfo
import socket
import logging

logger = logging.getLogger(__name__)

class DiscoveryService:
    """Register and discover devices on local network."""
    
    def __init__(self, device_id: str, device_name: str, port: int = 8001):
        self.device_id = device_id
        self.device_name = device_name
        self.port = port
        self.zeroconf = None
        self.service_info = None
    
    def register(self):
        """Register this device on mDNS."""
        
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        
        service_name = f"{self.device_name}.local"
        
        self.service_info = ServiceInfo(
            "_signalflow._tcp.local.",
            f"{self.device_name}._signalflow._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=self.port,
            properties={
                "device_id": self.device_id,
                "device_name": self.device_name,
                "version": "1.0"
            }
        )
        
        self.zeroconf = Zeroconf()
        self.zeroconf.register_service(self.service_info)
        
        logger.info(f"✓ Registered device: {service_name} ({ip}:{self.port})")
    
    def discover(self) -> list[dict]:
        """Discover other devices on network."""
        
        from zeroconf import ServiceBrowser, ServiceStateChange
        
        devices = []
        
        def on_service_state_change(zeroconf, service_type, name, state_change):
            if state_change == ServiceStateChange.Added:
                info = zeroconf.get_service_info(service_type, name)
                if info:
                    devices.append({
                        "name": info.name,
                        "ip": socket.inet_ntoa(info.addresses[0]),
                        "port": info.port,
                        "device_id": info.properties.get(b"device_id", b"").decode()
                    })
        
        zeroconf = Zeroconf()
        ServiceBrowser(
            zeroconf,
            "_signalflow._tcp.local.",
            handlers=[on_service_state_change]
        )
        
        # Wait for discovery
        import time
        time.sleep(2)
        
        zeroconf.close()
        return devices

# src/app/main.py (INITIALIZE DISCOVERY)
discovery = DiscoveryService(
    device_id=config.get("device_id", "rowan-laptop"),
    device_name=config.get("device_name", "rowan-macbook"),
    port=8001
)
discovery.register()
```

**Checkpoint 4.2: Task Queue System**

```python
# src/app/services/agent_queue.py (NEW)

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class Task:
    task_id: str
    source_agent: str
    target_agent: str
    priority: int  # 0-5
    payload: dict
    status: str = "pending"
    retry_count: int = 0
    max_retries: int = 3

class TaskQueue:
    """Inter-agent task queue with retry logic."""
    
    def __init__(self, db):
        self.db = db
    
    def enqueue(self, source: str, target: str, payload: dict, priority: int = 0):
        """Add task to queue."""
        
        task_id = f"{source}→{target}:{datetime.now().timestamp()}"
        
        self.db.execute(
            """INSERT INTO agent_task_queue 
               (task_id, source_agent, target_agent, priority, payload, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (task_id, source, target, priority, json.dumps(payload))
        )
        
        logger.info(f"✓ Task enqueued: {source} → {target}")
        return task_id
    
    def dequeue(self, agent_name: str, limit: int = 1) -> list[Task]:
        """Get next tasks for agent."""
        
        tasks = self.db.select(
            """SELECT * FROM agent_task_queue 
               WHERE target_agent = ? AND status = 'pending'
               ORDER BY priority DESC, created_at ASC
               LIMIT ?""",
            (agent_name, limit)
        )
        
        # Mark as processing
        for task in tasks:
            self.db.execute(
                "UPDATE agent_task_queue SET status = 'processing', started_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (task["task_id"],)
            )
        
        return tasks
    
    def mark_complete(self, task_id: str):
        """Mark task as complete."""
        
        self.db.execute(
            "UPDATE agent_task_queue SET status = 'complete', completed_at = CURRENT_TIMESTAMP WHERE task_id = ?",
            (task_id,)
        )
        
        logger.info(f"✓ Task complete: {task_id}")
    
    def mark_failed(self, task_id: str, error: str):
        """Mark task as failed, enqueue for retry."""
        
        task = self.db.select_one(
            "SELECT * FROM agent_task_queue WHERE task_id = ?",
            (task_id,)
        )
        
        retry_count = task["retry_count"] + 1
        
        if retry_count < task["max_retries"]:
            # Exponential backoff: 1s, 2s, 4s, 8s
            backoff = 2 ** (retry_count - 1)
            
            self.db.execute(
                """UPDATE agent_task_queue 
                   SET status = 'pending', retry_count = ?, 
                       created_at = datetime('now', '+' || ? || ' seconds')
                   WHERE task_id = ?""",
                (retry_count, backoff, task_id)
            )
            
            logger.warning(f"Task failed, retrying in {backoff}s: {task_id}")
        else:
            # Move to dead letter queue
            self.db.execute(
                "UPDATE agent_task_queue SET status = 'failed' WHERE task_id = ?",
                (task_id,)
            )
            
            logger.error(f"Task permanently failed (max retries exceeded): {task_id}")

# src/app/main.py (INITIALIZE QUEUE)
queue = TaskQueue(db)
```

**Checkpoint 4.3: Sync Logic**

```python
# src/app/services/sync_service.py (NEW)

class SyncService:
    """Orchestrate multi-device sync."""
    
    def __init__(self, db, embeddings):
        self.db = db
        self.embeddings = embeddings
    
    async def sync_device(self, device_id: str, client_changes: dict):
        """
        Handle device sync.
        
        client_changes: {
            "meetings": [{"id": 1, "name": "...", "last_modified_at": "..."}],
            "documents": [...],
            ...
        }
        """
        
        # Get server changes since last sync
        server_changes = self._get_server_changes(device_id)
        
        # Detect conflicts (same record modified on server and client)
        conflicts = self._detect_conflicts(device_id, client_changes, server_changes)
        
        # Resolve conflicts (last-write-wins or custom strategy)
        for conflict in conflicts:
            resolved = self._resolve_conflict(conflict)
            self._apply_resolution(conflict["type"], resolved)
        
        # Apply client changes to server
        for entity_type, changes in client_changes.items():
            for change in changes:
                self._apply_change(device_id, entity_type, change)
        
        # Sync embeddings if needed
        await self._sync_embeddings(device_id)
        
        return {
            "success": True,
            "server_changes": server_changes,
            "conflicts_resolved": len(conflicts)
        }
    
    def _detect_conflicts(self, device_id: str, client, server) -> list:
        """Find records modified on both sides."""
        
        conflicts = []
        
        # For each client change, check if server has newer version
        for meeting in client.get("meetings", []):
            server_version = self.db.select_one(
                "SELECT * FROM meeting_v2 WHERE id = ?",
                (meeting["id"],)
            )
            
            if server_version and server_version["last_modified_at"] != meeting["last_modified_at"]:
                conflicts.append({
                    "type": "meeting",
                    "id": meeting["id"],
                    "client_version": meeting,
                    "server_version": server_version
                })
        
        return conflicts
    
    def _resolve_conflict(self, conflict: dict):
        """Resolve single conflict.
        
        Strategy: Last-Write-Wins (could be customized per field)
        """
        
        client = conflict["client_version"]
        server = conflict["server_version"]
        
        # Last write timestamp wins
        if client.get("last_modified_at") > server.get("last_modified_at"):
            return client
        else:
            return server

# Usage in API:
@router.post("/api/mobile/sync")
async def mobile_sync(device_id: str, changes: dict):
    sync_service = SyncService(db, embeddings)
    result = await sync_service.sync_device(device_id, changes)
    return result
```

**Checkpoint 4.4: Testing Sync Logic**

```python
# test_sync.py

import pytest

@pytest.mark.asyncio
async def test_sync_no_conflicts():
    """Test sync when client and server have no conflicts."""
    
    device_id = "mobile-123"
    client_changes = {
        "meetings": [
            {"id": 1, "name": "Updated Stand-up", "last_modified_at": "2026-01-22T12:00:00"}
        ]
    }
    
    sync = SyncService(db, embeddings)
    result = await sync.sync_device(device_id, client_changes)
    
    assert result["success"]
    assert result["conflicts_resolved"] == 0
    
    # Verify change was applied
    meeting = db.select_one("SELECT * FROM meeting_v2 WHERE id = 1")
    assert meeting["name"] == "Updated Stand-up"
    assert meeting["synced_from_device"] == device_id

@pytest.mark.asyncio
async def test_sync_with_conflict_last_write_wins():
    """Test conflict resolution (last-write-wins)."""
    
    device_id = "mobile-123"
    
    # Server has version from 12:00
    db.execute(
        """INSERT INTO meeting_v2 (id, name, last_modified_at, synced_from_device)
           VALUES (1, 'Original', '2026-01-22T12:00:00', 'laptop-456')"""
    )
    
    # Client tries to set version from 11:00 (older)
    client_changes = {
        "meetings": [
            {"id": 1, "name": "Client Version", "last_modified_at": "2026-01-22T11:00:00"}
        ]
    }
    
    sync = SyncService(db, embeddings)
    result = await sync.sync_device(device_id, client_changes)
    
    assert result["conflicts_resolved"] == 1
    
    # Server version should win (newer timestamp)
    meeting = db.select_one("SELECT * FROM meeting_v2 WHERE id = 1")
    assert meeting["name"] == "Original"
```

**Exit Criteria:**
- [ ] mDNS device discovery working
- [ ] Devices can discover each other on local network
- [ ] TaskQueue system operational with retry logic
- [ ] Sync conflicts detected and resolved correctly
- [ ] No data loss in sync scenarios
- [ ] Exponential backoff retry working
- [ ] All sync tests passing

---

### Phase 5: Embeddings & Hybrid Search
**Duration:** 7-10 days
**Risk:** Low (additive only, no existing data modified)
**Mitigation:** Incremental backfill, health checks

**Checkpoint 5.1: Extend Embeddings to All Entity Types**

```python
# src/app/services/embeddings.py (ENHANCED)

class EmbeddingService:
    """Generate embeddings for all entity types."""
    
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.client = OpenAI()
        self.chroma = None  # Will be initialized
    
    def initialize_collections(self):
        """Initialize ChromaDB collections for all 6 entity types."""
        
        entity_types = [
            "meetings",          # ✓ existing
            "documents",         # ✓ existing
            "signals",           # NEW
            "dikw",              # NEW (DIKW items)
            "tickets",           # NEW (career tickets)
            "career_memories"    # NEW
        ]
        
        for entity_type in entity_types:
            collection = self.chroma.get_or_create_collection(
                name=entity_type,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"✓ Created collection: {entity_type}")
    
    async def embed_all(self):
        """Backfill embeddings for all existing content."""
        
        # Meetings
        await self._backfill_embeddings("meetings", self._get_meetings_to_embed)
        
        # Documents
        await self._backfill_embeddings("documents", self._get_documents_to_embed)
        
        # Signals (NEW)
        await self._backfill_embeddings("signals", self._get_signals_to_embed)
        
        # DIKW items (NEW)
        await self._backfill_embeddings("dikw", self._get_dikw_to_embed)
        
        # Tickets (NEW)
        await self._backfill_embeddings("tickets", self._get_tickets_to_embed)
        
        # Career memories (NEW)
        await self._backfill_embeddings("career_memories", self._get_memories_to_embed)
    
    async def _backfill_embeddings(self, entity_type: str, get_items_fn):
        """Backfill embeddings for entity type."""
        
        items = get_items_fn()
        total = len(items)
        
        logger.info(f"Backfilling {total} {entity_type} embeddings...")
        
        for i, item in enumerate(items):
            # Generate embedding
            embedding = await self._generate_embedding(item["text"])
            
            # Store in ChromaDB
            collection = self.chroma.get_collection(entity_type)
            collection.add(
                ids=[str(item["id"])],
                embeddings=[embedding],
                documents=[item["text"]],
                metadatas=[{"source_id": item["id"]}]
            )
            
            # Mark as embedded in database
            self._mark_embedded(entity_type, item["id"])
            
            if (i + 1) % 100 == 0:
                logger.info(f"  {i+1}/{total} ({(i+1)/total*100:.1f}%)")
        
        logger.info(f"✓ Completed backfill for {entity_type}")
    
    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text."""
        
        response = self.client.embeddings.create(
            input=text,
            model=self.model
        )
        
        return response.data[0].embedding
    
    def _mark_embedded(self, entity_type: str, item_id: int):
        """Mark item as having embeddings."""
        
        # Update embedding_status column
        table = f"{entity_type.rstrip('s')}_v2"  # meetings → meeting_v2
        
        self.db.execute(
            f"UPDATE {table} SET embedding_status = 'completed' WHERE id = ?",
            (item_id,)
        )

# CLI tool for backfill:
# python -m scripts.backfill_embeddings
```

**Checkpoint 5.2: Hybrid Search (Keyword + Semantic)**

```python
# src/app/services/search_hybrid.py (NEW)

class HybridSearch:
    """Search combining BM25 (keyword) + semantic (embeddings)."""
    
    def __init__(self, db, embeddings):
        self.db = db
        self.embeddings = embeddings
        self.keyword_weight = 0.4  # 40% keyword
        self.semantic_weight = 0.6  # 60% semantic (configurable)
    
    async def search(
        self,
        query: str,
        entity_types: list[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """Search across all entity types."""
        
        if entity_types is None:
            entity_types = ["meetings", "documents", "signals", "dikw", "tickets", "career_memories"]
        
        # Get results from both strategies
        keyword_results = self._search_keyword(query, entity_types, limit * 2)
        semantic_results = await self._search_semantic(query, entity_types, limit * 2)
        
        # Combine and score results
        combined = self._combine_results(
            keyword_results,
            semantic_results,
            self.keyword_weight,
            self.semantic_weight
        )
        
        # Sort by combined score
        sorted_results = sorted(combined, key=lambda x: x["score"], reverse=True)
        
        return sorted_results[:limit]
    
    def _search_keyword(self, query: str, entity_types: list[str], limit: int):
        """Search using BM25 (SQLite FTS5)."""
        
        results = []
        
        for entity_type in entity_types:
            # Use FTS5 virtual table for full-text search
            fts_table = f"{entity_type}_fts"  # meetings_fts, documents_fts, etc.
            
            rows = self.db.select(
                f"""SELECT id, entity_type, rank FROM {fts_table}
                   WHERE {fts_table} MATCH ?
                   ORDER BY rank DESC
                   LIMIT ?""",
                (query, limit)
            )
            
            for row in rows:
                results.append({
                    "id": row["id"],
                    "type": entity_type,
                    "strategy": "keyword",
                    "keyword_score": row["rank"]  # BM25 score
                })
        
        return results
    
    async def _search_semantic(self, query: str, entity_types: list[str], limit: int):
        """Search using embeddings (ChromaDB)."""
        
        # Generate embedding for query
        query_embedding = await self.embeddings._generate_embedding(query)
        
        results = []
        
        for entity_type in entity_types:
            # Query ChromaDB
            collection = self.embeddings.chroma.get_collection(entity_type)
            
            query_result = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=["documents", "distances"]
            )
            
            for i, doc_id in enumerate(query_result["ids"][0]):
                # Convert distance to similarity score (0-1)
                distance = query_result["distances"][0][i]
                similarity = 1 / (1 + distance)  # Normalize to 0-1
                
                results.append({
                    "id": int(doc_id),
                    "type": entity_type,
                    "strategy": "semantic",
                    "semantic_score": similarity
                })
        
        return results
    
    def _combine_results(self, keyword_results, semantic_results, k_weight, s_weight):
        """Combine keyword and semantic results."""
        
        # Group by (id, type)
        combined = {}
        
        for result in keyword_results:
            key = (result["id"], result["type"])
            if key not in combined:
                combined[key] = {"id": result["id"], "type": result["type"], "score": 0}
            combined[key]["score"] += result.get("keyword_score", 0) * k_weight
        
        for result in semantic_results:
            key = (result["id"], result["type"])
            if key not in combined:
                combined[key] = {"id": result["id"], "type": result["type"], "score": 0}
            combined[key]["score"] += result.get("semantic_score", 0) * s_weight
        
        return list(combined.values())

# Usage:
@router.get("/api/v1/search")
async def hybrid_search(
    q: str,
    entity_types: Optional[str] = None
):
    search = HybridSearch(db, embeddings)
    
    types = entity_types.split(",") if entity_types else None
    results = await search.search(q, types, limit=10)
    
    return {"query": q, "results": results}
```

**Checkpoint 5.3: Embedding Health Checks**

```python
# src/app/services/embedding_health.py

class EmbeddingHealth:
    """Monitor embedding coverage and health."""
    
    def __init__(self, db, embeddings):
        self.db = db
        self.embeddings = embeddings
    
    def get_stats(self) -> dict:
        """Get embedding coverage statistics."""
        
        stats = {
            "total": 0,
            "embedded": 0,
            "missing": 0,
            "failed": 0,
            "coverage_percent": 0
        }
        
        entity_types = ["meetings", "documents", "signals", "dikw", "tickets", "career_memories"]
        
        for entity_type in entity_types:
            table = f"{entity_type.rstrip('s')}_v2"
            
            total = self.db.select_one(f"SELECT COUNT(*) as count FROM {table}")["count"]
            embedded = self.db.select_one(
                f"SELECT COUNT(*) as count FROM {table} WHERE embedding_status = 'completed'"
            )["count"]
            failed = self.db.select_one(
                f"SELECT COUNT(*) as count FROM {table} WHERE embedding_status = 'failed'"
            )["count"]
            missing = total - embedded - failed
            
            stats["total"] += total
            stats["embedded"] += embedded
            stats["missing"] += missing
            stats["failed"] += failed
            
            logger.info(f"{entity_type}: {embedded}/{total} ({embedded/total*100 if total else 0:.1f}%)")
        
        stats["coverage_percent"] = (stats["embedded"] / stats["total"] * 100) if stats["total"] else 0
        
        return stats

# Usage:
health = EmbeddingHealth(db, embeddings)
stats = health.get_stats()

# Log or expose via API
logger.info(f"Embedding coverage: {stats['coverage_percent']:.1f}%")
```

**Checkpoint 5.5: Concept mindmaps (cross-meeting, tag-drillable)**

- Extract key concepts/entities from meetings and documents using existing signals plus embeddings; cluster by tags and date ranges.
- Build a lightweight graph (nodes: concepts, meetings; edges: mentions/co-occurrence) with drill-down filters for specific tags or single meetings.
- Expose via API and a simple view to render mindmaps; persist derived graphs so repeated queries are fast.

**Exit Criteria:**
- [ ] Embeddings generated for all 6 entity types
- [ ] ChromaDB collections populated (meetings, documents, signals, dikw, tickets, career_memories)
- [ ] Hybrid search (BM25 + semantic) working
- [ ] Search API endpoint functional
- [ ] Embedding health checks show > 95% coverage
- [ ] Concept mindmaps generated and drillable by tag/meeting
- [ ] No breaking changes to existing search

---

### Phase 6: Mobile App (Parallel with Phase 5)
**Duration:** 14-21 days
**Risk:** Low (new code only)
**Mitigation:** Thorough testing on simulator and real device

**Checkpoint 6.1-6.4:** See MOBILE_APP_GUIDE.md (future document)

---

### Phase 7: Cutover
**Duration:** 3-5 days
**Risk:** Low (well-tested code)
**Mitigation:** Comprehensive testing, easy rollback

**Checkpoint 7.1: All Tests Passing**

```bash
# Run full test suite
pytest src/ --cov=src --cov-report=html -v

# Verify coverage > 80%
Coverage: 85%
Failures: 0
Errors: 0
```

**Checkpoint 7.2: Old Code Completely Unused**

```python
# Monitor old code usage via metrics

metrics = MigrationMetrics()

for agent_name in ["arjuna", "career_coach", "meeting_analyzer", "dikw_synthesizer"]:
    stats = metrics.get_stats(agent_name, minutes=1440)  # Last 24 hours
    
    old_code_percent = stats["old_code_calls"] / (stats["old_code_calls"] + stats["new_code_calls"]) * 100
    
    assert old_code_percent == 0, f"Old {agent_name} still in use: {old_code_percent}%"
```

**Checkpoint 7.3: Legacy Code Deletion**

```bash
# Delete adapters
rm src/app/api/assistant.py
rm src/app/api/career.py
# etc.

# Delete old agent implementations
rm src/app/api/signals.py
# Keep only agents/arjuna.py, agents/career_coach.py, etc.

# Update imports in main.py
```

**Checkpoint 7.4: Documentation Updated**

```markdown
# Update README

## Architecture

This project uses:
- FastAPI backend with agent-based architecture
- ChromaDB for semantic embeddings (6 types)
- SQLite with hybrid search (keyword + semantic)
- Multi-device sync via mDNS + task queues
- React Native mobile app for offline-first operation

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.
```

**Exit Criteria:**
- [ ] All tests passing (> 80% coverage)
- [ ] Old code verified unused (metrics)
- [ ] Legacy code deleted
- [ ] Documentation updated
- [ ] README updated with new architecture
- [ ] Ready for production deployment

---

## Success Criteria Across All Phases

### Phase 1 (Local Refactoring)
- [ ] Zero breaking changes to external API
- [ ] All agents extracted and working
- [ ] Adapters allow old code to work with new agents
- [ ] Feature flags ready for gradual rollout

### Phase 2 (Database Evolution)
- [ ] Old and new tables coexist
- [ ] Data synced from old to new tables
- [ ] Compatibility views working
- [ ] No data loss
- [ ] Rollback procedure tested

### Phase 3 (API Modernization)
- [ ] /api/v1 endpoints functional
- [ ] /api/mobile endpoints functional
- [ ] Mobile client can sync
- [ ] Old routes still work
- [ ] OpenAPI docs generated

### Phase 4 (Multi-Device & Queues)
- [ ] mDNS device discovery working
- [ ] TaskQueue with retry logic operational
- [ ] Sync conflicts resolved correctly
- [ ] No data loss in sync
- [ ] All sync tests passing

### Phase 5 (Embeddings & Search)
- [ ] Embeddings generated for all 6 types
- [ ] Hybrid search (BM25 + semantic) working
- [ ] Search API functional
- [ ] > 95% embedding coverage
- [ ] Zero breaking changes

### Phase 6 (Mobile App)
- [ ] React Native project builds APK
- [ ] Offline mode working
- [ ] Device discovery from mobile
- [ ] Mobile can sync with servers
- [ ] No server-side breaking changes

### Phase 7 (Cutover)
- [ ] All tests passing (> 80% coverage)
- [ ] Old code verified unused
- [ ] Legacy code deleted
- [ ] Documentation updated
- [ ] Ready for production

---

## Rollback Procedures by Phase

### Phase 1: Code Extraction Rollback
**Time:** < 5 minutes

```bash
git revert <phase-1-commit>
# Old code in api/ still works
# New agents/ directory removed
# No database changes, so data is safe
```

### Phase 2: Database Rollback
**Time:** < 2 minutes

```bash
# Option 1: Feature flag
set use_new_database: false

# Option 2: Restore from backup
cp backups/database.2026-01-22.db agent.db
```

### Phase 3: API Rollback
**Time:** < 2 minutes

```bash
# Feature flag disables new API endpoints
set use_api_v1: false

# Mobile reverts to old endpoints (still supported)
```

### Phase 4: Sync Rollback
**Time:** < 5 minutes

```bash
# Stop sync service
set enable_sync: false

# All device changes discarded (revert to last good sync)
# No data corruption (conflict resolution ensures safety)
```

### Phase 5: Embeddings Rollback
**Time:** < 2 minutes

```bash
# Feature flag disables hybrid search
set use_hybrid_search: false

# Fall back to keyword-only search (original behavior)
# No data loss (embeddings are additive)
```

### Phase 6-7: Rollback
**Time:** < 10 minutes

```bash
git revert <phase-7-commit>
# Restore old code
# All data preserved
```

---

## Monitoring During Migration

### Key Metrics to Track

```python
metrics_to_monitor = {
    "agent_latency_ms": {"old": 100, "new": 95, "threshold": 150},
    "api_error_rate": {"old": 0.5%, "new": 0.4%, "threshold": 2%},
    "sync_conflict_rate": {"target": 0, "threshold": 5},
    "embedding_coverage": {"target": 100%, "threshold": 95%},
    "hybrid_search_latency": {"target": 200, "threshold": 500},
    "mobile_sync_success": {"target": 99%, "threshold": 95%},
}
```

### Automated Rollback Triggers

```python
# If error rate exceeds threshold:
if error_rate > 5%:
    set_feature_flag("use_new_code", False)
    log_alert("ERROR_RATE_EXCEEDED: Rolled back to legacy code")
    page_oncall()
```

