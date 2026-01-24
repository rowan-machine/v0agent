# Comprehensive RAG, Hybrid Search, and Mindmap Integration Plan

## Problem Statement
1. Current mindmap API returns flat data (all nodes at one level) - hierarchy is lost
2. Mindmap data is not aggregated from all conversations
3. Not integrated with hybrid RAG for search accessibility
4. Summarization doesn't synthesize across all data

## Solution Architecture

### 1. Enhanced Mindmap Structure with Hierarchy

**New endpoints:**
- `/api/mindmap/data-hierarchical` - Returns full hierarchy with parent-child relationships
- `/api/mindmap/nodes-by-level/{level}` - Get nodes at specific hierarchy level
- `/api/mindmap/conversations` - Get mindmaps aggregated from all conversations
- `/api/mindmap/synthesize` - AI-generated synthesis of all mindmaps

**Data structure changes:**
```json
{
  "nodes": [
    {
      "id": "node_1",
      "title": "Main Topic",
      "level": 0,
      "parent_id": null,
      "children_ids": ["node_2", "node_3"],
      "conversation_id": "conv_123",
      "conversation_name": "Q1 Planning",
      "depth": 0
    },
    {
      "id": "node_2",
      "title": "Sub-topic",
      "level": 1,
      "parent_id": "node_1",
      "children_ids": [],
      "conversation_id": "conv_123",
      "depth": 1
    }
  ],
  "edges": [
    {"source": "node_1", "target": "node_2"}
  ]
}
```

### 2. Conversation Mindmap Aggregation

**New table: `conversation_mindmaps`**
```sql
CREATE TABLE conversation_mindmaps (
  id INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL,
  mindmap_data JSON NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
)
```

**Aggregation logic:**
- Store raw mindmap from each conversation
- Generate master synthesis periodically
- Track which conversations contributed to the synthesis

### 3. Hybrid RAG Integration

**Enhanced search functionality:**
- Index mindmap nodes with metadata (hierarchy level, conversation, timestamps)
- Include mindmap synthesis in search results
- Link search results back to conversation contexts

**New endpoints:**
- `/api/search/hybrid-with-mindmap` - Unified search combining text + mindmap structure
- `/api/chat/rag-context` - Get contextual RAG data for chat

### 4. Mindmap Synthesis

**New endpoints:**
- `/api/mindmap/synthesize` - Generate AI synthesis of all mindmaps
- `/api/mindmap/synthesis-history` - Track synthesis changes over time

**Synthesis triggers:**
- On mindmap creation/update in conversation
- On schedule (hourly or daily)
- Manual trigger via API

## Implementation Steps

### Phase 1: Database & Data Structure
1. Add `conversation_mindmaps` table
2. Add hierarchy tracking columns to existing mindmap data
3. Create synthesis storage table

### Phase 2: Mindmap API Enhancements
1. Update `/api/mindmap/data` to include hierarchy
2. Add `/api/mindmap/data-hierarchical` endpoint
3. Add `/api/mindmap/conversations` endpoint
4. Add `/api/mindmap/synthesize` endpoint

### Phase 3: Conversation Integration
1. Store mindmap data when conversation ends/updated
2. Trigger synthesis on mindmap storage
3. Create aggregation logic

### Phase 4: Search Integration
1. Index mindmap nodes in search
2. Create hybrid search endpoint
3. Update chat RAG to use mindmap data

### Phase 5: Chat Integration
1. Pass mindmap synthesis to chat context
2. Include mindmap nodes in RAG results
3. Link chat responses to mindmap nodes

## Files to Modify

### New Files
- `src/app/services/mindmap_synthesis.py` - Synthesis logic
- `src/app/models/mindmap.py` - Mindmap data models

### Modified Files
- `src/app/db.py` - Add new tables
- `src/app/main.py` - Update mindmap endpoints
- `src/app/api/search.py` - Hybrid search with mindmap
- `src/app/api/chat.py` - Include mindmap in RAG
- `src/app/conversations.py` - Store mindmap on conversation events

## Data Flow

```
[Conversation] 
    ↓ (mindmap created/updated)
[Store raw mindmap] → [conversation_mindmaps table]
    ↓ (trigger synthesis)
[Aggregate all mindmaps] → [Generate AI synthesis]
    ↓ (store synthesis)
[mindmap_syntheses table]
    ↓ (index for search)
[Hybrid search index]
    ↓ (available in chat)
[Chat RAG context]
    ↓ (retrieve in chat responses)
[AI responses with mindmap context]
```

## Key Features

✅ Preserve hierarchy (parent-child relationships)
✅ Track conversation sources
✅ Aggregate across all data
✅ Synthesize with AI
✅ Index for search
✅ Include in chat RAG
✅ Real-time synthesis updates
✅ Historical tracking
