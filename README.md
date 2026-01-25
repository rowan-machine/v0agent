# SignalFlow

> **Personal meeting intelligence and sprint workflow system**

SignalFlow is a local-first productivity platform that transforms meeting notes into actionable intelligence. It extracts signals, organizes knowledge using the DIKW pyramid, and guides you through structured sprint workflows.

![SignalFlow](https://img.shields.io/badge/SignalFlow-v2.0-6366f1?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)

---

## ✨ Features

### 🎯 Signal Extraction
Automatically extract 5 types of signals from meeting notes:
- **Decisions** — What was decided
- **Action Items** — Tasks to complete
- **Blockers** — What's preventing progress
- **Risks** — Potential issues identified
- **Ideas** — New proposals and suggestions

### 🔺 DIKW Pyramid
Promote signals through knowledge levels with AI-assisted synthesis:
```
Data → Information → Knowledge → Wisdom
```
- **Data**: Raw signals and facts
- **Information**: Contextualized insights
- **Knowledge**: Actionable patterns
- **Wisdom**: Strategic principles

### 🔄 Workflow Modes
Customizable workflow modes to match your development process. Each mode has a distinct color and can be configured with its own checklist:

- **7 default modes** (A-G) with customizable names, icons, and checklists
- **Color-coded visualization** - borders and indicators change with each mode
- **Progress tracking** - Check off tasks as you complete each phase
- **Flexible workflow** - Adapt the system to your sprint methodology

Configure modes in the settings to match your team's workflow (planning → implementation → review → deployment, etc.)

### 🤖 Integrated AI Capabilities
Powered by LLM intelligence throughout the platform:

- **Smart Signal Extraction** — AI automatically identifies decisions, actions, blockers, risks, and ideas from meeting notes
- **DIKW Synthesis** — AI generates contextual summaries when promoting signals through knowledge levels
- **Quick Ask** — Natural language dashboard queries ("Show my blockers", "What was decided about the API?")
- **Ticket Decomposition** — Break down tickets into actionable subtasks with AI assistance
- **Implementation Planning** — Generate step-by-step plans for ticket completion
- **Career Coaching** — Get personalized suggestions based on your work patterns and sprint data
- **Semantic Search** — Find relevant content using natural language, powered by embeddings
- **Meeting Analyzer** — Extract structured insights from unstructured meeting notes
- **Learning Loop** — System improves signal extraction quality based on your feedback

### 🎫 Ticket Management
- Create tickets from signals
- AI-powered ticket decomposition
- Implementation plan generation
- Status tracking (todo, in_progress, blocked, in_review, done)

### 💬 AI Quick Actions
One-click AI queries from the dashboard:
- Current blockers
- Recent decisions
- Outstanding action items
- @mentions
- Reach-outs needed

### 🔐 Session Authentication
Simple password-based authentication with secure session management.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- OpenAI API key

### Installation

```bash
# Clone the repository
git clone https://github.com/rowan-machine/v0agent.git
cd v0agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Environment Variables

Create a `.env` file:

```env
# Required
OPENAI_API_KEY=sk-your-api-key-here

# Optional
AUTH_PASSWORD=your-secure-password  # Default: signalflow
SECRET_KEY=your-secret-key          # For session encryption
USER_NAME=YourName                  # Display name in profile (default: Rowan)
DEFAULT_AI_MODEL=gpt-4o-mini        # AI model to use
```

### Run the Server

```bash
# Development mode with auto-reload
uvicorn src.app.main:app --reload --port 8000

# Production mode
uvicorn src.app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 and log in with your password.

---

## 🛠️ Development Setup (Clone to New Machine)

If you're setting up this project on a new machine (personal computer, etc.):

### 1. Clone & Basic Setup
```bash
git clone https://github.com/rowan-machine/v0agent.git
cd v0agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Database Initialization
The SQLite database (`agent.db`) is created automatically on first run. If you need to start fresh:
```bash
rm agent.db  # Remove existing database
uvicorn src.app.main:app --reload --port 8000  # Creates new DB with schema
```

### 3. Optional: Supabase Sync
If using Supabase for cloud sync:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key  # For migrations
```

### 4. Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_notifications_api.py -v

# Run with coverage
pytest tests/ --cov=src/app --cov-report=html
```

### 5. Optional: Playwright E2E Tests
```bash
pip install playwright pytest-playwright
playwright install chromium
pytest tests/e2e/ --browser chromium  # When e2e tests are created
```

---

## 📖 Usage Guide

### Adding Meeting Notes

1. Navigate to **Meetings** → **New Meeting**
2. Paste your meeting notes (supports markdown)
3. Add meeting name and date
4. Click **Save** — signals are automatically extracted

### Working with Signals

Signals appear on the dashboard with action buttons:

| Button | Action |
|--------|--------|
| ✓ | Promote to DIKW (Data level) |
| ✕ | Reject signal |
| 📦 | Archive signal |
| ↑ | Choose DIKW level to promote to |

### Using the DIKW Pyramid

1. **Approve signals** to add them to the Data level
2. **Click ↑** on any DIKW item to promote it
3. **Merge items** at the same level for synthesis
4. AI generates summaries appropriate to each level

### Workflow Modes

1. Click the **mode indicator** (top-right corner)
2. Select your current workflow mode (A-F)
3. Use the **workflow panel** checklist to track progress
4. Click **Next Step →** to advance modes

### AI Quick Actions

1. Click any **chip** on the dashboard (Blockers, Decisions, etc.)
2. Or type a custom question in the input field
3. AI response appears with action buttons:
   - **Save to Memory** — Store for future context
   - **Dismiss** — Close without saving
   - **Create Ticket** — Convert to actionable ticket

### Managing Tickets

1. Navigate to **Tickets** → **New Ticket**
2. Paste ticket ID and description
3. Use **AI Decompose** to break into subtasks
4. Use **Generate Plan** for implementation steps

---

## 🏗️ Architecture

```
signalflow/
├── src/app/
│   ├── main.py          # FastAPI routes & API endpoints
│   ├── db.py            # SQLite schema & connections
│   ├── db_adapter.py    # DualWriteDB (SQLite + Supabase)
│   ├── tracing.py       # LangSmith tracing integration
│   ├── llm.py           # OpenAI integration
│   ├── auth.py          # Session authentication
│   ├── meetings.py      # Meeting parsing & signal extraction
│   ├── search.py        # Full-text & semantic search
│   ├── agents/          # Multi-agent system
│   │   ├── registry.py  # AgentRegistry
│   │   ├── arjuna.py    # Arjuna intent classifier
│   │   ├── career_coach.py
│   │   ├── meeting_analyzer.py
│   │   └── dikw_synthesizer.py
│   ├── api/v1/          # REST API endpoints
│   ├── services/        # Business logic & agent bus
│   ├── templates/       # Jinja2 HTML templates
│   └── static/          # CSS, JS assets
├── mobile/              # React Native Expo app
├── prompts/             # Agent-specific prompts
├── agent.db             # SQLite database (local-first)
├── .env                 # Environment variables
└── requirements.txt
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `meeting_summaries` | Meeting notes and extracted signals |
| `docs` | Supporting documents |
| `tickets` | Task tickets with AI summaries |
| `dikw_items` | DIKW pyramid items |
| `signal_status` | Signal approval/rejection tracking |
| `ai_memory` | Saved AI responses |
| `sprint_settings` | Sprint configuration |
| `settings` | User preferences |

---

## 🔌 API Reference

### Signals API

```bash
# Update signal status
POST /api/signals/status
{
  "meeting_id": 1,
  "signal_type": "decision",
  "signal_text": "We will use React",
  "status": "approved"
}

# Convert signal to ticket
POST /api/signals/convert-to-ticket
{
  "meeting_id": 1,
  "signal_type": "action",
  "signal_text": "Set up CI/CD pipeline"
}
```

### DIKW API

```bash
# Get pyramid items
GET /api/dikw?level=knowledge&status=active

# Promote signal to DIKW
POST /api/dikw/promote-signal
{
  "signal_text": "...",
  "signal_type": "decision",
  "meeting_id": 1,
  "level": "data"
}

# Promote item to next level
POST /api/dikw/promote
{
  "item_id": 1
}

# Merge multiple items
POST /api/dikw/merge
{
  "item_ids": [1, 2, 3]
}
```

### AI API

```bash
# Quick ask
POST /api/dashboard/quick-ask
{
  "topic": "blockers"
}
# or
{
  "query": "What decisions were made about the API?"
}
```

### Settings API

```bash
# Get/set workflow mode
GET /api/settings/mode
POST /api/settings/mode
{
  "mode": "mode-b"
}

# Get/set workflow progress
GET /api/settings/workflow-progress/mode-a
POST /api/settings/workflow-progress
{
  "mode": "mode-a",
  "progress": [true, false, true, false]
}
```

---

## 🛠️ Development

### Running Tests

```bash
pytest tests/
```

### Database Reset

```bash
rm agent.db
python -c "from src.app.db import init_db; init_db()"
```

### Checking Logs

```bash
# Run with debug logging
uvicorn src.app.main:app --reload --log-level debug
```

### Adding New Signal Types

1. Update signal extraction regex in `meetings.py`
2. Add icon mapping in `dashboard.html`
3. Update DIKW promotion prompts in `main.py`

---

## 🗺️ Roadmap

### ✅ Completed (v2.0 Migration)
- [x] Multi-agent architecture with AgentRegistry
- [x] MCP (Model Context Protocol) tool integration
- [x] Embeddings-based semantic search (pgvector on Supabase)
- [x] Hybrid search (keyword + semantic)
- [x] Supabase cloud backend (28 tables migrated)
- [x] DualWriteDB adapter for local-first + cloud sync
- [x] LangSmith tracing for observability
- [x] API v1 endpoints with Pydantic validation
- [x] React Native Expo mobile app scaffold
- [x] Smart suggestions based on embeddings

### 📋 Future Enhancements (Deferred)
- [ ] Calendar integration for meeting imports
- [ ] Multi-user support with roles
- [ ] Export to Notion/Obsidian
- [ ] Mobile-responsive PWA
- [ ] Push notifications for action items
- [ ] Voice input for meetings
- [ ] APK build for Android distribution
- [ ] Real-time Supabase subscriptions

---

## � Documentation

See the [docs/](docs/README.md) folder for comprehensive documentation:

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture/) | System design and infrastructure |
| [Guides](docs/guides/) | Deployment, testing, and quick start guides |
| [Migration](docs/migration/) | Database migration records and plans |
| [Reference](docs/reference/) | Best practices and API references |

---

## �📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- AI powered by [OpenAI](https://openai.com/)
- Icons from [Heroicons](https://heroicons.com/)
- Styled with [Tailwind CSS](https://tailwindcss.com/)

---

<p align="center">
  <strong>SignalFlow</strong> — Transform meetings into action
  <br>
  <sub>Built for focused, offline-first sprint workflows</sub>
</p>
