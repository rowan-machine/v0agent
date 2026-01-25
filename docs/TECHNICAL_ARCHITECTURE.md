# SignalFlow Technical Architecture Documentation

> **Version**: 2.0 | **Last Updated**: January 2026  
> **Status**: Production (Railway Deployment)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Infrastructure Layer](#infrastructure-layer)
3. [Agent Architecture](#agent-architecture)
4. [Domain Models](#domain-models)
5. [Signal Extraction Pipeline](#signal-extraction-pipeline)
6. [DIKW Knowledge Management](#dikw-knowledge-management)
7. [Search and Query System](#search-and-query-system)
8. [Workflow Modes](#workflow-modes)
9. [Career Development System](#career-development-system)
10. [Tickets and Test Plans](#tickets-and-test-plans)
11. [MCP Tools and Commands](#mcp-tools-and-commands)
12. [Data Flow Architecture](#data-flow-architecture)

---

## System Overview

SignalFlow is a meeting intelligence and career development platform built with:

- **Backend**: Python 3.11 + FastAPI
- **Primary Database**: Supabase (PostgreSQL with pgvector)
- **Secondary Database**: SQLite (local-first, dual-write for backward compatibility)
- **Templates**: Jinja2 + Tailwind CSS
- **LLM Integration**: OpenAI (GPT-4o, GPT-4o-mini) + Anthropic (Claude Sonnet/Opus)
- **Vector Store**: ChromaDB (in-process) + Supabase pgvector (cloud)
- **Deployment**: Railway (production), Docker (local)

### Core Architecture Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
├─────────────────────────────────────────────────────────────────┤
│  Agents Layer          │  Services Layer      │  API Layer       │
│  ├── Arjuna           │  ├── agent_bus       │  ├── /meetings    │
│  ├── MeetingAnalyzer  │  ├── embeddings      │  ├── /tickets     │
│  ├── DIKWSynthesizer  │  ├── signal_learning │  ├── /signals     │
│  ├── CareerCoach      │  ├── background_jobs │  ├── /query       │
│  └── TicketAgent      │  └── scheduler       │  └── /career      │
├─────────────────────────────────────────────────────────────────┤
│  Repositories (Ports)           │  Infrastructure (Adapters)     │
│  ├── BaseRepository<T>          │  ├── SupabaseClient            │
│  ├── MeetingsRepository         │  ├── SQLite Connection         │
│  ├── DocumentsRepository        │  ├── ChromaDB Client           │
│  └── TicketsRepository          │  └── Rate Limiter              │
├─────────────────────────────────────────────────────────────────┤
│  Supabase (PostgreSQL + pgvector)  │  SQLite (local fallback)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Infrastructure Layer

### Supabase Client

**Location**: `src/app/infrastructure/supabase_client.py`

```python
class SupabaseSync:
    """
    Utilities for syncing data between SQLite and Supabase.
    
    Methods:
        - sync_meeting(meeting: Dict) -> Optional[str]
        - sync_document(doc: Dict, meeting_uuid: str) -> Optional[str]
        - sync_embedding(ref_type: str, ref_id: str, vector: List[float]) -> bool
    """
```

**Key Functions**:
- `get_supabase_client()`: Singleton client factory
- `SupabaseSync.sync_meeting()`: Sync meeting with schema mapping
- `SupabaseSync.sync_document()`: Sync document with meeting linkage

### Database Schema (28 Tables)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `meetings` | Meeting records | `meeting_name`, `synthesized_notes`, `signals` (JSONB), `raw_text` |
| `documents` | Knowledge documents | `source`, `content`, `meeting_id` (FK) |
| `tickets` | Sprint work items | `ticket_id`, `status`, `priority`, `ai_summary` |
| `test_plans` | QA tracking | `test_plan_id`, `acceptance_criteria`, `task_decomposition` |
| `dikw` | Knowledge pyramid items | `level`, `content`, `summary`, `parent_id` |
| `signals` | Extracted meeting signals | `signal_type`, `content`, `meeting_id`, `confidence` |
| `workflow_modes` | 7 workflow stages | `mode_key`, `steps_json`, `sort_order` |
| `accountability` | Waiting-for items | `description`, `responsible_party`, `status` |
| `standups` | Daily updates | `content`, `sentiment`, `standup_date` |
| `career_profile` | User career data | `current_role`, `target_role`, `strengths`, `goals` |
| `ai_memory` | Long-term AI context | `content`, `expires_at`, `confidence` |
| `embeddings` | Vector embeddings | `ref_type`, `ref_id`, `embedding` (vector) |

### Repository Pattern (Hexagonal Architecture)

**Location**: `src/app/repositories/base.py`

```python
class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository defining the PORT interface.
    Concrete implementations (adapters) provide actual behavior.
    
    Methods:
        - get_all(options: QueryOptions) -> List[T]
        - get_by_id(entity_id: str) -> Optional[T]
        - get_count(filters: Dict) -> int
        - create(entity: T) -> T
        - update(entity_id: str, data: Dict) -> Optional[T]
        - delete(entity_id: str) -> bool
    """

@dataclass
class QueryOptions:
    """Query configuration for repository operations."""
    limit: int = 100
    offset: int = 0
    order_by: str = "created_at"
    order_desc: bool = True
    filters: Dict[str, Any] = field(default_factory=dict)
```

---

## Agent Architecture

### BaseAgent (Abstract Base Class)

**Location**: `src/app/agents/base.py`

```python
class BaseAgent(ABC):
    """
    Abstract base class for all SignalFlow agents.
    
    Features:
        - Configuration via AgentConfig
        - LLM interactions via ask_llm()
        - Model routing via ModelRouter
        - Guardrails for pre/post call hooks
        - LangSmith tracing integration
    
    Configuration:
        - name: Agent identifier
        - description: Agent purpose
        - primary_model: Default LLM model
        - fallback_model: Backup model
        - temperature: LLM temperature
        - tools: List of available tool names
        - enable_tracing: LangSmith toggle
    """
```

### Agent Registry

| Agent | Location | Primary Purpose | Data Access |
|-------|----------|-----------------|-------------|
| **Arjuna** | `agents/arjuna.py` | Primary conversational assistant | Full system context, all tables |
| **MeetingAnalyzer** | `agents/meeting_analyzer.py` | Signal extraction from meetings | Meetings, documents, signals |
| **DIKWSynthesizer** | `agents/dikw_synthesizer.py` | Knowledge pyramid management | DIKW table, signals |
| **CareerCoach** | `agents/career_coach.py` | Career development guidance | Career profile, standups, tickets |
| **TicketAgent** | `agents/ticket_agent.py` | Ticket summarization & planning | Tickets, sprint settings |

---

## Agent Descriptions

### 1. Arjuna Agent

**Location**: `src/app/agents/arjuna.py`  
**Prompt**: `prompts/agents/arjuna/system.jinja2`

```
You are **Arjuna** 🙏, a smart assistant for the SignalFlow productivity app.

## Your Personality
- Greet users with "Hare Krishna!" when appropriate
- Be warm, helpful, and proactive
- Make reasonable assumptions rather than asking too many questions
```

**Capabilities**:
- Natural language intent parsing
- Ticket creation/updates
- Navigation assistance
- Sprint management
- Accountability tracking
- Standup logging
- Focus recommendations
- MCP command routing

**Data Available**:
- Sprint settings (name, goal, dates)
- Ticket statistics and recent tickets
- Waiting-for items
- Today's standups
- Available models
- System pages directory

**Search Methods**:
- `query_data`: Structured data queries
- `semantic_search`: Vector-based semantic search
- `query_agent`: Route to specialized agents

---

### 2. Meeting Analyzer Agent

**Location**: `src/app/agents/meeting_analyzer.py`  
**Prompt**: `prompts/agents/meeting_analyzer/system.jinja2`

```
You are a meeting intelligence agent specializing in extracting actionable 
signals from meeting notes and transcripts.
```

**Capabilities**:
- Extract structured signals (decisions, actions, blockers, risks, ideas)
- Adaptive heading-based parsing for multiple formats (Teams, Pocket)
- Screenshot analysis with vision integration
- Multi-source transcript processing
- Semantic signal grouping and deduplication

**Signal Types Extracted**:

| Type | Keywords | Emoji | Initial DIKW Level |
|------|----------|-------|-------------------|
| Decision | decided, agreed, approved | ✅ | Information |
| Action Item | will, needs to, must, todo | 📋 | Data |
| Blocker | blocked, waiting on, can't proceed | 🚫 | Data |
| Risk | concern, might fail, uncertain | ⚠️ | Information |
| Idea | suggestion, what if, could we | 💡 | Data |
| Key Signal | insight, critical, main takeaway | 🔑 | Knowledge |

**Pocket Template Detection** (30+ templates):
- All-Hands Meeting
- Sprint Retrospective
- Sprint Planning
- 1:1 Meeting
- Technical Discussion
- Incident Review
- And 25+ more...

---

### 3. DIKW Synthesizer Agent

**Location**: `src/app/agents/dikw_synthesizer.py`  
**Prompt**: `prompts/agents/dikw_synthesizer/system.jinja2`

```
You are the DIKW Synthesizer, an AI knowledge architect that transforms 
raw signals into structured wisdom.
```

**DIKW Pyramid Levels**:

| Level | Description | Promotion Action |
|-------|-------------|------------------|
| **Data** | Raw facts, observations, signals without context | → Add context and meaning |
| **Information** | Contextualized data with structure | → Extract patterns and insights |
| **Knowledge** | Actionable insights and applied understanding | → Distill strategic principles |
| **Wisdom** | Strategic principles, timeless lessons | Terminal level |

**Capabilities**:
- Signal promotion through DIKW levels
- Multi-item synthesis and merging
- Confidence-based validation
- AI-assisted content refinement
- Tag generation and clustering
- Evolution tracking

**Promotion Prompts**:

```python
PROMOTION_PROMPTS = {
    'information': "Transform this raw data into structured information...",
    'knowledge': "Extract actionable knowledge from this information...",
    'wisdom': "Distill strategic wisdom from this knowledge..."
}
```

---

### 4. Career Coach Agent

**Location**: `src/app/agents/career_coach.py`  
**Prompt**: `prompts/agents/career_coach/system.jinja2`

```
You are a friendly, supportive career coach having a casual conversation 
with someone about their career journey. Think of yourself as a mentor 
they're catching up with over coffee.
```

**Capabilities**:
- Generate personalized growth suggestions
- Analyze standups with sentiment detection
- Provide career insights from skills/projects
- Conversational career coaching
- Connect work context to career goals

**Data Available**:
- Career profile (current role, target role, strengths, goals)
- Sprint information
- Active tickets (up to 10)
- Recent standups (up to 5, with sentiment)
- Code activity (up to 5 recent files)

**Career Repo Capabilities Exposed**:
- Meeting ingestion with signal extraction
- DIKW pyramid promotion
- Quick AI updates with per-item actions
- Accountability tracking
- Workflow mode tracking
- Career profile + AI-generated growth suggestions

---

### 5. Ticket Agent

**Location**: `src/app/agents/ticket_agent.py`

**Capabilities**:
- **Summary Generation**: Tag-aware, format-guided summaries
- **Implementation Planning**: Premium model (GPT-4o) for detailed plans
- **Task Decomposition**: Atomic subtasks with estimates

**Tag-Based Format Hints**:

| Tag | Effect |
|-----|--------|
| `brief`, `short` | 2-3 sentences max |
| `detailed`, `verbose` | Comprehensive coverage |
| `technical`, `tech` | Implementation focus |
| `business`, `stakeholder` | Business framing |
| `bullet`, `bullets` | Bullet point format |
| `checklist` | Checkbox format |

---

## Domain Models

### Meetings vs Documents

| Aspect | Meetings | Documents |
|--------|----------|-----------|
| **Purpose** | Meeting records with synthesis | Knowledge base content |
| **Key Fields** | `meeting_name`, `synthesized_notes`, `signals`, `raw_text` | `source`, `content`, `document_date` |
| **Signal Extraction** | Automatic on save | Manual/on-demand |
| **Transcript Storage** | `raw_text` with markers (`=== Pocket Transcript ===`) | Full content in `content` |
| **Linkage** | Parent record | Links to meetings via `meeting_id` |
| **Embedding** | Both notes and raw_text | Full content |

**Transcript Document Generation**:
Documents can be created from meeting transcripts (Pocket or Teams) via:
- API: `POST /api/meetings/{id}/generate-document`
- UI: "Generate Document" button in edit_meeting page

---

## Signal Extraction Pipeline

### Pipeline Flow

```
┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  Meeting Input   │───▶│  Parser Layer   │───▶│  Signal Extractor│
│  (Summary/Trans) │    │  (Adaptive)     │    │  (AI-Powered)    │
└──────────────────┘    └─────────────────┘    └──────────────────┘
                                                        │
                                                        ▼
                        ┌─────────────────┐    ┌──────────────────┐
                        │  Signal Store   │◀───│  Deduplication   │
                        │  (signals_json) │    │  (Semantic)      │
                        └─────────────────┘    └──────────────────┘
```

### Adaptive Heading Patterns

**Location**: `src/app/agents/meeting_analyzer.py`

```python
HEADING_PATTERNS = {
    "markdown_h1": r"^#\s+(.+)$",
    "markdown_h2": r"^##\s+(.+)$",
    "markdown_h3": r"^###\s+(.+)$",
    "bold": r"^\*\*(.+?)\*\*\s*:?\s*$",
    "colon": r"^([A-Za-z][A-Za-z\s/]+):\s*$",
    "emoji": r"^([\U0001F300-\U0001F9FF])\s*(.+)$",
}
```

### Heading to Signal Type Mapping

```python
HEADING_TO_SIGNAL_TYPE = {
    "decision": "decision", "decisions": "decision",
    "action items": "action_item", "tasks": "action_item", "next steps": "action_item",
    "blocker": "blocker", "blockers": "blocker", "impediments": "blocker",
    "risk": "risk", "risks": "risk", "concerns": "risk",
    "idea": "idea", "ideas": "idea", "suggestions": "idea",
}
```

### Signal Learning Service

**Location**: `src/app/services/signal_learning.py`

```python
class SignalLearningService:
    """
    Feedback-driven AI improvement for signal extraction.
    
    Feedback Loop:
    1. Collect feedback from user actions (approve, reject, archive)
    2. Analyze patterns in feedback data
    3. Generate learning hints for signal extraction
    4. Store learnings in ai_memory for context retrieval
    
    Methods:
        - get_feedback_summary(days: int) -> Dict[str, Any]
        - generate_learning_context() -> str
        - store_learning(signal_type: str, pattern: str) -> bool
    """
```

---

## DIKW Knowledge Management

### Level Descriptions

```python
DIKW_LEVEL_DESCRIPTIONS = {
    'data': "Raw facts, observations, and signals without context",
    'information': "Contextualized data with meaning and structure",
    'knowledge': "Actionable insights, patterns, and applied understanding",
    'wisdom': "Strategic principles, timeless lessons, and guiding truths"
}
```

### Promotion Rules

| Promotion | Validation Gate | AI Prompt Focus |
|-----------|----------------|-----------------|
| Data → Information | Context added | Explain meaning in context |
| Information → Knowledge | Pattern identified | Extract actionable insights |
| Knowledge → Wisdom | Strategic principle | Distill guiding truth |

### Synthesis Operations

**Single-Item Promotion**:
```python
async def promote_item(self, item_id: str) -> Dict[str, Any]:
    """Promote a single item to the next DIKW level."""
```

**Multi-Item Synthesis**:
```python
async def synthesize_items(self, item_ids: List[str]) -> Dict[str, Any]:
    """Merge multiple items into a higher-level insight."""
```

---

## Search and Query System

### Search Types

| Search Type | Location | Method | Data Sources |
|-------------|----------|--------|--------------|
| **Full-Text** | `search.py` | Keyword matching | Meetings, documents |
| **Semantic** | `chat/turn.py` | Vector similarity | Embeddings (ChromaDB/pgvector) |
| **Query** | `query.py` | LLM-powered Q&A | Combined context |

### Full-Text Search

**Location**: `src/app/search.py`

```python
def _search_documents_supabase(query: str, start_date: str, end_date: str, limit: int) -> list:
    """
    Search documents using Supabase.
    - Case-insensitive content/source matching
    - Date range filtering
    - Highlight match with <mark> tags
    """

def _search_meetings_supabase(query: str, include_transcripts: bool, start_date: str, end_date: str, limit: int) -> list:
    """
    Search meetings using Supabase.
    - Meeting name and notes search
    - Optional transcript search (raw_text)
    - Date filtering
    """
```

### Semantic Search Pipeline

**Location**: `src/app/chat/turn.py`

```python
def run_turn(question: str, source_type: str, start_date: str, end_date: str) -> Tuple[str, List[Dict]]:
    """
    Single-turn, stateless Q&A pipeline.
    
    Steps:
    1. Plan query (extract keywords, concepts, source preference)
    2. Lexical retrieval (keyword-based)
    3. Semantic search (vector similarity)
    4. Rank and merge results
    5. Build context for LLM
    6. Generate answer
    """
```

### Embedding Service

**Location**: `src/app/services/embeddings.py`

```python
class EmbeddingService:
    """
    Unified embedding service using ChromaDB.
    
    Collections:
        - meetings
        - documents
        - signals
        - dikw
        - tickets
        - career_memories
    
    Methods:
        - add_embedding(collection_name, doc_id, text, metadata)
        - search_similar(collection_name, query_text, limit)
        - delete_embedding(collection_name, doc_id)
    """
```

### Agent Search Capabilities

| Agent | Search Methods | Data Access |
|-------|---------------|-------------|
| **Arjuna** | `query_data`, `semantic_search`, `query_agent` | Full system |
| **MeetingAnalyzer** | Heading parsing, signal lookup | Meetings, linked docs |
| **DIKWSynthesizer** | DIKW item queries | DIKW table |
| **CareerCoach** | Profile, standups, tickets | Career-related tables |
| **TicketAgent** | Ticket queries | Tickets, sprint settings |

---

## Workflow Modes

### The 7 Workflow Stages

```sql
CREATE TABLE workflow_modes (
  mode_key TEXT NOT NULL UNIQUE,    -- e.g., 'mode-a', 'mode-b'
  name TEXT NOT NULL,               -- e.g., 'Context Distillation'
  icon TEXT DEFAULT '🎯',           -- emoji icon
  short_description TEXT,           -- brief summary
  description TEXT,                 -- detailed description
  steps_json TEXT,                  -- JSON array of checklist steps
  sort_order INTEGER DEFAULT 0,     -- display order
  is_active INTEGER DEFAULT 1       -- enabled/disabled
);
```

### Default Workflow Modes

| Mode | Name | Description |
|------|------|-------------|
| A | Context Distillation | Gathering and organizing context |
| B | Idea Capture | Collecting ideas and signals |
| C | Sprint Planning | Defining sprint goals and tickets |
| D | Deep Work | Focused execution time |
| E | Code Review | Review and feedback phase |
| F | Documentation | Writing docs and knowledge capture |
| G | Retrospective | Sprint review and learning |

### Workflow API

- `GET /api/workflow-mode`: Get current mode
- `POST /api/workflow-mode`: Set current mode
- `GET /api/workflow-modes`: List all modes
- `POST /api/workflow-modes`: Create/update mode
- `DELETE /api/workflow-modes/{mode_key}`: Delete mode

---

## Career Development System

### Career Profile Schema

```python
{
    "current_role": "Senior Data Engineer",
    "target_role": "Staff Engineer",
    "strengths": "Python, SQL, System Design",
    "weaknesses": "Public Speaking",
    "interests": "AI/ML, Platform Engineering",
    "goals": "Lead a team within 2 years"
}
```

### Standup Analysis

**Location**: `src/app/agents/career_coach.py`

```python
async def analyze_standup(self, standup_content: str) -> Dict[str, Any]:
    """
    Analyze a standup update.
    
    Returns:
        - sentiment: positive/neutral/negative
        - blockers_detected: List of identified blockers
        - accomplishments: List of achievements
        - recommendations: Suggested actions
    """
```

### Career Growth Suggestions

Generated based on:
- Career profile (current role, target role, goals)
- Recent standups (patterns, sentiment)
- Ticket history (completed work, areas of focus)
- Code activity (files modified, skills demonstrated)

---

## Tickets and Test Plans

### Ticket Schema

```sql
CREATE TABLE tickets (
  id INTEGER PRIMARY KEY,
  ticket_id TEXT NOT NULL UNIQUE,   -- e.g. JIRA-1234
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'backlog',    -- backlog, todo, in_progress, in_review, blocked, done
  priority TEXT,                     -- low, medium, high, critical
  sprint_points INTEGER DEFAULT 0,
  in_sprint INTEGER DEFAULT 1,
  requires_deployment INTEGER DEFAULT 0,
  ai_summary TEXT,                   -- AI-generated summary
  implementation_plan TEXT,          -- AI-generated plan
  tags TEXT                          -- comma-separated tags
);
```

### Test Plan Schema

```sql
CREATE TABLE test_plans (
  id INTEGER PRIMARY KEY,
  test_plan_id TEXT NOT NULL UNIQUE,  -- e.g. TP-ABC123
  title TEXT NOT NULL,
  description TEXT,
  acceptance_criteria TEXT,
  task_decomposition TEXT,            -- AI-generated tasks
  status TEXT DEFAULT 'draft',        -- draft, active, passed, failed
  priority TEXT DEFAULT 'medium',
  linked_ticket_id INTEGER,           -- FK to tickets
  tags TEXT
);
```

### AI Features for Tickets

| Feature | Endpoint | Model | Description |
|---------|----------|-------|-------------|
| Summary | `POST /tickets/{id}/generate-summary` | GPT-4o-mini | Tag-aware summary |
| Plan | `POST /tickets/{id}/generate-plan` | GPT-4o | Implementation plan |
| Decompose | `POST /tickets/{id}/generate-decomposition` | GPT-4o-mini | Atomic subtasks |

---

## MCP Tools and Commands

### MCP Short Notation

**Location**: `src/app/mcp/commands.py`

**Format**: `/command subcommand [args]` or `@agent command`

### Arjuna Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `/arjuna focus` | `/aj focus` | Get prioritized work recommendations |
| `/arjuna ticket <title>` | `/aj t "Fix auth bug"` | Create a new ticket |
| `/arjuna update <id>` | `/aj u AJ-123 --status done` | Update ticket |
| `/arjuna standup` | `/aj su` | Log standup |
| `/arjuna waiting` | `/aj w "Review from Sarah"` | Add accountability item |
| `/arjuna model` | `/aj m gpt-4o` | Change AI model |
| `/arjuna go <page>` | `/aj go tickets` | Navigate to page |

### Agent Routing Commands

| Command | Routes To | Description |
|---------|-----------|-------------|
| `/query` | Query system | Data queries |
| `/semantic` | Embedding search | Vector similarity search |
| `/career` | CareerCoach | Career-related queries |
| `/meeting` | MeetingAnalyzer | Meeting analysis |
| `/dikw` | DIKWSynthesizer | Knowledge promotion |

### Chain Commands (Multi-Step Automation)

| Chain | Description |
|-------|-------------|
| `/chain ticket-sprint` | Create ticket → Add to sprint |
| `/chain standup-feedback` | Log standup → Get feedback |
| `/chain ticket-plan-decompose` | Create ticket → Generate plan → Decompose |
| `/chain focus-execute` | Get focus → Start work |
| `/chain blocked-escalate` | Mark blocked → Notify |

### MCP Tools Registry

**Location**: `src/app/mcp/tools.py`

| Tool | Function | Description |
|------|----------|-------------|
| `store_meeting_synthesis` | Meeting storage | Save meeting with signal extraction |
| `store_doc` | Document storage | Save document with embedding |
| `query_memory` | Memory query | Q&A over documents/meetings |
| `load_meeting_bundle` | Bundle import | Import Pocket bundle |

---

## Agent Bus (Inter-Agent Communication)

**Location**: `src/app/services/agent_bus.py`

```python
class AgentBus:
    """
    Central message bus for agent communication.
    
    Message Types:
        - QUERY: Request information
        - TASK: Assign work
        - RESULT: Return results
        - NOTIFICATION: Broadcast info
        - STATUS: Status update
        - ERROR: Error notification
    
    Priority Levels:
        - LOW (1)
        - NORMAL (2)
        - HIGH (3)
        - CRITICAL (4)
    
    Usage:
        bus = AgentBus()
        msg = AgentMessage(
            source_agent="arjuna",
            target_agent="meeting_analyzer",
            message_type=MessageType.QUERY,
            content={"question": "Extract signals from meeting 123"}
        )
        bus.send(msg)
    """
```

---

## Model Router

**Location**: `src/app/agents/model_router.py`

### Task Type → Model Mapping

| Task Type | Default Model | Cost Tier | Latency Budget |
|-----------|---------------|-----------|----------------|
| classification | gpt-4o-mini | Low | 2000ms |
| routing | gpt-4o-mini | Low | 1500ms |
| parsing | gpt-4o-mini | Low | 2000ms |
| summarization | gpt-4o-mini | Standard | 5000ms |
| extraction | gpt-4o-mini | Standard | 5000ms |
| synthesis | gpt-4o | Premium | 10000ms |
| planning | gpt-4o | Premium | 15000ms |
| coaching | gpt-4o-mini | Standard | 8000ms |

### Selection Logic

```python
def select(task_type: str, agent_name: str = None, override: str = None) -> ModelSelectionResult:
    """
    Select the appropriate model for a task.
    
    Priority:
    1. User override (if provided)
    2. Agent-specific config
    3. Task type default
    4. Fallback chain
    """
```

---

## Data Flow Architecture

### Meeting Ingestion Flow

```
┌─────────────────┐
│  Meeting Input  │
│  (UI/MCP/API)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────┐
│  Text Cleaning  │───▶│  Parse Sections │
└─────────────────┘    └────────┬────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Extract Signals│    │  Generate       │    │  Create         │
│  (AI-Powered)   │    │  Embeddings     │    │  Transcript Doc │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │  Dual Write         │
                    │  Supabase + SQLite  │
                    └─────────────────────┘
```

### Query Flow

```
┌─────────────────┐
│  User Question  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Query Planner  │
│  (Extract Terms)│
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│Lexical│ │Semantic│
│Search │ │Search  │
└───┬───┘ └───┬───┘
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│  Rank & Merge   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Build Context  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Answer     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response +     │
│  Sources        │
└─────────────────┘
```

---

## Appendix: File Structure Reference

```
src/app/
├── agents/
│   ├── base.py              # BaseAgent, AgentConfig
│   ├── arjuna.py            # Primary assistant (2566 lines)
│   ├── career_coach.py      # Career development (836 lines)
│   ├── dikw_synthesizer.py  # Knowledge pyramid (1190 lines)
│   ├── meeting_analyzer.py  # Signal extraction (812 lines)
│   ├── ticket_agent.py      # Ticket AI (526 lines)
│   ├── model_router.py      # LLM model selection
│   └── guardrails.py        # Pre/post call hooks
├── services/
│   ├── agent_bus.py         # Inter-agent messaging
│   ├── embeddings.py        # ChromaDB integration
│   ├── signal_learning.py   # Feedback-driven learning
│   ├── meetings_supabase.py # Supabase meeting ops
│   └── documents_supabase.py# Supabase document ops
├── infrastructure/
│   ├── supabase_client.py   # Supabase connection
│   └── cache.py             # Caching layer
├── repositories/
│   ├── base.py              # Repository interface
│   ├── meetings.py          # Meeting repository
│   └── documents.py         # Document repository
├── mcp/
│   ├── tools.py             # MCP tool implementations
│   ├── commands.py          # Command definitions
│   └── parser.py            # Command parser
└── prompts/agents/
    ├── arjuna/system.jinja2
    ├── career_coach/system.jinja2
    ├── dikw_synthesizer/system.jinja2
    └── meeting_analyzer/system.jinja2
```

---

*Document generated: January 2026*  
*SignalFlow v2.0 - Railway Production Deployment*
