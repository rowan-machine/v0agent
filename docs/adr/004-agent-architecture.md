# ADR-004: Multi-Agent Architecture

## Status

Accepted

## Date

2026-01-22

## Context

SignalFlow uses AI for multiple purposes:
- Meeting signal extraction
- Career coaching and feedback
- DIKW synthesis and promotion
- General Q&A (Arjuna assistant)
- Smart suggestions

Initially, all AI calls were inline `ask_llm()` calls with hardcoded prompts. This led to:

1. **Code duplication**: Similar prompts scattered across endpoints
2. **No specialization**: Same model used for all tasks
3. **Testing difficulty**: Hard to mock AI behavior
4. **Prompt drift**: Inconsistent prompt quality over time

## Decision

Implement a multi-agent architecture with specialized agents:

### Agent Registry

Central registry for agent discovery and instantiation:

```python
# src/app/agents/registry.py
class AgentRegistry:
    _agents: Dict[str, Type[BaseAgent]] = {}
    
    @classmethod
    def register(cls, name: str):
        def decorator(agent_class):
            cls._agents[name] = agent_class
            return agent_class
        return decorator
    
    @classmethod
    def get(cls, name: str) -> BaseAgent:
        return cls._agents[name]()
```

### Specialized Agents

| Agent | Purpose | Model |
|-------|---------|-------|
| `ArjunaAgent` | General Q&A, intent parsing | GPT-4 |
| `CareerCoachAgent` | Standup feedback, career guidance | Claude |
| `MeetingAnalyzerAgent` | Signal extraction from transcripts | GPT-4 |
| `DIKWSynthesizerAgent` | Knowledge synthesis, promotion | Claude |

### Base Agent Interface

```python
class BaseAgent(ABC):
    name: str
    description: str
    default_model: str
    
    @abstractmethod
    async def execute(self, task: str, context: Dict) -> AgentResponse:
        pass
    
    def get_prompt(self, template: str, **kwargs) -> str:
        # Load from prompts/{agent_name}/{template}.jinja2
        pass
```

### Prompt Templates

Each agent has Jinja2 templates in `prompts/agents/{agent_name}/`:

```
prompts/agents/
├── arjuna/
│   ├── system.jinja2
│   ├── parse_intent.jinja2
│   └── clarify_intent.jinja2
├── career_coach/
│   ├── analyze_standup.jinja2
│   └── suggest_standup.jinja2
└── meeting_analyzer/
    └── extract_signals.jinja2
```

### Adapter Pattern

Existing endpoints use adapters to call new agents:

```python
# In career.py endpoint
from app.agents.career_coach import CareerCoachAgent

async def analyze_standup_endpoint(standup: str):
    agent = CareerCoachAgent()
    result = await agent.analyze_standup(standup)
    return result
```

## Consequences

### Positive

- ✅ Clear separation of concerns - each agent has one job
- ✅ Model specialization - right model for right task
- ✅ Testable - agents can be mocked
- ✅ Maintainable prompts - templates in dedicated files
- ✅ Extensible - new agents easy to add
- ✅ Adapter pattern enables gradual migration

### Negative

- ⚠️ More files/indirection than inline calls
- ⚠️ Learning curve for understanding agent flows
- ⚠️ Potential for agent proliferation
- ⚠️ Need to manage prompt template versioning

### Neutral

- Model router can select model based on task type
- Guardrails can be added pre/post agent execution
- Metrics can track agent performance

## Alternatives Considered

### Alternative 1: Single Monolithic AI Service

**Pros**: Simple, one place for all AI logic
**Cons**: God class, hard to test, no specialization
**Decision**: Rejected - doesn't scale with complexity

### Alternative 2: LangChain Agents

**Pros**: Mature framework, tool use, memory built-in
**Cons**: Heavy dependency, opinionated, overkill for our needs
**Decision**: Rejected - prefer lightweight custom solution

### Alternative 3: Microservices for Each Agent

**Pros**: Independent scaling, language flexibility
**Cons**: Operational complexity, network latency, overkill
**Decision**: Rejected - premature optimization

## References

- [MULTI_AGENT_ARCHITECTURE.md](../../MULTI_AGENT_ARCHITECTURE.md)
- [REFACTORING_BEST_PRACTICES_ADVANCED.md](../../REFACTORING_BEST_PRACTICES_ADVANCED.md)
- Agent implementations in `src/app/agents/`
