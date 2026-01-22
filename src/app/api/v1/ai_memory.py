# src/app/api/v1/ai_memory.py
"""
AI Memory Integration API

Provides endpoints for storing, retrieving, and managing AI memories
that provide context for future conversations and learning.

Key features:
1. Store approved AI responses as memories
2. Retrieve relevant memories for context injection
3. Manage memory lifecycle (approve, archive, reject)
4. Semantic search over memories
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

from ...db import connect
from ...memory.embed import embed_text, EMBED_MODEL
from ...memory.vector_store import upsert_embedding, semantic_search

router = APIRouter()


# ============== Pydantic Models ==============

class MemoryCreate(BaseModel):
    """Create a new AI memory."""
    source_type: Literal["quick_ask", "chat", "summary"] = Field(
        ..., description="Origin of the memory"
    )
    source_query: Optional[str] = Field(None, description="Original question/topic")
    content: str = Field(..., description="AI response content to store")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    importance: int = Field(default=5, ge=1, le=10, description="Importance for retrieval (1-10)")


class MemoryUpdate(BaseModel):
    """Update an existing memory."""
    content: Optional[str] = None
    status: Optional[Literal["approved", "rejected", "archived"]] = None
    tags: Optional[str] = None
    importance: Optional[int] = Field(None, ge=1, le=10)


class MemoryResponse(BaseModel):
    """Response for memory operations."""
    id: int
    source_type: str
    source_query: Optional[str]
    content: str
    status: str
    tags: Optional[str]
    importance: int
    created_at: str
    updated_at: str


class MemorySearchResult(BaseModel):
    """Memory with semantic similarity score."""
    id: int
    source_type: str
    source_query: Optional[str]
    content: str
    tags: Optional[str]
    importance: int
    similarity_score: float


class MemoryContext(BaseModel):
    """Formatted context for LLM injection."""
    memories: List[str]
    total_tokens_estimate: int
    memory_count: int


# ============== Endpoints ==============

@router.post("/memories", response_model=MemoryResponse, status_code=201)
async def create_memory(memory: MemoryCreate):
    """
    Store a new AI memory for future context retrieval.
    
    Memories are automatically embedded for semantic search.
    High-importance memories (7+) are prioritized in context retrieval.
    """
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO ai_memory (source_type, source_query, content, tags, importance)
            VALUES (?, ?, ?, ?, ?)
            """,
            (memory.source_type, memory.source_query, memory.content,
             memory.tags, memory.importance)
        )
        memory_id = cursor.lastrowid
        
        # Create embedding for semantic search
        text_for_embedding = f"{memory.source_query or ''}\n{memory.content}"
        vector = embed_text(text_for_embedding)
        upsert_embedding("ai_memory", memory_id, EMBED_MODEL, vector)
        
        # Fetch the created record
        row = conn.execute(
            "SELECT * FROM ai_memory WHERE id = ?",
            (memory_id,)
        ).fetchone()
    
    return MemoryResponse(**dict(row))


@router.get("/memories", response_model=List[MemoryResponse])
async def list_memories(
    status: Optional[str] = Query("approved", description="Filter by status"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    min_importance: int = Query(1, ge=1, le=10),
    limit: int = Query(50, ge=1, le=200),
):
    """List memories with optional filtering."""
    with connect() as conn:
        query = "SELECT * FROM ai_memory WHERE importance >= ?"
        params = [min_importance]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)
        
        query += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, tuple(params)).fetchall()
    
    return [MemoryResponse(**dict(row)) for row in rows]


@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: int):
    """Get a specific memory by ID."""
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ai_memory WHERE id = ?",
            (memory_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return MemoryResponse(**dict(row))


@router.put("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(memory_id: int, memory: MemoryUpdate):
    """
    Update an existing memory.
    
    Use this to:
    - Approve or reject memories
    - Archive old memories
    - Update content or importance
    """
    with connect() as conn:
        # Check if memory exists
        existing = conn.execute(
            "SELECT id FROM ai_memory WHERE id = ?",
            (memory_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        # Build dynamic update
        updates = ["updated_at = datetime('now')"]
        params = []
        
        if memory.content is not None:
            updates.append("content = ?")
            params.append(memory.content)
        if memory.status is not None:
            updates.append("status = ?")
            params.append(memory.status)
        if memory.tags is not None:
            updates.append("tags = ?")
            params.append(memory.tags)
        if memory.importance is not None:
            updates.append("importance = ?")
            params.append(memory.importance)
        
        query = f"UPDATE ai_memory SET {', '.join(updates)} WHERE id = ?"
        params.append(memory_id)
        conn.execute(query, tuple(params))
        
        # Re-embed if content changed
        if memory.content:
            row = conn.execute(
                "SELECT source_query, content FROM ai_memory WHERE id = ?",
                (memory_id,)
            ).fetchone()
            text_for_embedding = f"{row['source_query'] or ''}\n{row['content']}"
            vector = embed_text(text_for_embedding)
            upsert_embedding("ai_memory", memory_id, EMBED_MODEL, vector)
        
        # Fetch updated record
        row = conn.execute(
            "SELECT * FROM ai_memory WHERE id = ?",
            (memory_id,)
        ).fetchone()
    
    return MemoryResponse(**dict(row))


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: int):
    """Delete a memory (soft delete by setting status to 'rejected')."""
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM ai_memory WHERE id = ?",
            (memory_id,)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        conn.execute(
            "UPDATE ai_memory SET status = 'rejected', updated_at = datetime('now') WHERE id = ?",
            (memory_id,)
        )
    
    return None


@router.get("/memories/search", response_model=List[MemorySearchResult])
async def search_memories(
    query: str = Query(..., description="Search query"),
    top_k: int = Query(10, ge=1, le=50, description="Number of results"),
    min_similarity: float = Query(0.3, ge=0, le=1, description="Minimum similarity threshold"),
):
    """
    Semantic search over memories.
    
    Uses embeddings to find memories most relevant to the query.
    Only returns approved memories above the similarity threshold.
    """
    # Get query embedding
    query_vector = embed_text(query)
    
    # Search for similar memories
    results = semantic_search(
        query_vector=query_vector,
        ref_type="ai_memory",
        top_k=top_k * 2,  # Get more to filter
        min_similarity=min_similarity
    )
    
    # Fetch memory details for matched IDs
    if not results:
        return []
    
    with connect() as conn:
        memory_ids = [r["ref_id"] for r in results]
        placeholders = ",".join("?" * len(memory_ids))
        
        rows = conn.execute(
            f"""
            SELECT * FROM ai_memory 
            WHERE id IN ({placeholders}) AND status = 'approved'
            """,
            tuple(memory_ids)
        ).fetchall()
    
    # Merge with similarity scores
    memory_map = {row["id"]: dict(row) for row in rows}
    search_results = []
    
    for r in results:
        if r["ref_id"] in memory_map:
            mem = memory_map[r["ref_id"]]
            search_results.append(MemorySearchResult(
                id=mem["id"],
                source_type=mem["source_type"],
                source_query=mem["source_query"],
                content=mem["content"],
                tags=mem["tags"],
                importance=mem["importance"],
                similarity_score=r["similarity"]
            ))
    
    return search_results[:top_k]


@router.get("/memories/context", response_model=MemoryContext)
async def get_memory_context(
    query: str = Query(..., description="Current conversation context"),
    max_memories: int = Query(5, ge=1, le=20),
    max_tokens: int = Query(2000, ge=100, le=8000),
    include_high_importance: bool = Query(True, description="Always include importance 8+ memories"),
):
    """
    Get formatted memory context for LLM injection.
    
    This endpoint is designed for chat systems that need to inject
    relevant memories into the conversation context.
    
    Returns formatted memories ready for system prompt injection:
    - Prioritizes high-importance memories
    - Semantic search for relevance
    - Respects token budget
    """
    memories_to_include = []
    tokens_used = 0
    
    with connect() as conn:
        # First, always include high-importance memories (8+)
        if include_high_importance:
            high_importance = conn.execute(
                """
                SELECT * FROM ai_memory 
                WHERE status = 'approved' AND importance >= 8
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (max_memories,)
            ).fetchall()
            
            for row in high_importance:
                content = row["content"]
                estimated_tokens = len(content) // 4  # Rough estimate
                
                if tokens_used + estimated_tokens <= max_tokens:
                    memories_to_include.append(dict(row))
                    tokens_used += estimated_tokens
    
    # Then, add semantically relevant memories
    remaining_slots = max_memories - len(memories_to_include)
    remaining_tokens = max_tokens - tokens_used
    
    if remaining_slots > 0 and remaining_tokens > 100:
        search_results = await search_memories(
            query=query,
            top_k=remaining_slots * 2,
            min_similarity=0.4
        )
        
        existing_ids = {m["id"] for m in memories_to_include}
        
        for result in search_results:
            if result.id in existing_ids:
                continue
            
            estimated_tokens = len(result.content) // 4
            if tokens_used + estimated_tokens <= max_tokens:
                memories_to_include.append({
                    "id": result.id,
                    "source_type": result.source_type,
                    "source_query": result.source_query,
                    "content": result.content,
                    "importance": result.importance,
                    "similarity_score": result.similarity_score
                })
                tokens_used += estimated_tokens
                
                if len(memories_to_include) >= max_memories:
                    break
    
    # Format for LLM context
    formatted_memories = []
    for mem in memories_to_include:
        source = mem.get("source_query", "")
        content = mem["content"]
        
        if source:
            formatted_memories.append(f"[Q: {source}]\n{content}")
        else:
            formatted_memories.append(content)
    
    return MemoryContext(
        memories=formatted_memories,
        total_tokens_estimate=tokens_used,
        memory_count=len(memories_to_include)
    )


@router.post("/memories/from-chat")
async def save_chat_as_memory(
    query: str = Query(..., description="The user's question"),
    response: str = Query(..., description="The AI's response"),
    importance: int = Query(5, ge=1, le=10),
    tags: Optional[str] = Query(None),
):
    """
    Quick endpoint to save a chat exchange as a memory.
    
    Convenience wrapper around create_memory for chat interfaces.
    """
    memory = MemoryCreate(
        source_type="chat",
        source_query=query,
        content=response,
        tags=tags,
        importance=importance
    )
    
    return await create_memory(memory)


@router.get("/memories/stats")
async def get_memory_stats():
    """Get statistics about stored memories."""
    with connect() as conn:
        stats = conn.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN status = 'archived' THEN 1 ELSE 0 END) as archived,
                AVG(importance) as avg_importance
            FROM ai_memory
            """
        ).fetchone()
        
        by_source = conn.execute(
            """
            SELECT source_type, COUNT(*) as count
            FROM ai_memory
            WHERE status = 'approved'
            GROUP BY source_type
            """
        ).fetchall()
    
    return {
        "total": stats["total"] or 0,
        "by_status": {
            "approved": stats["approved"] or 0,
            "rejected": stats["rejected"] or 0,
            "archived": stats["archived"] or 0
        },
        "avg_importance": round(stats["avg_importance"] or 0, 2),
        "by_source": {row["source_type"]: row["count"] for row in by_source}
    }
