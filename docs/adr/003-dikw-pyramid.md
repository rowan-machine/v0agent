# ADR-003: DIKW Knowledge Hierarchy

## Status

Accepted

## Date

2026-01-22

## Context

SignalFlow extracts signals from meetings (decisions, actions, blockers, risks, ideas). These raw signals need to be transformed into actionable knowledge that grows over time. We needed a framework for:

1. **Signal organization**: Raw signals are noisy and need curation
2. **Knowledge synthesis**: Related signals should merge into higher-level insights
3. **Wisdom extraction**: Patterns across time should inform future decisions
4. **Confidence tracking**: Some insights are more validated than others

## Decision

Implement the DIKW (Data-Information-Knowledge-Wisdom) pyramid as the knowledge management framework:

### Hierarchy Levels

| Level | Description | Example |
|-------|-------------|---------|
| **Data** | Raw signals extracted from meetings | "Decision: Use PostgreSQL for the database" |
| **Information** | Contextualized, validated signals | "Team chose PostgreSQL for ACID compliance and JSON support" |
| **Knowledge** | Synthesized insights from multiple signals | "Database decisions prioritize data integrity over performance" |
| **Wisdom** | High-level patterns and principles | "Architecture decisions should favor proven technologies" |

### Schema Design

```sql
CREATE TABLE dikw_items (
  id UUID PRIMARY KEY,
  level TEXT CHECK (level IN ('data', 'information', 'knowledge', 'wisdom')),
  content TEXT NOT NULL,
  confidence REAL DEFAULT 0.5,  -- 0.0 to 1.0
  validation_count INTEGER DEFAULT 0,
  source_ref_ids UUID[],  -- Links to source items
  promoted_to UUID,  -- Link to promoted item
  tags TEXT[],
  status TEXT DEFAULT 'active'
);
```

### Promotion Flow

1. **Signal → Data**: Auto-created when signals are approved
2. **Data → Information**: AI summarization + user validation
3. **Information → Knowledge**: Cross-signal synthesis when themes emerge
4. **Knowledge → Wisdom**: Long-term pattern recognition

### Evolution Tracking

Every promotion/merge is tracked in `dikw_evolution`:

```sql
CREATE TABLE dikw_evolution (
  id UUID PRIMARY KEY,
  item_id UUID REFERENCES dikw_items(id),
  event_type TEXT,  -- 'created', 'promoted', 'merged', 'edited'
  from_level TEXT,
  to_level TEXT,
  content_snapshot TEXT,
  created_at TIMESTAMPTZ
);
```

## Consequences

### Positive

- ✅ Clear progression path for knowledge maturity
- ✅ Confidence scores enable prioritization
- ✅ Evolution history provides audit trail
- ✅ AI can assist at each promotion step
- ✅ Tags enable cross-cutting knowledge graphs
- ✅ Supports both manual and AI-driven synthesis

### Negative

- ⚠️ Complexity in determining when to promote
- ⚠️ Risk of knowledge stagnating at lower levels
- ⚠️ Requires user engagement to validate promotions
- ⚠️ AI synthesis quality varies

### Neutral

- Confidence scores adjust based on validation and time
- Merge operations combine source items into one
- Archived items preserved for historical queries

## Alternatives Considered

### Alternative 1: Flat Tag-Based Organization

**Pros**: Simple, flexible, familiar
**Cons**: No concept of knowledge maturity or synthesis
**Decision**: Rejected - doesn't support knowledge evolution

### Alternative 2: Wiki/Document-Based

**Pros**: Rich text, linking, familiar mental model
**Cons**: Doesn't fit signal-based input, manual synthesis only
**Decision**: Rejected - too manual, doesn't leverage AI

### Alternative 3: Graph-Only (Neo4j style)

**Pros**: Flexible relationships, powerful queries
**Cons**: No inherent hierarchy, harder to visualize progress
**Decision**: Partially adopted - entity_links provides graph layer on top

## References

- [DIKW Pyramid (Wikipedia)](https://en.wikipedia.org/wiki/DIKW_pyramid)
- [Knowledge Management Systems](https://www.sciencedirect.com/topics/computer-science/knowledge-management-system)
- DIKWSynthesizerAgent in `src/app/agents/dikw_synthesizer.py`
