# LangChain/LangGraph/LangSmith Evaluation Sandbox

**Phase 1 Checkpoint 8**: Evaluate LangChain ecosystem for router/guardrail hooks

## Purpose
Prototype the router/guardrail hooks against these libraries in isolation to validate fit; keep production path plain Python until stability is proven.

## Evaluation Criteria

### Model Router Integration
- [ ] Can LangChain's `ChatModel` wrap our existing OpenAI calls?
- [ ] Does `langchain_core.runnables` support our YAML policy-based routing?
- [ ] Latency overhead measurement (target: < 50ms added per call)
- [ ] Token counting compatibility with our budgets

### Guardrails Integration
- [ ] Can `langchain_core.output_parsers` replace our JSON parsing?
- [ ] Does LangGraph support our pre/post hook pattern?
- [ ] Safety chain composition (input filter → agent → output filter)
- [ ] Retry/fallback patterns with LangChain

### LangSmith Observability
- [ ] Tracing integration with existing logging
- [ ] Cost tracking per agent/task type
- [ ] Latency dashboards
- [ ] Prompt versioning support

### LangGraph Workflow
- [ ] Agent graph for multi-step flows
- [ ] State persistence compatibility with SQLite
- [ ] Human-in-the-loop checkpointing
- [ ] Error recovery patterns

## Test Scenarios

1. **Model Router Test**: Route a classification task to gpt-4o-mini, synthesis to claude-sonnet
2. **Guardrail Test**: Input filter → agent call → self-reflection → output
3. **Observability Test**: Trace a full agent conversation with LangSmith
4. **Workflow Test**: Multi-agent graph with Career Coach + Arjuna

## Dependencies (sandbox only)

```bash
pip install langchain langchain-core langchain-openai langgraph langsmith
```

## Decision Matrix

| Feature | LangChain Fit | Native Python Fit | Decision |
|---------|---------------|-------------------|----------|
| Model Router | TBD | Already working (YAML) | |
| Guardrails | TBD | Already working (hooks) | |
| Tracing | TBD | Basic logging exists | |
| Agent Graphs | TBD | Not implemented | |

## Conclusion
_To be filled after evaluation_
