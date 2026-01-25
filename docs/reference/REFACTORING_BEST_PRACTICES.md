# Refactoring Best Practices Guide for SignalFlow

**Purpose:** Actionable best practices for Phase 2+ refactoring, organized by concern area.

**Last Updated:** January 22, 2026  
**Target Audience:** Developers working on agent extraction and API decoupling

---

## Table of Contents
1. [Testing Strategy](#testing-strategy)
2. [Code Organization](#code-organization)
3. [Git Workflow](#git-workflow)
4. [Database Schema Changes](#database-schema-changes)
5. [Performance Optimization](#performance-optimization)
6. [Error Handling & Logging](#error-handling--logging)
7. [Documentation](#documentation)

---

## Testing Strategy

### Before You Start Refactoring: Establish Safety Net

**Step 1: Identify what to test**
```python
# src/app/api/assistant.py - What needs to be tested BEFORE refactoring?

# CRITICAL (Must test):
def parse_intent(message: str) -> Intent  # Core behavior
def execute_intent(intent: Intent) -> str  # Main flow
def format_response(data: dict) -> str  # Output format

# IMPORTANT (Test coverage):
def extract_entities(text: str) -> List[Entity]  # Dependency
def validate_input(data: dict) -> bool  # Input validation

# NICE-TO-HAVE (Can skip first):
def log_interaction(data: dict) -> None  # Side effect
def format_timestamp(ts: int) -> str  # Utility
```

**Step 2: Write tests for current behavior**
```python
# tests/agents/test_arjuna_current.py
import pytest
from src.app.api.assistant import parse_intent, execute_intent

class TestArjunaCurrentBehavior:
    """Tests of CURRENT Arjuna behavior - these pass before refactoring."""
    
    def test_parse_intent_with_todo(self):
        """Current behavior: recognizes 'add task' as create_ticket."""
        intent = parse_intent("Add task: review PR #123")
        assert intent.type == "create_ticket"
        assert intent.title == "review PR #123"
    
    def test_execute_intent_creates_ticket(self):
        """Current behavior: executes create_ticket intent."""
        intent = Intent(type="create_ticket", title="Test task")
        result = execute_intent(intent)
        assert "created" in result.lower()
        assert "ticket" in result.lower()
    
    def test_parse_intent_with_query(self):
        """Current behavior: recognizes 'what did we discuss' as search."""
        intent = parse_intent("What did we discuss about the API refactor?")
        assert intent.type == "search_meetings"
        assert "API" in intent.query
    
    def test_malformed_input_returns_error(self):
        """Current behavior: handles bad input gracefully."""
        intent = parse_intent("")  # Empty input
        assert intent.type == "clarify"
```

### Test-Driven Refactoring Process

**Step 3: Keep tests passing during refactoring**

```python
# WRONG: Refactor without tests
# ❌ Extract Arjuna → create agents/arjuna.py → Tests break → Debug for hours

# RIGHT: Test-driven refactoring
# ✅ Run tests (baseline pass)
# ✅ Extract one method → Ensure tests still pass
# ✅ Extract next method → Ensure tests still pass
# ✅ Final refactor complete → All tests still pass
```

**Step 4: Mock LLM for deterministic tests**

```python
# tests/conftest.py - Shared test fixtures
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_llm():
    """Mock LLM client that returns predictable responses."""
    mock = Mock()
    
    # Define response patterns
    mock.ask.side_effect = lambda prompt: {
        "intent detection": '{"type": "create_ticket", "title": "Test"}',
        "career analysis": '{"insights": ["Growing", "Strong leadership"]}',
        "signal extraction": '{"decisions": ["Approved"], "actions": ["Implement"]}',
    }.get(
        # Extract key from prompt for matching
        next((k for k in mock.ask.side_effect.keys() if k in prompt), "default"),
        '{"error": "No mock for this prompt"}'
    )
    
    return mock

# Usage in tests:
def test_arjuna_with_mocked_llm(mock_llm):
    arjuna = ArjunaAgent(llm_client=mock_llm)
    intent = arjuna.parse_intent("Add task: review code")
    
    assert intent.type == "create_ticket"
    # LLM not called - mocked instead
```

### Testing Checklist for Phase 2

**For each agent you extract:**
- [ ] Write tests for current behavior (before refactoring)
- [ ] All tests pass before you start
- [ ] Extract one method at a time
- [ ] Run tests after each extraction
- [ ] Green bar always (no broken tests)
- [ ] Add tests for new features (queue integration, embeddings)
- [ ] Test error cases (LLM timeout, queue full, network error)
- [ ] Performance tests (< 1s for intent parsing)

---

## Code Organization

### SOLID Principles Application

#### Single Responsibility Principle (SRP)

**BAD:**
```python
# src/app/api/assistant.py - Does everything
class Arjuna:
    def parse_intent(self, msg: str):  # Intent parsing
        pass
    
    def execute_intent(self, intent):  # Execution
        pass
    
    def format_response(self, data):   # Formatting
        pass
    
    def log_interaction(self, data):   # Logging
        pass
    
    def cache_result(self, key, val):  # Caching
        pass
    
    def measure_performance(self):     # Monitoring
        pass
    # ... plus 20 more methods mixing concerns
```

**GOOD:**
```python
# src/app/agents/arjuna.py - Single responsibility
class ArjunaAgent(BaseAgent):
    """Responsible ONLY for intent-based assistance."""
    
    def __init__(self, config, llm_client, intent_registry):
        self.intent_registry = intent_registry
        # Dependencies injected
    
    def ask_llm(self, prompt: str) -> str:
        """Delegate to base class (inherited)."""
        return super().ask_llm(prompt)
    
    def handle_intent(self, message: str) -> str:
        """Core responsibility: parse intent and route."""
        intent = self._parse_intent(message)
        result = self.intent_registry.execute(intent)
        return result

# Separate concerns:
# src/app/services/intent_parser.py - Intent parsing logic
# src/app/services/intent_router.py - Intent routing
# src/app/services/logging.py - Logging/monitoring
# src/app/services/cache.py - Caching
```

#### Dependency Injection

**BAD:**
```python
class ArjunaAgent:
    def __init__(self):
        # Hard-coded dependencies - tightly coupled
        self.llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.db = SQLiteConnection("agent.db")
        self.embedding_service = EmbeddingService()
        # Can't test without these real services
```

**GOOD:**
```python
class ArjunaAgent(BaseAgent):
    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClient,
        embedding_service: EmbeddingService,
        tool_registry: ToolRegistry
    ):
        # Dependencies injected - loosely coupled
        self.config = config
        self.llm_client = llm_client
        self.embedding_service = embedding_service
        self.tool_registry = tool_registry
        # Can pass mocks in tests

# Usage:
llm = OpenAI()  # Or MockLLM in tests
arjuna = ArjunaAgent(
    config=config,
    llm_client=llm,
    embedding_service=embedding_service,
    tool_registry=tool_registry
)
```

### File Organization Standards

```
src/app/agents/
├── __init__.py              # Registry, factory functions
├── base.py                  # BaseAgent abstract class
├── arjuna.py               # ArjunaAgent (intent-based assistance)
├── career_coach.py         # CareerCoachAgent
├── dikw_synthesizer.py     # DikwAgent
└── meeting_analyzer.py     # MeetingAnalyzerAgent

prompts/agents/
├── arjuna/
│   ├── system.jinja2       # System prompt
│   ├── intent_parser.jinja2
│   └── clarification.jinja2
├── career_coach/
│   ├── insights.jinja2
│   ├── feedback.jinja2
│   └── suggestions.jinja2
├── dikw_synthesizer/
│   ├── promote_to_info.jinja2
│   ├── promote_to_knowledge.jinja2
│   └── synthesize.jinja2
└── meeting_analyzer/
    ├── extract_signals.jinja2
    └── group_signals.jinja2

src/app/services/
├── embeddings.py           # ChromaDB wrapper
├── encryption.py           # Fernet encryption
├── intent_registry.py      # Intent type registry (from extracted code)
├── agent_queue.py          # Inter-agent message queues
├── sync_service.py         # Multi-device sync
└── search_hybrid.py        # Hybrid keyword + semantic search

tests/agents/
├── test_arjuna.py
├── test_career_coach.py
├── test_dikw_synthesizer.py
└── test_meeting_analyzer.py

config/
├── agents.yaml             # Agent configurations
├── queues.yaml             # Queue settings
├── models.yaml             # Model assignments
└── default.yaml            # System config
```

### Naming Conventions

**Classes:**
```python
# Agents
class ArjunaAgent(BaseAgent)
class CareerCoachAgent(BaseAgent)
class DikwSynthesizerAgent(BaseAgent)
class MeetingAnalyzerAgent(BaseAgent)

# Services
class EmbeddingService
class EncryptionService
class SyncService
class IntentRegistry

# Configuration
class AgentConfig
class QueueConfig
class SyncConfig
```

**Methods:**
```python
# Action-oriented names
async def ask_llm(self, prompt: str) -> str
def parse_intent(self, message: str) -> Intent
def extract_signals(self, text: str) -> List[Signal]
def handle_task(self, task: Task) -> Result

# Avoid:
def process()     # Too vague
def do_thing()    # Unclear
def x()           # What does this do?
```

**Variables:**
```python
# Be specific
intent: Intent = parser.parse(message)
embedding: List[float] = service.embed(text)
similar_items: List[Item] = search.find_similar(item_id)

# Avoid:
data = ...        # What kind of data?
result = ...      # What's the result?
x = 5             # What is this number?
```

---

## Git Workflow

### Commit Message Standards

**Format:**
```
<Type>(<Scope>): <Subject>

<Body>

<Footer>
```

**Types:**
- `feat` - New feature (agent extraction, new API endpoint)
- `fix` - Bug fix
- `refactor` - Code restructuring (no functional change)
- `perf` - Performance improvement
- `test` - Test additions/changes
- `docs` - Documentation
- `chore` - Build, dependencies

**Examples:**

```bash
# Good commits
git commit -m "feat(arjuna): extract intent parser from assistant.py

- Move 200-line intent parser to agents/arjuna.py
- Use embeddings for common intent detection
- Add intent registry for handler mapping
- Maintain backward compatibility with legacy route

Closes #123"

# Good smaller commits (preferred)
git commit -m "refactor(arjuna): move intent parser to separate class

- Extract IntentParser from Arjuna
- Use dependency injection for services
- Add unit tests for parser"

git commit -m "test(arjuna): add intent parsing tests

- Test 10 common intent types
- Mock LLM responses
- Add edge case tests"

git commit -m "perf(arjuna): use embeddings for intent matching

- 30% faster than LLM-based intent detection
- < 100ms p95 latency
- Reduces API calls by 40%"

# Bad commits (avoid)
git commit -m "Update code"      # Too vague
git commit -m "Fixed stuff"      # Unclear what was fixed
git commit -m "Refactor agent and API and tests"  # Too broad, mix types
```

### Branch Strategy for Phases

```bash
# Phase 2: Agent Extraction
git checkout -b refactor/phase-2-agents

# Work on Arjuna extraction
git checkout -b feature/extract-arjuna
# ... make changes ...
git commit -m "feat(arjuna): extract agent from api/assistant.py"
git commit -m "test(arjuna): add unit tests"
git push

# Pull request → Code review → Merge to refactor/phase-2-agents
git checkout refactor/phase-2-agents
git merge feature/extract-arjuna

# Same for other agents:
git checkout -b feature/extract-career-coach
# ... work ...
git merge back to refactor/phase-2-agents

# When phase complete:
git checkout main
git merge refactor/phase-2-agents
git tag phase-2-agents-complete
git push --tags
```

### Pre-Commit Checklist

Before pushing code:

- [ ] Tests pass: `pytest tests/agents/ -v`
- [ ] Linting passes: `flake8 src/app/agents/`
- [ ] Type checking: `mypy src/app/agents/`
- [ ] No debug prints or commented code
- [ ] Docstrings for public methods
- [ ] Commit message is descriptive
- [ ] No secrets in code (API keys, etc.)
- [ ] Performance tests added for performance-sensitive code

**Pre-commit hook:**
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run tests
pytest tests/ -q || exit 1

# Run linting
flake8 src/app/agents/ || exit 1

# Check for secrets
grep -r "OPENAI_API_KEY" src/ && exit 1

echo "✅ Pre-commit checks passed"
```

---

## Database Schema Changes

### Careful Migration Strategy

**Phase 4 adds new tables for multi-agent support:**

```sql
-- scripts/migrations/005_agent_task_queue.sql

-- UP: Add queue tables
CREATE TABLE agent_task_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    source_agent TEXT NOT NULL,
    target_agent TEXT NOT NULL,
    task_type TEXT NOT NULL,
    params JSON NOT NULL,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    result JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_target_status (target_agent, status)
);

-- DOWN: Remove queue tables
DROP TABLE IF EXISTS agent_task_queue;
```

### Migration Execution

```python
# scripts/run_migrations.py

from pathlib import Path
from src.app.db import connect

def run_migrations():
    """Run all pending migrations in order."""
    db = connect()
    migrations_dir = Path("scripts/migrations")
    
    # Get completed migrations
    completed = db.select("SELECT name FROM schema_migrations")
    completed_names = {row['name'] for row in completed}
    
    # Find pending migrations
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    for migration_file in migration_files:
        migration_name = migration_file.name
        if migration_name in completed_names:
            print(f"⏭️  Skipping {migration_name} (already run)")
            continue
        
        print(f"🚀 Running {migration_name}...")
        
        # Read SQL file
        sql = migration_file.read_text()
        
        # Find UP and DOWN sections
        up_sql = sql.split("-- UP:")[1].split("-- DOWN:")[0].strip()
        
        try:
            # Execute migration
            db.executescript(up_sql)
            
            # Record in schema_migrations
            db.execute(
                "INSERT INTO schema_migrations (name, applied_at) VALUES (?, NOW())",
                (migration_name,)
            )
            
            print(f"✅ {migration_name} completed")
        except Exception as e:
            print(f"❌ {migration_name} FAILED: {e}")
            raise

if __name__ == "__main__":
    run_migrations()
```

### Schema Testing

```python
# tests/test_migrations.py

import pytest
from src.app.db import connect

class TestMigrations:
    def test_migration_005_creates_task_queue_table(self):
        """Verify migration 005 creates required tables."""
        db = connect()
        
        # Check table exists
        tables = db.select(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_task_queue'"
        )
        assert len(tables) > 0, "agent_task_queue table not created"
        
        # Check columns exist
        columns = db.execute(
            "PRAGMA table_info(agent_task_queue)"
        ).fetchall()
        column_names = [col[1] for col in columns]
        
        required = ['task_id', 'source_agent', 'target_agent', 'status']
        for req_col in required:
            assert req_col in column_names, f"Missing column: {req_col}"
    
    def test_migration_rollback_removes_table(self):
        """Verify migration can be rolled back."""
        db = connect()
        
        # Get migration down SQL
        migration_sql = Path("scripts/migrations/005_agent_task_queue.sql").read_text()
        down_sql = migration_sql.split("-- DOWN:")[1].strip()
        
        # Execute down
        db.executescript(down_sql)
        
        # Verify table gone
        tables = db.select(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_task_queue'"
        )
        assert len(tables) == 0, "Table not removed by rollback"
```

---

## Performance Optimization

### Profiling Before Optimization

```python
# src/app/agents/arjuna.py - Add performance monitoring

import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def measure_performance(func):
    """Decorator to measure function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        
        logger.info(f"{func.__name__} took {elapsed:.3f}s")
        
        # Alert if slow
        if elapsed > 1.0:
            logger.warning(f"⚠️  {func.__name__} is slow: {elapsed:.3f}s")
        
        return result
    return wrapper

class ArjunaAgent(BaseAgent):
    @measure_performance
    def handle_intent(self, message: str) -> str:
        """Handle user message."""
        pass
```

### Database Query Optimization

**Identify slow queries:**

```python
# src/app/db.py - Add query logging

import logging
import time

logger = logging.getLogger(__name__)

class Database:
    def execute(self, query, params=None):
        start = time.perf_counter()
        result = self._execute_impl(query, params)
        elapsed = time.perf_counter() - start
        
        # Log slow queries
        if elapsed > 0.1:  # > 100ms is slow
            logger.warning(f"Slow query ({elapsed:.3f}s): {query}")
            # Suggest index
            if "WHERE" in query and "INDEX" not in query.upper():
                logger.warning(f"  💡 Add index on WHERE columns")
        
        return result
```

**Add indexes:**

```sql
-- scripts/migrations/007_performance_indexes.sql

-- Fast lookups for common queries
CREATE INDEX idx_meetings_created_at ON meetings(created_at DESC);
CREATE INDEX idx_signals_meeting_id ON signals(meeting_id);
CREATE INDEX idx_dikw_level ON dikw_items(level, parent_id);
CREATE INDEX idx_tickets_status ON tickets(status, sprint_id);
CREATE INDEX idx_task_queue_target_status ON agent_task_queue(target_agent, status);

-- Full-text search indexes
CREATE VIRTUAL TABLE meetings_fts USING fts5(title, summary);
CREATE VIRTUAL TABLE documents_fts USING fts5(title, content);
```

### Embedding Query Optimization

```python
# src/app/services/embeddings.py - Query caching

from functools import lru_cache
import hashlib

class EmbeddingService:
    def __init__(self, ...):
        self.search_cache = {}  # Query → results
    
    def search(
        self,
        collection: str,
        query: str,
        top_k: int = 5,
        use_cache: bool = True
    ) -> List[Dict]:
        """Search with optional caching."""
        
        # Cache key
        cache_key = hashlib.md5(
            f"{collection}:{query}:{top_k}".encode()
        ).hexdigest()
        
        if use_cache and cache_key in self.search_cache:
            logger.debug(f"Cache hit: {cache_key}")
            return self.search_cache[cache_key]
        
        # Execute search
        results = self.client.query(
            collection_name=collection,
            query_texts=[query],
            n_results=top_k
        )
        
        # Cache result (24 hour TTL)
        self.search_cache[cache_key] = results
        
        return results
```

### Performance Targets

**Set targets for each component:**

```yaml
# config/performance.yaml

targets:
  api:
    read_latency_p95: 200ms
    write_latency_p95: 500ms
    error_rate: < 0.1%
  
  agents:
    intent_parsing: 100ms
    career_analysis: 3s
    dikw_synthesis: 2s
    meeting_analysis: 5s
  
  embeddings:
    single_query: 200ms
    batch_query_1000: 5s
    indexing_per_1000_items: 10s
  
  mobile:
    sync_time: < 5s
    offline_queries: < 100ms
    apk_size: < 50MB
```

---

## Error Handling & Logging

### Structured Logging

```python
# src/app/agents/arjuna.py

import logging
import json
from typing import Any

logger = logging.getLogger(__name__)

class ArjunaAgent(BaseAgent):
    def handle_intent(self, message: str) -> str:
        """Handle user message with structured logging."""
        
        request_id = str(uuid.uuid4())
        
        try:
            logger.info(
                "intent_request_started",
                extra={
                    "request_id": request_id,
                    "message_length": len(message),
                    "user_id": getattr(self, 'user_id', 'unknown')
                }
            )
            
            intent = self._parse_intent(message)
            
            logger.info(
                "intent_parsed",
                extra={
                    "request_id": request_id,
                    "intent_type": intent.type,
                    "confidence": intent.confidence
                }
            )
            
            result = self._execute_intent(intent)
            
            logger.info(
                "intent_executed",
                extra={
                    "request_id": request_id,
                    "success": True,
                    "execution_time": elapsed
                }
            )
            
            return result
            
        except TimeoutError as e:
            logger.error(
                "intent_execution_timeout",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "intent_type": intent.type
                }
            )
            return "I took too long to respond. Please try again."
        
        except Exception as e:
            logger.exception(
                "intent_execution_failed",
                extra={
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                    "message": str(e)
                }
            )
            return "Sorry, something went wrong."
```

### Error Recovery

```python
class BaseAgent:
    async def ask_llm(self, prompt: str, max_retries: int = 3) -> str:
        """Call LLM with automatic retry on failure."""
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"LLM call (attempt {attempt + 1}/{max_retries})")
                
                response = await self.llm_client.ask(
                    prompt,
                    model=self.config.primary_model,
                    timeout=10
                )
                
                return response
            
            except RateLimitError as e:
                # Exponential backoff for rate limits
                wait_time = 2 ** attempt
                logger.warning(f"Rate limited. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                last_error = e
            
            except TimeoutError as e:
                # Try fallback model
                if self.config.fallback_model:
                    logger.warning(f"Timeout with {self.config.primary_model}. Trying {self.config.fallback_model}...")
                    try:
                        response = await self.llm_client.ask(
                            prompt,
                            model=self.config.fallback_model,
                            timeout=15
                        )
                        return response
                    except Exception as e2:
                        last_error = e2
                else:
                    last_error = e
            
            except Exception as e:
                # Unexpected error - retry
                logger.error(f"Unexpected error: {e}. Retrying...")
                last_error = e
                await asyncio.sleep(1)
        
        # All retries exhausted
        logger.error(f"LLM call failed after {max_retries} attempts")
        raise last_error
```

---

## Documentation

### Code Comments & Docstrings

```python
class ArjunaAgent(BaseAgent):
    """Conversational assistant for task management and insights.
    
    Responsibilities:
    - Parse user intent from natural language
    - Route intents to appropriate handlers or agents
    - Maintain conversation history
    - Generate contextual responses
    
    Design Patterns:
    - Intent Registry: Maps intent types to handlers
    - Dependency Injection: Receives LLM, tools, embeddings
    - Message Queueing: Enqueues tasks to other agents
    
    Example:
        >>> arjuna = ArjunaAgent(config, llm, embeddings)
        >>> response = await arjuna.ask("What should I do today?")
        >>> print(response)
        "You have 3 high-priority tickets and a meeting in 30 minutes."
    
    Performance:
    - Intent parsing: < 100ms (using embeddings)
    - Response generation: < 3s (using LLM)
    - Total latency: < 5s p95
    """
    
    def parse_intent(self, message: str) -> Intent:
        """Extract user intent from message.
        
        This method uses embedding-based similarity matching for common
        intents (create task, search meetings, etc.) and falls back to
        LLM parsing for ambiguous requests.
        
        Args:
            message: Raw user input text
        
        Returns:
            Intent object with type, parameters, and confidence score
        
        Raises:
            ValueError: If message is empty or too long (>5000 chars)
        
        Example:
            >>> intent = arjuna.parse_intent("Add task: review PR")
            >>> intent.type
            'create_ticket'
            >>> intent.confidence
            0.97
        """
        pass
```

### README Documentation

```markdown
## Arjuna Agent

The conversational assistant that helps you stay on top of work.

### Features
- **Intent Recognition** - Understands 20+ intent types
- **Multi-Device Sync** - Keeps sync across all your devices
- **Offline Support** - Works on mobile without internet
- **Quick Actions** - Keyboard shortcuts for common tasks

### Usage

```python
from src.app.agents import get_registry

# Get Arjuna agent
arjuna = get_registry().get("arjuna")

# Ask question
response = await arjuna.ask("What's on my todo list?")
print(response)
```

### Configuration

Edit `config/agents.yaml`:
```yaml
agents:
  arjuna:
    primary_model: gpt-4o-mini  # Fast, cheaper
    fallback_model: gpt-4o      # More capable, fallback
    temperature: 0.7             # Balanced creative/deterministic
    max_tokens: 1000
```

### Performance

- Intent parsing: < 100ms
- Response generation: < 3s
- API latency p95: < 200ms
```

---

## Summary Checklist

**Before You Start Phase 2 (Agent Refactoring):**

- [ ] Understand SOLID principles
- [ ] Read this entire guide
- [ ] Set up testing fixtures (mock LLM)
- [ ] Establish git workflow
- [ ] Review performance targets
- [ ] Set up monitoring/logging
- [ ] Review current code structure
- [ ] Create detailed task list per agent

**During Refactoring:**

- [ ] Small, focused commits
- [ ] Run tests after each change
- [ ] Keep green bar (all tests pass)
- [ ] Document as you go
- [ ] Add logging for debugging
- [ ] Monitor performance

**After Each Agent Extraction:**

- [ ] All tests pass
- [ ] Performance targets met
- [ ] Documentation complete
- [ ] Code review completed
- [ ] Merge to main
- [ ] Tag milestone

**Remember:** Slow, steady refactoring with comprehensive tests beats fast, broken refactoring. 🐢 > 🐇

