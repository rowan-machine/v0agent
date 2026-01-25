# Advanced Refactoring Best Practices (Overlooked Items)

**Purpose:** Additional best practices and patterns for safe, phased refactoring that prevents breaking changes.

**Status:** Complementary to REFACTORING_BEST_PRACTICES.md

---

## 1. Backward Compatibility Strategy

### Adapter Pattern for Gradual Cutover

**Problem:** Old code calls `from src.app.api.assistant import Arjuna` but we're moving to `from src.app.agents import ArjunaAgent`

**Solution: Create Adapter Layer**

```python
# src/app/api/assistant.py (OLD FILE - Keep for backward compatibility)
# Instead of deleting, convert to adapter

from src.app.agents import get_registry

# DEPRECATED: This module is being refactored into agents/
# Old code can continue to work via this adapter

class Arjuna:
    """DEPRECATED: Use src.app.agents.ArjunaAgent instead.
    
    This class exists only for backward compatibility.
    It delegates to the new agent system.
    """
    
    def __init__(self):
        # Get new agent from registry
        self.agent = get_registry().get("arjuna")
    
    def parse_intent(self, message: str):
        """Deprecated: Use agent.ask_llm() instead."""
        return self.agent.parse_intent(message)
    
    def execute_intent(self, intent):
        """Deprecated: Use agent.handle_intent() instead."""
        return self.agent.execute_intent(intent)

# This way:
# - Old code using Arjuna() still works
# - It delegates to new agent
# - We can gradually migrate call sites
# - No breaking changes
```

### Import Compatibility

```python
# src/app/main.py - Keep old imports working

# OLD WAY (still works):
from src.app.api.assistant import Arjuna
from src.app.api.career import CareerCoach

# NEW WAY (preferred, but not required):
from src.app.agents import get_registry

# Both paths work during migration!
```

**Benefits:**
- Zero breaking changes
- Can migrate gradually (some routes use old code, others use new)
- Easy to identify and migrate call sites
- Audit trail (deprecated warnings in logs)

---

## 2. Feature Flags for Gradual Rollout

**Problem:** Can't risk switching all agents at once to new code

**Solution: Feature Flags**

```python
# config/feature_flags.yaml

features:
  use_new_arjuna:
    enabled: false
    environments: [development]
    rolloutPercentage: 0  # 0-100
  
  use_new_career_coach:
    enabled: false
    environments: [development]
    rolloutPercentage: 0
  
  use_new_meeting_analyzer:
    enabled: false
    environments: [development]
    rolloutPercentage: 0
  
  use_new_dikw_synthesizer:
    enabled: false
    environments: [development]
    rolloutPercentage: 0

# src/app/flags.py
class FeatureFlags:
    def __init__(self):
        self.flags = load_yaml("config/feature_flags.yaml")
    
    def is_enabled(self, flag_name: str, user_id: str = None) -> bool:
        """Check if feature is enabled for user."""
        flag = self.flags.get("features", {}).get(flag_name, {})
        
        if not flag.get("enabled"):
            return False
        
        # Gradual rollout: first 10%, then 25%, then 50%, etc.
        if user_id and flag.get("rolloutPercentage", 100) < 100:
            # Hash user_id to determine if in rollout group
            user_hash = hash(user_id) % 100
            return user_hash < flag["rolloutPercentage"]
        
        return True

# Usage in code:
flags = FeatureFlags()

if flags.is_enabled("use_new_arjuna"):
    arjuna = get_registry().get("arjuna")  # New code
else:
    arjuna = Arjuna()  # Old code (adapter)

result = arjuna.ask(message)
```

**Rollout Timeline Example:**
```
Week 1: 0% (testing in development only)
Week 2: 10% (early adopters in production)
Week 3: 25% (growing confidence)
Week 4: 50% (half of production)
Week 5: 75% (nearly everyone)
Week 6: 100% (fully rolled out)
```

---

## 3. Database Compatibility Layers

**Problem:** Can't migrate database schema all at once

**Solution: View-Based Compatibility**

```sql
-- Keep old tables, add new ones alongside

-- OLD TABLE (still used by legacy code)
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY,
    name TEXT,
    notes TEXT,
    date TEXT
);

-- NEW TABLES (used by new code)
CREATE TABLE meeting_v2 (
    id INTEGER PRIMARY KEY,
    name TEXT,
    notes TEXT,
    date TEXT,
    synced_from_device TEXT,  -- NEW COLUMN
    last_modified_device TEXT,  -- NEW COLUMN
    last_modified_at TIMESTAMP,  -- NEW COLUMN
    embedding_status TEXT  -- NEW COLUMN
);

-- COMPATIBILITY VIEW (old code sees unified view)
CREATE VIEW meetings_unified AS
SELECT 
    id, name, notes, date,
    'local' as synced_from_device,  -- Default for old records
    'unknown' as last_modified_device,
    current_timestamp as last_modified_at,
    'pending' as embedding_status
FROM meetings
UNION ALL
SELECT id, name, notes, date, synced_from_device, 
       last_modified_device, last_modified_at, embedding_status
FROM meeting_v2;
```

**Usage:**
```python
# Old code (unchanged):
db.select("SELECT * FROM meetings WHERE id = ?", (id,))

# New code (uses new columns):
db.select("SELECT * FROM meeting_v2 WHERE id = ?", (id,))

# View allows gradual migration:
# 1. Create new table
# 2. Sync old data to new table
# 3. Create view for compatibility
# 4. Migrate code to use new table
# 5. Drop old table when migration complete
```

---

## 4. Circular Dependency Prevention

**Problem:** AgentRegistry in __init__.py creates import cycles

**Solution: Separate Registry Module**

```python
# src/app/agents/registry.py (NEW FILE)
class AgentRegistry:
    """Centralized agent management."""
    # (move all AgentRegistry code here)

# src/app/agents/__init__.py (CLEAN)
from .base import BaseAgent, AgentConfig
from .registry import AgentRegistry

def get_registry():
    """Get global registry singleton."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry

__all__ = ["BaseAgent", "AgentConfig", "AgentRegistry", "get_registry"]
```

**Benefits:**
- No circular imports
- Clear dependency graph
- Easy to test (can mock registry)
- Cleaner init file

---

## 5. Type Hints Throughout

**Why:** Catch bugs at IDE level, not runtime

```python
# BAD (what we have)
def parse_intent(message):
    intent = self._parse_intent(message)
    return intent

# GOOD (with type hints)
from typing import Optional
from dataclasses import dataclass

@dataclass
class Intent:
    type: str
    confidence: float
    params: dict[str, any]

def parse_intent(self, message: str) -> Intent:
    """Parse intent from user message."""
    intent = self._parse_intent(message)
    return intent

# Now IDE knows:
# - What message should be (str)
# - What parse_intent returns (Intent object)
# - Can autocomplete Intent fields
```

**Coverage Checklist:**
- [x] Function parameters
- [x] Function return types
- [x] Class attributes
- [x] Dict types (dict[str, int])
- [x] List types (list[str])
- [x] Optional types (Optional[str])
- [ ] mypy configuration (add to pyproject.toml)

---

## 6. Integration Points Between Old & New Code

**Problem:** How do old and new code actually interact?

**Solution: Define Integration Contracts**

```python
# src/app/api/assistant.py (OLD) calling NEW agents
# This is where old and new code meet

from src.app.agents import get_registry

class ArjunaAdapter:
    """Old Arjuna class, now delegates to new agent."""
    
    async def handle_user_message(self, message: str, user_id: str):
        # OLD ROUTE HANDLER calls new agent
        
        try:
            # Get new agent
            agent = get_registry().get("arjuna")
            
            # Call new method
            result = await agent.ask_llm(message)
            
            # Convert old-style response to new format
            return self._format_response(result)
        
        except Exception as e:
            # Fallback to old implementation
            logger.warning(f"New agent failed: {e}. Falling back to legacy.")
            return self._legacy_implementation(message)

# Define clear boundaries:
# 1. Old code owns: Flask/FastAPI routes, templates, HTML
# 2. New code owns: Agent logic, LLM calls, embeddings
# 3. Integration: Routes call agents via registry
```

---

## 7. Monitoring & Metrics During Migration

**Problem:** Don't know if new code is working correctly

**Solution: Instrumentation**

```python
# src/app/services/migration_metrics.py

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class AgentMetric:
    agent_name: str
    used_new_code: bool
    latency_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class MigrationMetrics:
    """Track migration progress and health."""
    
    def __init__(self):
        self.metrics = []
    
    def record(self, metric: AgentMetric):
        """Record a metric."""
        self.metrics.append(metric)
        
        # Log for monitoring
        logger.info(
            f"Agent: {metric.agent_name}, "
            f"NewCode: {metric.used_new_code}, "
            f"Latency: {metric.latency_ms}ms, "
            f"Success: {metric.success}",
            extra={
                "metric_type": "agent_migration",
                "agent": metric.agent_name,
                "new_code": metric.used_new_code,
            }
        )
    
    def get_stats(self, agent_name: str, minutes: int = 60):
        """Get migration stats for an agent."""
        recent = [
            m for m in self.metrics
            if m.agent_name == agent_name and
               (datetime.now() - m.timestamp).total_seconds() < minutes * 60
        ]
        
        return {
            "total_calls": len(recent),
            "new_code_calls": sum(1 for m in recent if m.used_new_code),
            "old_code_calls": sum(1 for m in recent if not m.used_new_code),
            "success_rate": sum(1 for m in recent if m.success) / len(recent) if recent else 0,
            "avg_latency_ms": sum(m.latency_ms for m in recent) / len(recent) if recent else 0,
            "errors": [m.error for m in recent if m.error],
        }

# Usage:
metrics = MigrationMetrics()

# In agent code:
start = time.time()
try:
    result = agent.ask_llm(prompt)
    metrics.record(AgentMetric(
        agent_name="arjuna",
        used_new_code=True,
        latency_ms=(time.time() - start) * 1000,
        success=True
    ))
except Exception as e:
    metrics.record(AgentMetric(
        agent_name="arjuna",
        used_new_code=True,
        latency_ms=(time.time() - start) * 1000,
        success=False,
        error=str(e)
    ))

# Dashboard endpoint:
@router.get("/api/v1/debug/migration-stats/{agent_name}")
def get_migration_stats(agent_name: str):
    return metrics.get_stats(agent_name)
```

**Monitoring Checklist:**
- [ ] Latency comparison (old vs new)
- [ ] Error rate comparison
- [ ] Rollout percentage tracking
- [ ] Gradual rollout dashboard
- [ ] Automated rollback triggers (if error rate > 5%)

---

## 8. Rollback Procedures Per Phase

**Problem:** If Phase 2 breaks, we need to rollback quickly

**Solution: Documented Rollback Path**

```markdown
## Phase 2 Rollback Procedure

### If Agent Extraction Fails

**Automatic Rollback (1 minute):**
1. Feature flag: set `use_new_arjuna: enabled = false`
2. Server restart: `pkill -f uvicorn && uvicorn src.app.main:app --reload`
3. All traffic routed to old Arjuna class (adapter)

**Code Rollback (if needed):**
1. `git revert <phase-2-commit-hash>`
2. Restore agents/__init__.py and agents/base.py
3. Delete agents/arjuna.py
4. Delete prompts/agents/arjuna/
5. Restart services

**Data Rollback (no data was changed):**
- No database changes in Phase 2
- No rollback needed
```

---

## 9. State Machine for Sync Conflicts

**Problem:** Multi-device sync can have conflicts, need systematic resolution

**Solution: State Machine**

```python
# src/app/services/sync_conflict.py

from enum import Enum
from dataclasses import dataclass

class ConflictStrategy(Enum):
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MANUAL_MERGE = "manual_merge"
    MERGE_BOTH = "merge_both"

class SyncConflictResolver:
    """Resolve conflicts using state machine."""
    
    def resolve(
        self,
        local_version: dict,
        remote_version: dict,
        conflict_type: str,
        strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS
    ) -> dict:
        """
        Resolve sync conflict between versions.
        
        States:
        1. DETECT: Identify conflict
        2. CLASSIFY: What type? (same field, different field, etc.)
        3. RESOLVE: Apply strategy
        4. MERGE: Combine if possible
        5. RETURN: Resolved version
        """
        
        # STATE 1: DETECT
        if local_version == remote_version:
            return local_version  # No conflict
        
        # STATE 2: CLASSIFY
        conflict_class = self._classify_conflict(
            local_version, remote_version
        )
        
        # STATE 3: RESOLVE based on strategy
        if strategy == ConflictStrategy.LAST_WRITE_WINS:
            resolved = self._last_write_wins(local_version, remote_version)
        elif strategy == ConflictStrategy.MERGE_BOTH:
            resolved = self._merge_both(local_version, remote_version)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # STATE 4: MERGE if possible
        merged = self._attempt_merge(local_version, remote_version, resolved)
        
        # STATE 5: RETURN
        return merged
```

---

## 10. API Versioning Strategy

**Problem:** API changes will break mobile app

**Solution: Explicit API Versioning**

```python
# src/app/api/v1/__init__.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["v1"])

# src/app/api/v1/meetings.py
@router.get("/meetings/{id}")
async def get_meeting_v1(id: int):
    """
    Get meeting (API v1).
    
    Schema:
    {
        "id": 1,
        "name": "Stand-up",
        "notes": "Discussed...",
        "date": "2026-01-22"
    }
    """
    pass

# src/app/api/v2/__init__.py (FUTURE)
# from fastapi import APIRouter
# router = APIRouter(prefix="/api/v2", tags=["v2"])

# src/app/api/v2/meetings.py (FUTURE)
# @router.get("/meetings/{id}")
# async def get_meeting_v2(id: int):
#     """Get meeting (API v2 - with embedding_status, synced_from_device)."""
#     pass

# main.py
app.include_router(v1.router)
# app.include_router(v2.router)  # Enable when ready
```

**Benefits:**
- Mobile app can specify `Accept: application/vnd.signalflow.v1+json`
- Server supports multiple API versions simultaneously
- Gradual migration to v2 when all clients ready
- No breaking changes

---

## 11. Cache Invalidation Strategy

**Problem:** When embeddings are updated, stale caches break results

**Solution: Versioned Caches**

```python
# src/app/services/cache.py

from typing import Any, Callable
import hashlib
from datetime import datetime

class VersionedCache:
    """Cache with version tracking."""
    
    def __init__(self):
        self.cache = {}
        self.versions = {}  # entity_type → version_number
    
    def set(self, key: str, value: Any, entity_type: str):
        """Cache value, tag with entity version."""
        version = self.versions.get(entity_type, 0)
        
        cache_key = f"{key}:v{version}"
        self.cache[cache_key] = {
            "value": value,
            "timestamp": datetime.now(),
            "entity_type": entity_type,
            "version": version
        }
    
    def get(self, key: str, entity_type: str) -> Any:
        """Get cache, auto-invalidate if version changed."""
        version = self.versions.get(entity_type, 0)
        cache_key = f"{key}:v{version}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]["value"]
        
        return None  # Cache miss or invalidated
    
    def invalidate(self, entity_type: str):
        """Invalidate all caches for entity type."""
        self.versions[entity_type] = self.versions.get(entity_type, 0) + 1
        logger.info(f"Invalidated cache for {entity_type} (v{self.versions[entity_type]})")

# Usage:
cache = VersionedCache()

# Cache a result
cache.set(
    key="signal_search:cloud_architecture",
    value=results,
    entity_type="signals"
)

# When embeddings update:
cache.invalidate("signals")  # All signal caches now stale
# Next call to cache.get("signal_search:cloud_architecture", "signals")
# returns None (cache miss) → recalculate
```

---

## 12. Message Queue Overflow Handling

**Problem:** If task queue gets too full, what happens?

**Solution: Backpressure & Overflow Policy**

```python
# src/app/services/agent_queue.py

class TaskQueue:
    """Queue with overflow handling."""
    
    def __init__(self, max_size: int = 1000, overflow_policy: str = "drop_oldest"):
        self.max_size = max_size
        self.overflow_policy = overflow_policy
        self.queue = []
        self.metrics = {"total_enqueued": 0, "dropped": 0, "overflows": 0}
    
    def enqueue(self, task: dict) -> bool:
        """
        Enqueue task with backpressure handling.
        
        Returns:
        - True: task enqueued
        - False: task dropped (queue full)
        """
        
        if len(self.queue) >= self.max_size:
            self.metrics["overflows"] += 1
            
            if self.overflow_policy == "drop_oldest":
                dropped = self.queue.pop(0)
                self.metrics["dropped"] += 1
                logger.warning(f"Queue overflow! Dropped task: {dropped['task_id']}")
            
            elif self.overflow_policy == "reject_new":
                logger.error(f"Queue full ({self.max_size}). Rejecting new task.")
                return False
            
            elif self.overflow_policy == "block":
                # Caller must retry
                raise QueueFullError(f"Queue is full (max {self.max_size})")
        
        self.queue.append(task)
        self.metrics["total_enqueued"] += 1
        
        return True
    
    def get_metrics(self):
        return {
            **self.metrics,
            "current_size": len(self.queue),
            "capacity_percent": (len(self.queue) / self.max_size) * 100
        }
```

---

## Summary: Overlooked Best Practices

| Practice | Why It Matters | When to Apply |
|----------|---------------|---------------|
| Adapter Pattern | Zero breaking changes | During Phase 2-3 |
| Feature Flags | Gradual rollout safety | Phase 2+ |
| Database Views | Schema evolution | Phase 3-4 |
| Separate Modules | Avoid circular imports | Refactor agents/ |
| Type Hints | IDE catches bugs early | All phases |
| Integration Points | Clear contracts | Phase 2+ |
| Monitoring | Know if migration works | Phase 2+ |
| Rollback Procedures | Quick recovery | All phases |
| State Machines | Systematic conflict resolution | Phase 4+ |
| API Versioning | Support multiple clients | Phase 3+ |
| Versioned Caches | Avoid stale data | Phase 5+ |
| Backpressure | Prevent queue overflow | Phase 4+ |

