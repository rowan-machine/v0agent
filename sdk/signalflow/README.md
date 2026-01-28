# SignalFlow Python SDK

Official Python SDK for the SignalFlow - Memory & Signal Intelligence Platform.

## Installation

```bash
# Basic installation
pip install signalflow-sdk

# With async support
pip install signalflow-sdk[async]

# With AI analyst features
pip install signalflow-sdk[analyst]

# Full installation
pip install signalflow-sdk[all]
```

## Quick Start

### Synchronous Client

```python
from signalflow import SignalFlowClient

# Initialize client
client = SignalFlowClient(
    base_url="https://api.signalflow.io",
    api_key="your-api-key"
)

# List meetings
meetings = client.meetings.list(limit=10)
for meeting in meetings["items"]:
    print(f"Meeting: {meeting['title']}")

# Create a meeting
meeting = client.meetings.create(
    title="Sprint Planning",
    content="Discussed sprint goals..."
)

# Get signals from a meeting
signals = client.signals.for_meeting(meeting["id"])
for signal in signals["items"]:
    print(f"[{signal['signal_type']}] {signal['content']}")

# List tickets
tickets = client.tickets.list(status="in_progress")

# Access DIKW knowledge items
knowledge = client.knowledge.list(level="knowledge")

# Get career profile
profile = client.career.get_profile()
```

### Async Client

```python
import asyncio
from signalflow import AsyncSignalFlowClient

async def main():
    async with AsyncSignalFlowClient(
        base_url="https://api.signalflow.io",
        api_key="your-api-key"
    ) as client:
        # Concurrent requests
        meetings, signals, tickets = await asyncio.gather(
            client.meetings.list(),
            client.signals.list(signal_type="action_item"),
            client.tickets.list(status="todo"),
        )
        
        print(f"Found {len(meetings['items'])} meetings")
        print(f"Found {len(signals['items'])} action items")
        print(f"Found {len(tickets['items'])} todo tickets")

asyncio.run(main())
```

## API Reference

### SignalFlowClient

The main synchronous client.

#### Initialization

```python
client = SignalFlowClient(
    base_url: str,           # API base URL
    api_key: str = None,     # Optional API key
    timeout: int = 30,       # Request timeout in seconds
)
```

#### Available Clients

- `client.meetings` - Meetings CRUD operations
- `client.signals` - Signal extraction and management
- `client.tickets` - Ticket and sprint management
- `client.knowledge` - DIKW knowledge hierarchy
- `client.career` - Career profile and suggestions

### AsyncSignalFlowClient

The async client with the same interface.

```python
async with AsyncSignalFlowClient(base_url, api_key) as client:
    # Use await for all operations
    meetings = await client.meetings.list()
```

## Domain Clients

### Meetings

```python
# List meetings with pagination
meetings = client.meetings.list(skip=0, limit=20)

# Get single meeting
meeting = client.meetings.get(meeting_id=1)

# Create meeting
meeting = client.meetings.create(
    title="Sprint Planning",
    content="Meeting notes...",
    tags=["sprint", "planning"]
)

# Update meeting
meeting = client.meetings.update(
    meeting_id=1,
    title="Updated Title"
)

# Delete meeting
client.meetings.delete(meeting_id=1)

# Search meetings
results = client.meetings.search(query="sprint planning")
```

### Signals

```python
# List all signals
signals = client.signals.list()

# Filter by type
action_items = client.signals.list(signal_type="action_item")
decisions = client.signals.list(signal_type="decision")

# Get signals for a meeting
meeting_signals = client.signals.for_meeting(meeting_id=1)

# Update signal status
client.signals.update_status(
    signal_id=1,
    status="resolved"
)
```

### Tickets

```python
# List tickets
tickets = client.tickets.list()

# Filter by status
in_progress = client.tickets.list(status="in_progress")

# Filter by sprint
sprint_tickets = client.tickets.list(sprint_id=5)

# Create ticket
ticket = client.tickets.create(
    title="Implement feature",
    description="Feature description",
    priority="high",
    sprint_id=5
)

# Update ticket
ticket = client.tickets.update(
    ticket_id=1,
    status="done"
)
```

### Knowledge (DIKW)

```python
# List DIKW items
items = client.knowledge.list()

# Filter by level
knowledge_items = client.knowledge.list(level="knowledge")

# Get single item
item = client.knowledge.get(item_id=1)

# Create item
item = client.knowledge.create(
    level="information",
    title="API Best Practices",
    content="Always use proper error handling..."
)

# Promote item to higher level
promoted = client.knowledge.promote(
    item_id=1,
    target_level="wisdom"
)

# Synthesize items
synthesized = client.knowledge.synthesize(
    item_ids=[1, 2, 3],
    target_level="knowledge"
)
```

### Career

```python
# Get career profile
profile = client.career.get_profile()

# Update profile
profile = client.career.update_profile(
    role_current="Senior Developer",
    role_target="Tech Lead",
    strengths=["Python", "System Design"]
)

# Get suggestions
suggestions = client.career.get_suggestions()

# Accept/reject suggestion
client.career.respond_to_suggestion(
    suggestion_id=1,
    action="accept"
)

# Record memory
client.career.record_memory(
    memory_type="completed_project",
    title="Launched v2.0",
    description="Led the team..."
)
```

## Error Handling

```python
from signalflow import SignalFlowClient
from signalflow.exceptions import (
    SignalFlowError,
    NotFoundError,
    ValidationError,
    AuthenticationError,
)

client = SignalFlowClient(base_url, api_key)

try:
    meeting = client.meetings.get(999)
except NotFoundError:
    print("Meeting not found")
except ValidationError as e:
    print(f"Validation error: {e.message}")
except AuthenticationError:
    print("Invalid API key")
except SignalFlowError as e:
    print(f"API error: {e}")
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=signalflow

# Type checking
mypy signalflow

# Linting
ruff check signalflow
```

### Building

```bash
# Build package
python -m build

# Upload to PyPI
twine upload dist/*
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## Support

- Documentation: https://docs.signalflow.io/sdk
- Issues: https://github.com/signalflow/signalflow-sdk/issues
- Email: support@signalflow.io
