# Mindmap-RAG Quick Reference Guide

## New API Endpoints

### Mindmap Data & Hierarchy

#### 1. Get Enhanced Mindmap Data (with hierarchical info)
```bash
GET /api/mindmap/data
```
Returns DIKW pyramid + hierarchical mindmaps from conversations

**Response:**
```json
{
  "tree": {...},
  "nodes": [...],
  "links": [...],
  "hierarchicalMindmaps": [
    {
      "id": 1,
      "conversation_id": 5,
      "hierarchy_levels": 3,
      "node_count": 15,
      "root_node_id": "node_123",
      "nodes": [...],
      "edges": [...]
    }
  ],
  "counts": {
    "hierarchical_mindmaps": 5,
    "total_mindmap_nodes": 127
  }
}
```

#### 2. Get Full Hierarchical Mindmaps (all details)
```bash
GET /api/mindmap/data-hierarchical
```
Returns all mindmaps with complete hierarchy information

**Response:**
```json
{
  "mindmaps": [
    {
      "id": 1,
      "conversation_id": 5,
      "nodes": [
        {
          "id": "node_1",
          "title": "Project Planning",
          "level": 0,
          "parent_id": null,
          "children_ids": ["node_2", "node_3"],
          "conversation_id": 5,
          "mindmap_id": 1
        }
      ],
      "hierarchy": {
        "levels": 3,
        "max_depth": 2,
        "nodes_by_level": {
          "0": ["node_1"],
          "1": ["node_2", "node_3"],
          "2": ["node_4"]
        }
      }
    }
  ],
  "summary": {
    "total_mindmaps": 5,
    "total_nodes": 127,
    "total_edges": 142
  }
}
```

#### 3. Get Nodes at Specific Hierarchy Level
```bash
GET /api/mindmap/nodes-by-level/{level}
```

**Example:**
```bash
GET /api/mindmap/nodes-by-level/1
```

**Response:**
```json
{
  "level": 1,
  "nodes": [
    {
      "id": "node_2",
      "title": "Team Structure",
      "level": 1,
      "parent_id": "node_1",
      "conversation_id": 5,
      "mindmap_id": 1
    }
  ],
  "count": 12
}
```

#### 4. Get Conversation Mindmaps (aggregated)
```bash
GET /api/mindmap/conversations
```

**Response:**
```json
{
  "conversations": [
    {
      "conversation_id": 5,
      "title": "Project Kickoff",
      "created_at": "2024-01-15T10:00:00",
      "mindmap_count": 3,
      "mindmap_ids": [1, 2, 3],
      "statistics": {
        "total_nodes": 45,
        "avg_depth": 2.1,
        "levels_distribution": {0: 3, 1: 20, 2: 15, 3: 7}
      }
    }
  ],
  "total_conversations": 5,
  "summary": {
    "total_mindmaps": 15,
    "total_nodes": 127,
    "avg_depth": 2.3,
    "conversation_count": 5
  }
}
```

---

### Synthesis & Knowledge Aggregation

#### 5. Generate Mindmap Synthesis (AI-powered)
```bash
POST /api/mindmap/synthesize?force=true
```

**Query Parameters:**
- `force` (optional): `true` to regenerate even if recent synthesis exists

**Response:**
```json
{
  "success": true,
  "synthesis_id": 42,
  "synthesis_text": "Knowledge synthesis aggregating themes from all conversations including project planning, team structures, and decision tracking. Key patterns include...",
  "source_mindmaps": 15,
  "source_conversations": 5,
  "key_topics": ["Project Planning", "Team Structure", "Decision Tracking", ...],
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

#### 6. Get Current Synthesis (without regenerating)
```bash
GET /api/mindmap/synthesis
```

**Response:**
```json
{
  "success": true,
  "synthesis": {
    "id": 42,
    "synthesis_text": "...",
    "hierarchy_summary": {...},
    "key_topics": [...],
    "relationships": [...],
    "source_mindmap_ids": [...],
    "source_conversation_ids": [...],
    "created_at": "...",
    "updated_at": "..."
  }
}
```

---

### Search Integration

#### 7. Search Mindmap Nodes Only
```bash
POST /api/search/mindmap
Content-Type: application/json

{
  "query": "team structure",
  "match_count": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "mindmap_node_node_2",
      "type": "mindmap",
      "title": "Team Structure",
      "snippet": "Organizational hierarchy with roles and responsibilities...",
      "score": 1.0
    }
  ],
  "query": "team structure",
  "total_results": 5,
  "search_type": "mindmap"
}
```

#### 8. Hybrid Search (Documents + Meetings + Mindmaps)
```bash
POST /api/search/hybrid-with-mindmap
Content-Type: application/json

{
  "query": "project planning decisions",
  "match_count": 15
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "doc_123",
      "type": "document",
      "title": "Project Charter",
      "snippet": "Project objectives and scope...",
      "score": 0.95
    },
    {
      "id": "mindmap_node_node_1",
      "type": "mindmap",
      "title": "Project Planning",
      "snippet": "Strategic planning for Q1 initiatives...",
      "score": 0.88
    },
    {
      "id": "meeting_456",
      "type": "meeting",
      "title": "Kickoff Meeting",
      "snippet": "Team aligned on project goals...",
      "score": 0.85
    }
  ],
  "query": "project planning decisions",
  "total_results": 12,
  "search_type": "hybrid_with_mindmap"
}
```

---

## Usage in Chat

The mindmap synthesis is automatically included in chat RAG context:

```python
# In src/app/chat/context.py - build_context() now includes:
# 1. Conversation messages
# 2. Memory blocks (documents, meetings, signals)
# 3. **NEW**: Mindmap synthesis with key topics
```

Chat queries automatically have access to:
- Aggregated knowledge from all conversation mindmaps
- Key topics extracted by AI
- Relationships and themes identified across conversations

---

## Example Use Cases

### Use Case 1: Find all first-level topics across mindmaps
```bash
GET /api/mindmap/nodes-by-level/0
```

### Use Case 2: Search for decision-related topics
```bash
POST /api/search/hybrid-with-mindmap
{
  "query": "decisions made in sprints",
  "match_count": 20
}
```

### Use Case 3: Get full synthesis for knowledge management
```bash
GET /api/mindmap/synthesis
```
Then display synthesis text to user for high-level understanding.

### Use Case 4: Chat query with mindmap knowledge
```
User: "What are the key themes across all our conversations?"
AI has access to: mindmap synthesis + documents + meetings
Response draws from all sources with hierarchy context.
```

### Use Case 5: Analyze hierarchy depth
```bash
GET /api/mindmap/conversations
```
Response includes `levels_distribution` showing structure across all mindmaps.

---

## Integration Points

### For Frontend/UI:
1. Display hierarchical mindmaps from `/api/mindmap/data-hierarchical`
2. Show synthesis summary from `/api/mindmap/synthesis`
3. Include mindmap results in search UI from `/api/search/hybrid-with-mindmap`
4. Allow filtering by hierarchy level using `/api/mindmap/nodes-by-level/{level}`

### For Chat Systems:
1. `build_context()` automatically includes synthesis
2. No additional code needed - synthesis flows into LLM context
3. Key topics available for better recommendations

### For Search Systems:
1. Use `/api/search/hybrid-with-mindmap` for unified search
2. Results include type indicator (document, meeting, mindmap)
3. Mindmap nodes include hierarchy context (parent_id, level)

---

## Database Tables (Reference)

### conversation_mindmaps
- Stores raw mindmap JSON with hierarchy info
- Fields: `id, conversation_id, mindmap_json, hierarchy_levels, root_node_id, node_count, created_at, updated_at`

### mindmap_syntheses
- Stores AI-generated synthesis
- Fields: `id, synthesis_text, hierarchy_summary, source_mindmap_ids, source_conversation_ids, key_topics, relationships, created_at, updated_at`

### mindmap_synthesis_history
- Tracks changes to syntheses
- Fields: `id, synthesis_id, previous_text, changes_summary, triggered_by, created_at`

---

## Common Questions

**Q: How often is the synthesis updated?**
A: Generated on demand (via POST `/api/mindmap/synthesize`), or automatically when mindmaps are stored. Cached for 1 hour to avoid redundant generation. Use `?force=true` to regenerate immediately.

**Q: Are hierarchy relationships preserved?**
A: Yes! Parent-child relationships and hierarchy levels are preserved in storage and returned by all endpoints.

**Q: Can I search across all data types?**
A: Yes! Use `/api/search/hybrid-with-mindmap` to search documents, meetings, AND mindmap nodes in one query.

**Q: Do chat queries include mindmap knowledge?**
A: Yes! The synthesis is automatically included in `build_context()` for all chat sessions.

**Q: How is the synthesis generated?**
A: Using GPT-4, aggregating all mindmaps and using AI to create coherent knowledge synthesis.

**Q: Can I filter by hierarchy level?**
A: Yes! Use `/api/mindmap/nodes-by-level/{level}` to get nodes at specific depths.

---

## Performance Notes

- Synthesis is cached for 1 hour (use `?force=true` to regenerate)
- All endpoints have efficient database indexes
- Hierarchy extraction is calculated on-demand
- Search results are limited and paginated
- Mindmap JSON stored as TEXT in SQLite for compatibility

---

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200`: Success
- `400`: Bad request (missing required params)
- `404`: Resource not found (e.g., no synthesis generated yet)
- `500`: Server error (check logs)

---

*Last Updated: 2024-01-15*
*Version: 1.0 - Initial Release*
