"""
Tests for F2b: Quick AI "My Updates" - Personalized Transcript Search

Tests the @Rowan button functionality that searches raw transcripts
for user mentions using keyword search with context extraction.
"""

import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Set test environment
os.environ.setdefault("USER_NAME", "TestUser")


@pytest.fixture
def agent_config():
    """Create a minimal AgentConfig for testing."""
    from src.app.agents.base import AgentConfig
    return AgentConfig(
        name="test-arjuna",
        description="Test agent for F2b",
        primary_model="gpt-4o-mini",
    )


class TestSearchUserMentionsInTranscripts:
    """Tests for _search_user_mentions_in_transcripts method."""
    
    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn
    
    @pytest.mark.asyncio
    async def test_finds_mentions_in_raw_text(self, mock_db_connection, agent_config):
        """Should find user mentions in meeting_summaries.raw_text."""
        from src.app.agents.arjuna import ArjunaAgent
        
        # Mock database results
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchall=lambda: [
                {
                    "id": 1,
                    "meeting_name": "Sprint Planning",
                    "raw_text": "TestUser mentioned the blockers. TestUser also asked about timeline.",
                    "meeting_date": "2025-01-15"
                }
            ]),
            MagicMock(fetchall=lambda: [])  # No meeting_documents results
        ]
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            agent = ArjunaAgent(config=agent_config)
            result = await agent._search_user_mentions_in_transcripts("TestUser")
        
        assert "Sprint Planning" in result
        assert "TestUser" in result
        assert "2025-01-15" in result
    
    @pytest.mark.asyncio
    async def test_finds_mentions_in_meeting_documents(self, mock_db_connection, agent_config):
        """Should find user mentions in meeting_documents.content."""
        from src.app.agents.arjuna import ArjunaAgent
        
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchall=lambda: []),  # No raw_text results
            MagicMock(fetchall=lambda: [
                {
                    "content": "Transcript: TestUser said we need to prioritize the API work.",
                    "source": "Teams",
                    "doc_type": "transcript",
                    "meeting_name": "API Review",
                    "meeting_date": "2025-01-14"
                }
            ])
        ]
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            agent = ArjunaAgent(config=agent_config)
            result = await agent._search_user_mentions_in_transcripts("TestUser")
        
        assert "API Review" in result
        assert "Teams" in result
        assert "TestUser said we need to prioritize" in result
    
    @pytest.mark.asyncio
    async def test_returns_message_when_no_mentions(self, mock_db_connection, agent_config):
        """Should return helpful message when no mentions found."""
        from src.app.agents.arjuna import ArjunaAgent
        
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: [])
        ]
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            agent = ArjunaAgent(config=agent_config)
            result = await agent._search_user_mentions_in_transcripts("TestUser")
        
        assert "No mentions of TestUser found" in result
    
    @pytest.mark.asyncio
    async def test_handles_database_error_gracefully(self, mock_db_connection, agent_config):
        """Should handle database errors gracefully."""
        from src.app.agents.arjuna import ArjunaAgent
        
        mock_db_connection.execute.side_effect = Exception("Database error")
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            agent = ArjunaAgent(config=agent_config)
            result = await agent._search_user_mentions_in_transcripts("TestUser")
        
        assert "No mentions of TestUser found" in result
    
    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, mock_db_connection, agent_config):
        """Should find mentions regardless of case."""
        from src.app.agents.arjuna import ArjunaAgent
        
        # The query uses LOWER() so it should be case-insensitive
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchall=lambda: [
                {
                    "id": 1,
                    "meeting_name": "Team Sync",
                    "raw_text": "TESTUSER was assigned the task. testuser will follow up.",
                    "meeting_date": "2025-01-15"
                }
            ]),
            MagicMock(fetchall=lambda: [])
        ]
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            agent = ArjunaAgent(config=agent_config)
            result = await agent._search_user_mentions_in_transcripts("TestUser")
        
        assert "Team Sync" in result


class TestExtractMentionSnippet:
    """Tests for _extract_mention_snippet helper method."""
    
    def test_extracts_context_around_mention(self, agent_config):
        """Should extract context around the user mention."""
        from src.app.agents.arjuna import ArjunaAgent
        
        agent = ArjunaAgent(config=agent_config)
        text = "A" * 100 + "Rowan said we need to fix the bug" + "B" * 100
        
        snippet = agent._extract_mention_snippet(text, "Rowan", context_chars=50)
        
        assert "Rowan" in snippet
        assert "said we need to fix" in snippet
        assert len(snippet) < len(text)
    
    def test_handles_multiple_mentions(self, agent_config):
        """Should extract multiple snippets for multiple mentions."""
        from src.app.agents.arjuna import ArjunaAgent
        
        agent = ArjunaAgent(config=agent_config)
        text = "First, Rowan reviewed the PR. Later, Rowan suggested changes. Finally, Rowan approved it."
        
        snippet = agent._extract_mention_snippet(text, "Rowan", context_chars=20)
        
        # Should have multiple occurrences
        assert snippet.count("Rowan") >= 2
    
    def test_limits_snippets_to_three(self, agent_config):
        """Should limit to 3 snippets per document."""
        from src.app.agents.arjuna import ArjunaAgent
        
        agent = ArjunaAgent(config=agent_config)
        # Create text with many mentions
        text = " ".join(["Rowan mentioned item " + str(i) + "." for i in range(10)])
        
        snippet = agent._extract_mention_snippet(text, "Rowan", context_chars=30)
        
        # Should have at most 3 snippets
        lines = [l for l in snippet.split("\n") if l.strip()]
        assert len(lines) <= 3
    
    def test_handles_empty_text(self, agent_config):
        """Should handle empty text gracefully."""
        from src.app.agents.arjuna import ArjunaAgent
        
        agent = ArjunaAgent(config=agent_config)
        
        assert agent._extract_mention_snippet("", "Rowan") == ""
        assert agent._extract_mention_snippet(None, "Rowan") == ""
    
    def test_handles_no_matches(self, agent_config):
        """Should return empty string when no matches."""
        from src.app.agents.arjuna import ArjunaAgent
        
        agent = ArjunaAgent(config=agent_config)
        text = "This text doesn't mention anyone relevant."
        
        snippet = agent._extract_mention_snippet(text, "Rowan")
        
        assert snippet == ""
    
    def test_adds_ellipsis_when_truncated(self, agent_config):
        """Should add ellipsis when context is truncated."""
        from src.app.agents.arjuna import ArjunaAgent
        
        agent = ArjunaAgent(config=agent_config)
        text = "A" * 200 + "Rowan spoke" + "B" * 200
        
        snippet = agent._extract_mention_snippet(text, "Rowan", context_chars=50)
        
        assert snippet.startswith("...")
        assert snippet.endswith("...")


class TestQuickAskWithUserMentions:
    """Tests for quick_ask with rowan_mentions topic."""
    
    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn
    
    @pytest.mark.asyncio
    async def test_uses_transcript_search_for_rowan_mentions(self, mock_db_connection, agent_config):
        """Should use _search_user_mentions_in_transcripts for rowan_mentions topic."""
        from src.app.agents.arjuna import ArjunaAgent
        
        # Mock the transcript search
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchall=lambda: [
                {
                    "id": 1,
                    "meeting_name": "Sprint Review",
                    "raw_text": "TestUser did an excellent job on the API.",
                    "meeting_date": "2025-01-15"
                }
            ]),
            MagicMock(fetchall=lambda: [])
        ]
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            with patch.object(ArjunaAgent, 'ask_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "Found mentions of TestUser in Sprint Review."
                
                with patch.dict(os.environ, {"USER_NAME": "TestUser"}):
                    agent = ArjunaAgent(config=agent_config)
                    result = await agent.quick_ask(topic="rowan_mentions")
        
        assert result["success"] is True
        # Verify the LLM was called with transcript context
        call_args = mock_llm.call_args
        assert "Sprint Review" in call_args[1]["prompt"] or "TestUser" in call_args[1]["prompt"]
    
    @pytest.mark.asyncio
    async def test_uses_env_user_name(self, mock_db_connection, agent_config):
        """Should use USER_NAME from environment."""
        from src.app.agents.arjuna import ArjunaAgent
        
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: [])
        ]
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            with patch.object(ArjunaAgent, 'ask_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "No mentions found."
                
                with patch.dict(os.environ, {"USER_NAME": "CustomUser"}):
                    agent = ArjunaAgent(config=agent_config)
                    result = await agent.quick_ask(topic="rowan_mentions")
        
        # Check the SQL query was built with the custom user name
        assert mock_db_connection.execute.called
        # First call should search for the user name
        call_args = mock_db_connection.execute.call_args_list[0]
        assert "%customuser%" in call_args[0][1][0].lower()
    
    @pytest.mark.asyncio
    async def test_defaults_to_rowan_when_no_env(self, mock_db_connection, agent_config):
        """Should default to 'Rowan' when USER_NAME not set."""
        from src.app.agents.arjuna import ArjunaAgent
        
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: [])
        ]
        
        # Remove USER_NAME from environment
        env_without_user = {k: v for k, v in os.environ.items() if k != "USER_NAME"}
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            with patch.object(ArjunaAgent, 'ask_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "No mentions found."
                
                with patch.dict(os.environ, env_without_user, clear=True):
                    agent = ArjunaAgent(config=agent_config)
                    result = await agent.quick_ask(topic="rowan_mentions")
        
        # Verify query uses "Rowan"
        call_args = mock_db_connection.execute.call_args_list[0]
        assert "%rowan%" in call_args[0][1][0].lower()


class TestGetRecentMeetingsContext:
    """Tests for _get_recent_meetings_context helper method."""
    
    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn
    
    @pytest.mark.asyncio
    async def test_returns_meeting_context(self, mock_db_connection, agent_config):
        """Should return context from recent meetings."""
        from src.app.agents.arjuna import ArjunaAgent
        
        mock_db_connection.execute.return_value = MagicMock(fetchall=lambda: [
            {
                "meeting_name": "Team Standup",
                "synthesized_notes": "Discussed sprint progress and blockers.",
                "signals_json": '{"decisions": ["Use new API"], "action_items": ["Review PR"]}'
            }
        ])
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            agent = ArjunaAgent(config=agent_config)
            context = await agent._get_recent_meetings_context()
        
        assert "Team Standup" in context
        assert "Discussed sprint progress" in context
        assert "Use new API" in context
    
    @pytest.mark.asyncio
    async def test_handles_missing_signals(self, mock_db_connection, agent_config):
        """Should handle meetings without signals_json."""
        from src.app.agents.arjuna import ArjunaAgent
        
        mock_db_connection.execute.return_value = MagicMock(fetchall=lambda: [
            {
                "meeting_name": "Quick Sync",
                "synthesized_notes": "Brief discussion.",
                "signals_json": None
            }
        ])
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            agent = ArjunaAgent(config=agent_config)
            context = await agent._get_recent_meetings_context()
        
        assert "Quick Sync" in context
        assert "Brief discussion" in context
    
    @pytest.mark.asyncio
    async def test_handles_database_error(self, mock_db_connection, agent_config):
        """Should handle database errors gracefully."""
        from src.app.agents.arjuna import ArjunaAgent
        
        mock_db_connection.execute.side_effect = Exception("DB Error")
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            agent = ArjunaAgent(config=agent_config)
            context = await agent._get_recent_meetings_context()
        
        assert context == ""


class TestOtherQuickAskTopics:
    """Tests that other quick_ask topics still work correctly."""
    
    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = MagicMock(fetchall=lambda: [
            {
                "meeting_name": "Sprint Planning",
                "synthesized_notes": "Planned the sprint.",
                "signals_json": '{"blockers": ["API delay"]}'
            }
        ])
        return mock_conn
    
    @pytest.mark.asyncio
    async def test_blockers_uses_standard_context(self, mock_db_connection, agent_config):
        """Should use standard meeting context for blockers topic."""
        from src.app.agents.arjuna import ArjunaAgent
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            with patch.object(ArjunaAgent, 'ask_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "Current blockers: API delay"
                
                agent = ArjunaAgent(config=agent_config)
                result = await agent.quick_ask(topic="blockers")
        
        assert result["success"] is True
        # Should call the standard context method, not transcript search
        call_args = mock_llm.call_args
        assert "blockers" in call_args[1]["prompt"].lower()
    
    @pytest.mark.asyncio
    async def test_decisions_uses_standard_context(self, mock_db_connection, agent_config):
        """Should use standard meeting context for decisions topic."""
        from src.app.agents.arjuna import ArjunaAgent
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            with patch.object(ArjunaAgent, 'ask_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "Key decisions made..."
                
                agent = ArjunaAgent(config=agent_config)
                result = await agent.quick_ask(topic="decisions")
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_custom_query_uses_standard_context(self, mock_db_connection, agent_config):
        """Should use standard meeting context for custom queries."""
        from src.app.agents.arjuna import ArjunaAgent
        
        with patch("src.app.db.connect", return_value=mock_db_connection):
            with patch.object(ArjunaAgent, 'ask_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "Based on meetings..."
                
                agent = ArjunaAgent(config=agent_config)
                result = await agent.quick_ask(query="What happened last week?")
        
        assert result["success"] is True
        call_args = mock_llm.call_args
        assert "last week" in call_args[1]["prompt"].lower()
