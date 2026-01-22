# ADR-005: Embedding & Semantic Search Strategy

## Status

Accepted

## Date

2026-01-22

## Context

SignalFlow stores diverse content types: meetings, documents, tickets, DIKW items. Users need to find relevant information across all types using natural language queries. Traditional keyword search is insufficient because:

1. **Vocabulary mismatch**: Users search "database" but content says "PostgreSQL"
2. **Conceptual search**: "architecture decisions" should find related discussions
3. **Cross-type discovery**: A search should surface related meetings AND documents
4. **Knowledge graph**: Similar items should be automatically linked

## Decision

Implement a hybrid search strategy combining keyword and semantic search:

### Embedding Model

**Model**: OpenAI `text-embedding-3-small`
- **Dimensions**: 1536
- **Cost**: $0.02 per 1M tokens
- **Quality**: Excellent for our use cases
- **Latency**: ~100ms per embedding

### Storage: pgvector

Store embeddings directly in Supabase PostgreSQL using pgvector:

```sql
CREATE TABLE embeddings (
  id UUID PRIMARY KEY,
  ref_type TEXT NOT NULL,  -- 'meeting', 'document', 'ticket', 'dikw'
  ref_id UUID NOT NULL,
  embedding VECTOR(1536),
  content_hash TEXT,  -- Detect when re-embedding needed
  UNIQUE(ref_type, ref_id)
);

-- IVFFlat index for approximate nearest neighbor
CREATE INDEX idx_embeddings_vector ON embeddings 
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### Hybrid Search Flow

1. **Keyword Search**: PostgreSQL full-text search with `tsvector`
2. **Semantic Search**: pgvector cosine similarity
3. **Fusion**: Reciprocal Rank Fusion (RRF) to combine results

```python
async def hybrid_search(query: str, types: List[str] = None):
    # Get keyword results
    keyword_results = await keyword_search(query, types)
    
    # Get semantic results
    query_embedding = await get_embedding(query)
    semantic_results = await semantic_search(query_embedding, types)
    
    # Fuse with RRF
    return reciprocal_rank_fusion(keyword_results, semantic_results)
```

### Entity Linking

Embeddings power automatic entity linking in `entity_links`:

```python
async def auto_link_document(doc_id: str):
    # Get document embedding
    doc_embedding = await get_embedding_for_ref('document', doc_id)
    
    # Find similar entities
    similar = await find_similar(doc_embedding, threshold=0.7)
    
    # Create links
    for item in similar:
        await create_entity_link(
            source_type='document', source_id=doc_id,
            target_type=item.type, target_id=item.id,
            link_type='semantic_similar',
            similarity_score=item.score
        )
```

### Smart Suggestions

Embeddings enable contextual suggestions:

```python
async def get_smart_suggestions(context: str):
    context_embedding = await get_embedding(context)
    
    # Find similar past work
    similar_tickets = await search_embeddings('ticket', context_embedding, limit=3)
    similar_dikw = await search_embeddings('dikw', context_embedding, limit=3)
    
    return {
        'related_tickets': similar_tickets,
        'relevant_knowledge': similar_dikw
    }
```

## Consequences

### Positive

- ✅ Natural language search across all content
- ✅ Automatic knowledge graph via similarity
- ✅ Smart suggestions based on context
- ✅ Unified embedding storage in same database
- ✅ Hybrid search balances precision and recall
- ✅ Content hash prevents redundant re-embedding

### Negative

- ⚠️ Embedding costs for large document volumes
- ⚠️ Initial backfill can be slow
- ⚠️ IVFFlat index needs tuning for optimal recall
- ⚠️ Embedding model updates require re-embedding

### Neutral

- Embeddings generated on insert/update
- Background job for bulk backfill
- Similarity threshold configurable per use case

## Alternatives Considered

### Alternative 1: Dedicated Vector Database (Pinecone/Weaviate)

**Pros**: Optimized for vectors, managed service
**Cons**: Another service to manage, data sync complexity, cost
**Decision**: Rejected - pgvector sufficient, keeps data unified

### Alternative 2: ChromaDB (Local)

**Pros**: Simple, local, good DX
**Cons**: Not cloud-native, separate from main database
**Decision**: Used during development, migrated to pgvector for production

### Alternative 3: Elasticsearch with dense_vector

**Pros**: Mature, combined keyword + vector
**Cons**: Complex ops, expensive, overkill
**Decision**: Rejected - PostgreSQL + pgvector simpler

## References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Reciprocal Rank Fusion](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- `src/app/search.py` - Hybrid search implementation
- `src/app/api/knowledge_graph.py` - Entity linking
