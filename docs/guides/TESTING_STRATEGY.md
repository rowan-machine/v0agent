# Comprehensive Testing Strategy

**Status:** Architecture & Planning Document  
**Purpose:** Define test categories, fixtures, mocks, and CI/CD integration  

---

## 1. Testing Pyramid & Coverage

```
           E2E Tests (5-10%)
         /                  \
        /                    \
    Integration Tests (20-30%)
      /                      \
    /                        \
  Unit Tests (60-70%)
```

### Testing Categories

| Category | Purpose | Coverage Target | Tools |
|----------|---------|-----------------|-------|
| **Unit Tests** | Test individual functions/classes | 80%+ | pytest, unittest.mock |
| **Integration Tests** | Test component interactions | 60%+ | pytest, FastAPI TestClient |
| **E2E Tests** | Test complete workflows | 50%+ | pytest, Selenium (optional) |
| **Smoke Tests** | Quick sanity checks | 30%+ | pytest |
| **Performance Tests** | Load/stress testing | Critical paths | locust (optional) |
| **Security Tests** | Vulnerabilities & auth | All auth | bandit, custom |

---

## 2. Test Structure

```
tests/
├── __init__.py
├── conftest.py                          # Shared fixtures & config
├── fixtures/
│   ├── __init__.py
│   ├── db_fixtures.py                  # Database mocks
│   ├── llm_fixtures.py                 # LLM mocks
│   ├── agent_fixtures.py               # Agent mocks
│   └── api_fixtures.py                 # API request fixtures
├── unit/
│   ├── test_agents.py                  # Agent logic
│   ├── test_services.py                # Service layer
│   ├── test_mcp_tools.py               # Tool registry
│   ├── test_agent_bus.py               # Message bus
│   ├── test_embeddings.py              # Embedding service
│   ├── test_encryption.py              # Security
│   └── test_config.py                  # Configuration
├── integration/
│   ├── test_agent_communication.py     # Agent-to-agent messaging
│   ├── test_api_routes.py              # API endpoints
│   ├── test_database_operations.py     # Database interactions
│   ├── test_search_integration.py      # Search with embeddings
│   ├── test_signal_extraction.py       # Meeting analysis
│   └── test_mcp_integration.py         # MCP server integration
├── e2e/
│   ├── test_workflows.py               # Complete workflows
│   ├── test_agent_coordination.py      # Multi-agent workflows
│   └── test_user_scenarios.py          # Real-world scenarios
├── smoke/
│   ├── test_startup.py                 # Can app start?
│   ├── test_health_checks.py           # Health endpoints
│   └── test_basic_operations.py        # Basic sanity
├── performance/
│   ├── test_load.py                    # Load testing
│   └── test_stress.py                  # Stress testing
└── security/
    ├── test_auth.py                    # Authentication
    ├── test_authorization.py           # Access control
    └── test_injection.py               # SQL injection, etc.
```

---

## 3. Fixtures & Mocks

### 3.1 Database Fixtures

```python
# tests/fixtures/db_fixtures.py (NEW)

import pytest
import sqlite3
from contextlib import contextmanager
import tempfile
import shutil
from pathlib import Path

@pytest.fixture
def temp_db():
    """Create temporary database for tests."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    
    yield str(db_path)
    
    # Cleanup
    shutil.rmtree(temp_dir)

@pytest.fixture
def db_connection(temp_db):
    """Get database connection with schema."""
    from src.app.db import initialize_db, connect
    
    initialize_db(temp_db)
    
    with connect(temp_db) as conn:
        yield conn

@pytest.fixture
def sample_meeting(db_connection):
    """Create sample meeting in database."""
    db_connection.execute("""
        INSERT INTO meeting_summaries 
        (title, date, transcript, summary, attendees)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "Test Meeting",
        "2024-01-15",
        "Meeting transcript...",
        "Meeting summary...",
        "Alice, Bob, Charlie"
    ))
    db_connection.commit()
    
    return db_connection.execute(
        "SELECT * FROM meeting_summaries WHERE title = ?",
        ("Test Meeting",)
    ).fetchone()

@pytest.fixture
def sample_document(db_connection):
    """Create sample document in database."""
    db_connection.execute("""
        INSERT INTO docs 
        (title, content, source)
        VALUES (?, ?, ?)
    """, (
        "Test Document",
        "Document content...",
        "test_source"
    ))
    db_connection.commit()
    
    return db_connection.execute(
        "SELECT * FROM docs WHERE title = ?",
        ("Test Document",)
    ).fetchone()

@pytest.fixture
def sample_signal(db_connection, sample_meeting):
    """Create sample signal in database."""
    # Signals are extracted from meetings
    meeting_id = sample_meeting["id"]
    
    db_connection.execute("""
        INSERT INTO signal_status 
        (signal_type, signal_text, source_meeting_id, status)
        VALUES (?, ?, ?, ?)
    """, (
        "decision",
        "We will use PostgreSQL for the new system",
        meeting_id,
        "active"
    ))
    db_connection.commit()
    
    return db_connection.execute(
        "SELECT * FROM signal_status WHERE signal_type = ?",
        ("decision",)
    ).fetchone()

@pytest.fixture
def db_with_sample_data(db_connection, sample_meeting, sample_document, sample_signal):
    """Database preloaded with sample data."""
    return db_connection
```

### 3.2 LLM Fixtures (Mock OpenAI)

```python
# tests/fixtures/llm_fixtures.py (NEW)

import pytest
from unittest.mock import Mock, patch, AsyncMock
import json

@pytest.fixture
def mock_openai():
    """Mock OpenAI API responses."""
    
    with patch("src.app.llm.openai.ChatCompletion.create") as mock_chat:
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Mock LLM response",
                    "role": "assistant"
                }
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        }
        mock_chat.return_value = mock_response
        yield mock_chat

@pytest.fixture
def mock_embeddings():
    """Mock embedding generation."""
    
    with patch("src.app.services.embeddings.openai.Embedding.create") as mock_embed:
        # Return mock embedding
        mock_embed.return_value = {
            "data": [{
                "embedding": [0.1] * 1536,  # 1536-dim embedding
                "index": 0
            }]
        }
        yield mock_embed

@pytest.fixture
def mock_llm_response():
    """Mock structured LLM response."""
    
    class MockLLMResponse:
        def __init__(self, content, role="assistant", tokens=150):
            self.content = content
            self.role = role
            self.tokens = tokens
        
        def to_dict(self):
            return {
                "content": self.content,
                "role": self.role,
                "tokens": self.tokens
            }
    
    return MockLLMResponse
```

### 3.3 Agent Fixtures

```python
# tests/fixtures/agent_fixtures.py (NEW)

import pytest
from src.app.agents.base import BaseAgent
from src.app.services.agent_bus import AgentBus, AgentMessage, MessagePriority
from unittest.mock import Mock, AsyncMock
from datetime import datetime
import uuid

@pytest.fixture
def mock_agent():
    """Create mock agent for testing."""
    
    class MockAgent(BaseAgent):
        async def process_message(self, msg):
            return {"status": "success", "message_id": msg.id}
        
        async def startup(self):
            self.state = "ready"
        
        async def shutdown(self):
            self.state = "stopped"
    
    return MockAgent(name="test_agent")

@pytest.fixture
def agent_bus(temp_db):
    """Agent message bus."""
    return AgentBus(db_path=temp_db)

@pytest.fixture
def sample_agent_message():
    """Sample agent message."""
    return AgentMessage(
        id=str(uuid.uuid4()),
        source_agent="test_agent_1",
        target_agent="test_agent_2",
        message_type="query",
        content={"query": "What is the status?"},
        priority=MessagePriority.NORMAL,
        created_at=datetime.now(),
    )

@pytest.fixture
def agent_registry(mock_agent):
    """Agent registry with mock agent."""
    from src.app.services.agent_lifecycle import AgentRegistry
    
    registry = AgentRegistry()
    registry.register(mock_agent, dependencies=[])
    return registry
```

### 3.4 API Fixtures

```python
# tests/fixtures/api_fixtures.py (NEW)

import pytest
from fastapi.testclient import TestClient
from src.app.main import app
import json

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """Authentication headers for tests."""
    return {
        "Authorization": "Bearer test_token_12345",
        "Content-Type": "application/json"
    }

@pytest.fixture
def sample_api_request():
    """Sample API request data."""
    return {
        "meetings": [
            {
                "title": "Q1 Planning",
                "date": "2024-01-15",
                "attendees": ["Alice", "Bob"],
                "transcript": "Meeting content here..."
            }
        ],
        "documents": [
            {
                "title": "API Design",
                "content": "Document content here...",
                "tags": ["technical", "design"]
            }
        ]
    }
```

### 3.5 Conftest (Central Configuration)

```python
# tests/conftest.py (NEW)

import pytest
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load test configuration
from dotenv import load_dotenv
load_dotenv(".env.test")

# Import all fixtures
from tests.fixtures.db_fixtures import *
from tests.fixtures.llm_fixtures import *
from tests.fixtures.agent_fixtures import *
from tests.fixtures.api_fixtures import *

# Global test configuration
@pytest.fixture(scope="session")
def test_config():
    """Test environment configuration."""
    return {
        "database_path": ":memory:",
        "enable_multi_agent": True,
        "enable_embeddings": False,  # Speed up tests
        "enable_neo4j": False,
        "llm_mode": "mock",  # Use mock LLM
        "log_level": "DEBUG",
    }

@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset module state between tests."""
    # Reset singletons
    import src.app.services.agent_bus as bus_module
    bus_module._bus = None
    
    import src.app.mcp.tool_registry as tool_module
    tool_module._tool_registry = None
    
    yield

@pytest.fixture(autouse=True)
def mock_env(monkeypatch, test_config):
    """Mock environment variables."""
    for key, value in test_config.items():
        monkeypatch.setenv(key.upper(), str(value))

# Markers for test categorization
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests"
    )
    config.addinivalue_line(
        "markers", "smoke: Smoke tests"
    )
    config.addinivalue_line(
        "markers", "performance: Performance tests"
    )
    config.addinivalue_line(
        "markers", "security: Security tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests (exclude with -m 'not slow')"
    )
```

---

## 4. Test Examples

### 4.1 Unit Test Example

```python
# tests/unit/test_agents.py (EXAMPLE)

import pytest
from src.app.agents.base import BaseAgent
from src.app.services.agent_bus import AgentMessage, MessagePriority
from datetime import datetime
import uuid

@pytest.mark.unit
class TestAgentBase:
    
    async def test_agent_initialization(self, mock_agent):
        """Test agent initializes correctly."""
        assert mock_agent.name == "test_agent"
        assert mock_agent.state == "idle"
        assert mock_agent.metrics["messages_processed"] == 0
    
    async def test_agent_can_startup(self, mock_agent):
        """Test agent startup."""
        await mock_agent.startup()
        assert mock_agent.state == "ready"
    
    async def test_agent_can_shutdown(self, mock_agent):
        """Test agent shutdown."""
        await mock_agent.startup()
        await mock_agent.shutdown()
        assert mock_agent.state == "stopped"
    
    async def test_agent_processes_message(self, mock_agent, sample_agent_message):
        """Test agent processes incoming message."""
        result = await mock_agent.process_message(sample_agent_message)
        assert result["status"] == "success"
        assert result["message_id"] == sample_agent_message.id

@pytest.mark.unit
class TestAgentBus:
    
    def test_send_message(self, agent_bus, sample_agent_message):
        """Test sending a message on the bus."""
        msg_id = agent_bus.send(sample_agent_message)
        assert msg_id == sample_agent_message.id
    
    def test_receive_messages(self, agent_bus, sample_agent_message):
        """Test receiving messages."""
        agent_bus.send(sample_agent_message)
        
        messages = agent_bus.receive("test_agent_2", limit=10)
        assert len(messages) == 1
        assert messages[0].id == sample_agent_message.id
    
    def test_message_status_lifecycle(self, agent_bus, sample_agent_message):
        """Test message status transitions."""
        msg_id = agent_bus.send(sample_agent_message)
        
        # Mark processing
        agent_bus.mark_processing(msg_id)
        # Check status...
        
        # Mark completed
        agent_bus.mark_completed(msg_id)
        # Check status...
```

### 4.2 Integration Test Example

```python
# tests/integration/test_agent_communication.py (EXAMPLE)

import pytest
from src.app.services.agent_lifecycle import AgentRegistry
from src.app.services.agent_bus import AgentBus, AgentMessage, MessagePriority

@pytest.mark.integration
class TestAgentCommunication:
    
    async def test_agent_to_agent_messaging(self, agent_registry, agent_bus):
        """Test one agent sending to another."""
        
        # Start agents
        await agent_registry.startup_all()
        
        # Agent 1 sends query to Agent 2
        msg = AgentMessage(
            id="test_123",
            source_agent="agent_1",
            target_agent="agent_2",
            message_type="query",
            content={"question": "What's the status?"},
        )
        
        agent_bus.send(msg)
        
        # Agent 2 receives message
        messages = agent_bus.receive("agent_2")
        assert len(messages) > 0
        
        # Cleanup
        await agent_registry.shutdown_all()
    
    async def test_broadcast_messaging(self, agent_bus):
        """Test broadcasting to all agents."""
        
        msg = AgentMessage(
            id="broadcast_1",
            source_agent="system",
            target_agent=None,  # Broadcast
            message_type="notification",
            content={"event": "system_initialized"},
        )
        
        agent_bus.send(msg)
        
        # All agents can receive
        messages_1 = agent_bus.receive("agent_1")
        messages_2 = agent_bus.receive("agent_2")
        
        assert len(messages_1) > 0
        assert len(messages_2) > 0
```

### 4.3 E2E Test Example

```python
# tests/e2e/test_workflows.py (EXAMPLE)

import pytest

@pytest.mark.e2e
class TestCompleteWorkflows:
    
    async def test_meeting_analysis_workflow(self, client, sample_meeting, agent_registry):
        """Test complete meeting analysis workflow."""
        
        # 1. Upload meeting
        response = client.post(
            "/api/meetings",
            json={"title": "Q1 Planning", "transcript": "Meeting content..."}
        )
        assert response.status_code == 201
        meeting_id = response.json()["id"]
        
        # 2. Trigger analysis
        response = client.post(
            f"/api/meetings/{meeting_id}/analyze"
        )
        assert response.status_code == 202  # Accepted
        
        # 3. Get results (polling)
        for _ in range(10):  # Try 10 times
            response = client.get(f"/api/meetings/{meeting_id}")
            if response.json()["status"] == "analyzed":
                break
            await asyncio.sleep(0.1)
        
        assert response.json()["status"] == "analyzed"
        assert len(response.json()["signals"]) > 0
```

---

## 5. CI/CD Integration

### 5.1 GitHub Actions Workflow

```yaml
# .github/workflows/test.yml (NEW)

name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .
        pip install pytest pytest-cov pytest-asyncio pytest-xdist
    
    - name: Run unit tests
      run: pytest tests/unit -v --cov=src/app --cov-report=xml
    
    - name: Run integration tests
      run: pytest tests/integration -v
    
    - name: Run smoke tests
      run: pytest tests/smoke -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Generate coverage report
      run: coverage report --fail-under=70

  lint:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
    
    - name: Install tools
      run: |
        pip install pylint black isort flake8
    
    - name: Format check
      run: |
        black --check src/
        isort --check src/
    
    - name: Lint
      run: |
        pylint src/
        flake8 src/
    
    - name: Security check
      run: |
        pip install bandit
        bandit -r src/ -ll

  e2e:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .
        pip install pytest pytest-asyncio
    
    - name: Start application
      run: python -m src.app.main &
      timeout-minutes: 2
    
    - name: Run E2E tests
      run: pytest tests/e2e -v --timeout=30
```

### 5.2 Pytest Configuration

```ini
# pytest.ini (NEW)

[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --tb=short
    --disable-warnings
    -ra
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    smoke: Smoke tests
    performance: Performance tests
    security: Security tests
    slow: Slow tests
asyncio_mode = auto
timeout = 300
```

---

## 6. Test Running & Reporting

### 6.1 Local Test Commands

```bash
# Run all tests
pytest tests/

# Run specific category
pytest tests/unit -v
pytest tests/integration -v
pytest tests/e2e -v
pytest tests/smoke -v

# Run with coverage
pytest tests/ --cov=src/app --cov-report=html

# Run specific test
pytest tests/unit/test_agents.py::TestAgentBase::test_agent_initialization -v

# Run excluding slow tests
pytest tests/ -m "not slow"

# Run with parallel execution (faster)
pytest tests/ -n auto

# Generate test report
pytest tests/ --html=report.html --self-contained-html
```

### 6.2 Coverage Goals

```
Target Coverage by Module:
├── agents/                      85%+
├── services/                    80%+
├── mcp/                         75%+
├── api/                         70%+
├── db.py                        85%+
├── config.py                    90%+
├── llm.py                       75%+
└── Overall                      75%+
```

---

## 7. Testing Best Practices

### 7.1 Do's

✅ Test one thing per test  
✅ Use descriptive test names  
✅ Use fixtures for setup/teardown  
✅ Mock external dependencies  
✅ Test error cases  
✅ Keep tests fast (< 100ms for unit)  
✅ Test edge cases and boundaries  
✅ Maintain test isolation  

### 7.2 Don'ts

❌ Don't test external APIs directly  
❌ Don't create real files in tests  
❌ Don't hardcode test data  
❌ Don't make tests dependent on order  
❌ Don't ignore flaky tests  
❌ Don't test implementation details  
❌ Don't skip error cases  

---

## 8. Debugging Failed Tests

```bash
# Run with debugging
pytest tests/ -vv --pdb

# Run with print statements
pytest tests/ -s

# Run with detailed traceback
pytest tests/ --tb=long

# Run single test with full output
pytest tests/unit/test_agents.py::test_agent_initialization -vv -s

# Save failed test info
pytest tests/ --lf  # Run last failed
pytest tests/ --ff  # Run failed first
```

---

## Summary

✅ **Comprehensive Coverage**: Unit → Integration → E2E → Smoke  
✅ **Organized Structure**: Fixtures, mocks, test categories  
✅ **CI/CD Ready**: GitHub Actions workflow  
✅ **Extensible**: Easy to add new test categories  
✅ **Best Practices**: Isolation, speed, clarity  
✅ **Debugging Support**: Multiple ways to investigate failures

