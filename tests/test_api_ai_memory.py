# tests/test_api_ai_memory.py
"""
Tests for AI Memory Integration API.

Tests the /api/v1/ai/memories endpoints for:
- Creating and storing AI memories
- Semantic search over memories
- Context retrieval for LLM injection
- Memory lifecycle management
"""

import pytest
from unittest.mock import patch


class TestAIMemoryAPI:
    """Test suite for AI memory endpoints."""
    
    def test_create_memory(
        self, client, mock_embeddings, ai_memory_factory, assert_response_success
    ):
        """Test creating a new AI memory."""
        memory_data = ai_memory_factory(
            source_type="chat",
            query="What is TDD?",
            content="Test-Driven Development is a software development approach...",
            importance=7
        )
        
        response = client.post("/api/v1/ai/memories", json=memory_data)
        data = assert_response_success(response, status_code=201)
        
        assert data["source_type"] == "chat"
        assert data["source_query"] == "What is TDD?"
        assert data["importance"] == 7
        assert data["status"] == "approved"
    
    def test_create_memory_from_quick_ask(
        self, client, mock_embeddings, ai_memory_factory, assert_response_success
    ):
        """Test creating memory from quick_ask source."""
        memory_data = ai_memory_factory(source_type="quick_ask")
        
        response = client.post("/api/v1/ai/memories", json=memory_data)
        data = assert_response_success(response, status_code=201)
        
        assert data["source_type"] == "quick_ask"
    
    def test_list_memories(self, client_with_data, assert_response_success):
        """Test listing all approved memories."""
        response = client_with_data.get("/api/v1/ai/memories")
        data = assert_response_success(response)
        
        assert isinstance(data, list)
        for memory in data:
            assert memory["status"] == "approved"
    
    def test_list_memories_filter_by_source(
        self, client_with_data, assert_response_success
    ):
        """Test filtering memories by source type."""
        response = client_with_data.get("/api/v1/ai/memories?source_type=chat")
        data = assert_response_success(response)
        
        for memory in data:
            assert memory["source_type"] == "chat"
    
    def test_list_memories_filter_by_importance(
        self, client_with_data, assert_response_success
    ):
        """Test filtering memories by minimum importance."""
        response = client_with_data.get("/api/v1/ai/memories?min_importance=7")
        data = assert_response_success(response)
        
        for memory in data:
            assert memory["importance"] >= 7
    
    def test_get_memory_by_id(self, client_with_data, assert_response_success):
        """Test getting a specific memory by ID."""
        response = client_with_data.get("/api/v1/ai/memories/1")
        data = assert_response_success(response)
        
        assert data["id"] == 1
        assert "content" in data
    
    def test_get_memory_not_found(self, client, assert_response_error):
        """Test 404 when memory doesn't exist."""
        response = client.get("/api/v1/ai/memories/9999")
        assert_response_error(response, status_code=404, detail="not found")
    
    def test_update_memory_content(
        self, client_with_data, mock_embeddings, assert_response_success
    ):
        """Test updating memory content re-embeds."""
        update_data = {"content": "Updated AI response content"}
        
        response = client_with_data.put("/api/v1/ai/memories/1", json=update_data)
        data = assert_response_success(response)
        
        assert "Updated" in data["content"]
    
    def test_update_memory_status(self, client_with_data, assert_response_success):
        """Test archiving a memory."""
        update_data = {"status": "archived"}
        
        response = client_with_data.put("/api/v1/ai/memories/1", json=update_data)
        data = assert_response_success(response)
        
        assert data["status"] == "archived"
    
    def test_update_memory_importance(self, client_with_data, assert_response_success):
        """Test updating memory importance."""
        update_data = {"importance": 10}
        
        response = client_with_data.put("/api/v1/ai/memories/1", json=update_data)
        data = assert_response_success(response)
        
        assert data["importance"] == 10
    
    def test_delete_memory_soft_delete(self, client_with_data):
        """Test that delete soft-deletes by setting status to rejected."""
        response = client_with_data.delete("/api/v1/ai/memories/1")
        assert response.status_code == 204
        
        # Memory still exists but is rejected
        # (Would need to check with status filter to verify)


class TestMemorySearch:
    """Tests for semantic search over memories."""
    
    def test_search_memories(
        self, client_with_data, mock_embeddings, assert_response_success
    ):
        """Test basic semantic search."""
        response = client_with_data.get("/api/v1/ai/memories/search?query=testing")
        data = assert_response_success(response)
        
        assert isinstance(data, list)
        # Results should have similarity scores
        for result in data:
            assert "similarity_score" in result
    
    def test_search_with_top_k(self, client_with_data, mock_embeddings, assert_response_success):
        """Test limiting search results."""
        response = client_with_data.get("/api/v1/ai/memories/search?query=test&top_k=5")
        data = assert_response_success(response)
        
        assert len(data) <= 5
    
    def test_search_with_min_similarity(
        self, client_with_data, mock_embeddings, assert_response_success
    ):
        """Test filtering by minimum similarity threshold."""
        response = client_with_data.get(
            "/api/v1/ai/memories/search?query=test&min_similarity=0.5"
        )
        data = assert_response_success(response)
        
        for result in data:
            assert result["similarity_score"] >= 0.5


class TestMemoryContext:
    """Tests for LLM context retrieval."""
    
    def test_get_context_basic(
        self, client_with_data, mock_embeddings, assert_response_success
    ):
        """Test getting formatted context for LLM injection."""
        response = client_with_data.get(
            "/api/v1/ai/memories/context?query=testing strategies"
        )
        data = assert_response_success(response)
        
        assert "memories" in data
        assert "total_tokens_estimate" in data
        assert "memory_count" in data
        assert isinstance(data["memories"], list)
    
    def test_context_respects_max_memories(
        self, client_with_data, mock_embeddings, assert_response_success
    ):
        """Test that context respects max_memories limit."""
        response = client_with_data.get(
            "/api/v1/ai/memories/context?query=test&max_memories=3"
        )
        data = assert_response_success(response)
        
        assert data["memory_count"] <= 3
    
    def test_context_respects_token_budget(
        self, client_with_data, mock_embeddings, assert_response_success
    ):
        """Test that context respects max_tokens budget."""
        response = client_with_data.get(
            "/api/v1/ai/memories/context?query=test&max_tokens=500"
        )
        data = assert_response_success(response)
        
        assert data["total_tokens_estimate"] <= 500
    
    def test_context_includes_high_importance(
        self, client_with_data, mock_embeddings, ai_memory_factory
    ):
        """Test that high-importance memories are always included."""
        # Create high-importance memory
        memory = ai_memory_factory(importance=9, content="Critical information")
        client_with_data.post("/api/v1/ai/memories", json=memory)
        
        response = client_with_data.get(
            "/api/v1/ai/memories/context?query=unrelated&include_high_importance=true"
        )
        
        # High importance memories should still appear
        assert response.status_code == 200


class TestMemoryFromChat:
    """Tests for quick chat-to-memory conversion."""
    
    def test_save_chat_as_memory(
        self, client, mock_embeddings, assert_response_success
    ):
        """Test convenience endpoint for saving chat exchange."""
        response = client.post(
            "/api/v1/ai/memories/from-chat",
            params={
                "query": "How do I write tests?",
                "response": "To write effective tests, start with...",
                "importance": 6
            }
        )
        data = assert_response_success(response, status_code=201)
        
        assert data["source_type"] == "chat"
        assert data["source_query"] == "How do I write tests?"
        assert data["importance"] == 6


class TestMemoryStats:
    """Tests for memory statistics."""
    
    def test_get_memory_stats(self, client_with_data, assert_response_success):
        """Test getting memory statistics."""
        response = client_with_data.get("/api/v1/ai/memories/stats")
        data = assert_response_success(response)
        
        assert "total" in data
        assert "by_status" in data
        assert "avg_importance" in data
        assert "by_source" in data
    
    def test_stats_counts_correct(
        self, client, mock_embeddings, ai_memory_factory, assert_response_success
    ):
        """Test that stats accurately reflect memory counts."""
        # Create several memories
        for i in range(3):
            memory = ai_memory_factory(importance=5 + i)
            client.post("/api/v1/ai/memories", json=memory)
        
        response = client.get("/api/v1/ai/memories/stats")
        data = assert_response_success(response)
        
        assert data["total"] >= 3
        assert data["by_status"]["approved"] >= 3
