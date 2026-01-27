# SignalFlow SDK

A Python client library for the SignalFlow meeting intelligence platform.

## Installation

```bash
# Basic installation
pip install signalflow-sdk

# With LangSmith analytics support
pip install "signalflow-sdk[analyst]"

# From source (development)
pip install -e "sdk/[dev]"
```

## Quick Start

### API Client

```python
from signalflow import SignalFlowClient, SignalType

# Initialize client
client = SignalFlowClient(environment="staging")
# Or: client = SignalFlowClient(api_url="http://localhost:8001")

# List recent meetings
meetings = client.meetings.list(limit=10)
for meeting in meetings.meetings:
    print(f"{meeting.meeting_name} - {meeting.meeting_date}")

# Search for action items
signals = client.signals.search("TODO", signal_type=SignalType.ACTION_ITEM)

# Get DIKW knowledge pyramid
pyramid = client.knowledge.get_pyramid()
print(f"Knowledge items: {pyramid.counts}")

# Create a ticket
ticket = client.tickets.create(
    title="Review Q4 goals",
    description="Discussed in team meeting",
    priority="high"
)
```

### Analyst Client (LangSmith Integration)

```python
from signalflow import AnalystClient

# Initialize (uses LANGSMITH_API_KEY env var)
analyst = AnalystClient()

# Get feedback summary for last week
summary = analyst.get_feedback_summary(days=7)
print(f"Total runs: {summary.total_runs}")
print(f"Average score: {summary.avg_score}")

# Get agent performance
perf = analyst.get_agent_performance("Arjuna")
print(f"Arjuna error rate: {perf.error_rate}%")

# Submit feedback for a trace
analyst.submit_feedback(
    run_id="run-xxx-xxx",
    score=0.9,
    comment="Very helpful response!"
)

# Get project statistics
stats = analyst.get_project_stats()
```

## Configuration

### Environment Variables

```bash
# API Client
export SIGNALFLOW_API_URL=http://localhost:8001
export SIGNALFLOW_API_KEY=your-api-key  # Optional

# Analyst Client (LangSmith)
export LANGSMITH_API_KEY=your-langsmith-key
export LANGSMITH_PROJECT=signalflow
```

### Environments

The SDK supports predefined environments:

| Environment | API URL |
|------------|---------|
| `local` | `http://localhost:8001` |
| `staging` | `https://v0agent-staging.up.railway.app` |
| `production` | `https://v0agent-production.up.railway.app` |

```python
# Use predefined environment
client = SignalFlowClient(environment="production")

# Or specify custom URL
client = SignalFlowClient(api_url="https://custom.api.com")
```

## Data Models

The SDK provides typed Pydantic models for all API responses:

```python
from signalflow.models import (
    Meeting,
    Signal,
    Ticket,
    DIKWItem,
    CareerProfile,
    CareerSuggestion,
    DIKWLevel,
    SignalType,
    TicketStatus,
)

# Type-safe access
meeting: Meeting = client.meetings.get("meeting-123")
print(meeting.signals)  # Dict[str, List[str]]

# Enums for filtering
tickets = client.tickets.list(status=TicketStatus.IN_PROGRESS)
signals = client.signals.list_recent(signal_type=SignalType.DECISION)
```

## API Reference

### SignalFlowClient

| Method | Description |
|--------|-------------|
| `meetings.list(limit, offset)` | List meetings with pagination |
| `meetings.get(id)` | Get a single meeting |
| `meetings.search(query)` | Search meetings |
| `meetings.get_signals(id)` | Get signals for a meeting |
| `signals.search(query, type)` | Search signals |
| `signals.list_recent(limit)` | List recent signals |
| `tickets.list(status)` | List tickets |
| `tickets.get(id)` | Get a ticket |
| `tickets.create(title, ...)` | Create a ticket |
| `tickets.update_status(id, status)` | Update ticket status |
| `knowledge.get_pyramid()` | Get DIKW pyramid |
| `knowledge.list_items(level)` | List DIKW items |
| `knowledge.search(query)` | Search knowledge |
| `career.get_profile()` | Get career profile |
| `career.get_suggestions()` | Get career suggestions |

### AnalystClient

| Method | Description |
|--------|-------------|
| `submit_feedback(run_id, score, comment)` | Submit trace feedback |
| `get_run(run_id)` | Get trace details |
| `list_runs(days)` | List recent traces |
| `get_feedback_for_run(run_id)` | Get feedback for a trace |
| `get_feedback_summary(days)` | Get aggregated feedback |
| `get_agent_performance(name)` | Get agent metrics |
| `get_project_stats()` | Get project statistics |

## Development

```bash
# Install dev dependencies
pip install -e "sdk/[dev]"

# Run tests
pytest sdk/tests/

# Type checking
mypy sdk/signalflow/
```

## License

MIT License - see LICENSE file for details.
