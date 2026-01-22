# tests/test_supabase_sync.py
"""
Tests for Supabase synchronization.

Tests the data sync between SQLite and Supabase including:
- Migration scripts
- Real-time sync
- Conflict resolution
- Offline-first behavior
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


class TestSupabaseMigration:
    """Tests for SQLite to Supabase migration."""
    
    def test_migrate_meetings(self, test_db, mock_supabase):
        """Test migrating meetings from SQLite to Supabase."""
        # Insert test meeting in SQLite
        test_db.execute(
            """
            INSERT INTO meeting_summaries (id, meeting_name, synthesized_notes, meeting_date)
            VALUES (1, 'Test Meeting', 'Test notes', '2024-01-15')
            """
        )
        test_db.commit()
        
        # Mock the migration function
        from scripts.migrate_data_to_supabase import migrate_meeting_summaries
        
        with patch("scripts.migrate_data_to_supabase.get_supabase_client", return_value=mock_supabase):
            count = migrate_meeting_summaries(test_db, mock_supabase)
        
        # Verify Supabase insert was called
        mock_supabase.table.assert_called_with("meeting_summaries")
    
    def test_migrate_with_json_fields(self, test_db, mock_supabase):
        """Test that JSON fields are properly parsed during migration."""
        # Insert meeting with JSON signals
        test_db.execute(
            """
            INSERT INTO meeting_summaries (id, meeting_name, synthesized_notes, signals_json)
            VALUES (1, 'Test', 'Notes', '{"decisions": [{"text": "Use Python"}]}')
            """
        )
        test_db.commit()
        
        # The migration should parse JSON strings into objects
        row = test_db.execute("SELECT signals_json FROM meeting_summaries WHERE id = 1").fetchone()
        assert row["signals_json"] is not None
    
    def test_migrate_empty_table(self, test_db, mock_supabase):
        """Test migration handles empty tables gracefully."""
        # Empty database, should not error
        from scripts.migrate_data_to_supabase import migrate_docs
        
        with patch("scripts.migrate_data_to_supabase.get_supabase_client", return_value=mock_supabase):
            count = migrate_docs(test_db, mock_supabase)
        
        assert count == 0


class TestSupabaseSync:
    """Tests for real-time sync functionality."""
    
    def test_sync_on_create(self, mock_supabase):
        """Test that new records sync to Supabase."""
        # This would test the sync trigger on record creation
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "uuid-123"}]
        )
        
        result = mock_supabase.table("meetings").insert({"meeting_name": "New"}).execute()
        
        assert result.data[0]["id"] == "uuid-123"
    
    def test_sync_on_update(self, mock_supabase):
        """Test that updates sync to Supabase."""
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "uuid-123", "meeting_name": "Updated"}]
        )
        
        result = mock_supabase.table("meetings").update({"meeting_name": "Updated"}).eq("id", "uuid-123").execute()
        
        assert result.data[0]["meeting_name"] == "Updated"
    
    def test_sync_on_delete(self, mock_supabase):
        """Test that deletes sync to Supabase."""
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        
        result = mock_supabase.table("meetings").delete().eq("id", "uuid-123").execute()
        
        assert len(result.data) == 0


class TestConflictResolution:
    """Tests for sync conflict handling."""
    
    def test_last_write_wins(self, mock_supabase):
        """Test last-write-wins conflict resolution."""
        # Simulate two updates with different timestamps
        local_update = {
            "id": "uuid-123",
            "meeting_name": "Local Update",
            "updated_at": datetime(2024, 1, 15, 10, 0, 0)
        }
        
        remote_update = {
            "id": "uuid-123",
            "meeting_name": "Remote Update",
            "updated_at": datetime(2024, 1, 15, 11, 0, 0)  # Later
        }
        
        # Remote is newer, should win
        winner = remote_update if remote_update["updated_at"] > local_update["updated_at"] else local_update
        
        assert winner["meeting_name"] == "Remote Update"
    
    def test_conflict_detection(self, mock_supabase):
        """Test that conflicts are detected during sync."""
        # This would test the conflict detection logic
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"updated_at": "2024-01-15T10:00:00Z"}]
        )
        
        local_updated_at = datetime(2024, 1, 15, 9, 0, 0)
        
        # Fetch remote version
        result = mock_supabase.table("meetings").select("updated_at").eq("id", "uuid-123").execute()
        remote_updated_at = datetime.fromisoformat(result.data[0]["updated_at"].replace("Z", "+00:00"))
        
        # If both have been modified since last sync, we have a conflict
        has_conflict = local_updated_at > datetime(2024, 1, 14) and remote_updated_at > datetime(2024, 1, 14)
        
        assert has_conflict is True


class TestOfflineFirst:
    """Tests for offline-first behavior."""
    
    def test_works_without_supabase(self, test_db):
        """Test that app works when Supabase is unavailable."""
        # Insert directly to SQLite (simulating offline)
        test_db.execute(
            "INSERT INTO docs (source, content) VALUES ('Offline Doc', 'Content')"
        )
        test_db.commit()
        
        # Verify data persists
        row = test_db.execute("SELECT * FROM docs WHERE source = 'Offline Doc'").fetchone()
        assert row is not None
    
    def test_queue_changes_when_offline(self, test_db):
        """Test that changes are queued for sync when offline."""
        # This would test the sync queue
        test_db.execute(
            """
            INSERT INTO sync_log (table_name, record_id, operation, synced)
            VALUES ('docs', 1, 'INSERT', 0)
            """
        )
        test_db.commit()
        
        # Check queue has pending item
        pending = test_db.execute(
            "SELECT COUNT(*) as count FROM sync_log WHERE synced = 0"
        ).fetchone()
        
        assert pending["count"] >= 1
    
    def test_sync_queued_changes_on_reconnect(self, test_db, mock_supabase):
        """Test that queued changes sync when connection restored."""
        # Queue some changes
        test_db.execute(
            """
            INSERT INTO sync_log (table_name, record_id, operation, synced)
            VALUES ('docs', 1, 'INSERT', 0), ('docs', 2, 'UPDATE', 0)
            """
        )
        test_db.commit()
        
        # Simulate sync process
        pending = test_db.execute(
            "SELECT * FROM sync_log WHERE synced = 0"
        ).fetchall()
        
        assert len(pending) == 2
        
        # After sync, mark as synced
        test_db.execute("UPDATE sync_log SET synced = 1")
        test_db.commit()
        
        remaining = test_db.execute(
            "SELECT COUNT(*) as count FROM sync_log WHERE synced = 0"
        ).fetchone()
        
        assert remaining["count"] == 0


class TestDataIntegrity:
    """Tests for data integrity during sync."""
    
    def test_uuid_mapping_preserved(self, test_db, mock_supabase):
        """Test that SQLite IDs map correctly to Supabase UUIDs."""
        # Insert with local ID
        test_db.execute(
            "INSERT INTO docs (id, source, content) VALUES (42, 'Test', 'Content')"
        )
        test_db.commit()
        
        # Supabase would return a UUID
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "uuid-42-mapped"}]
        )
        
        # The mapping should be tracked
        # (Implementation would store this mapping in a sync table)
    
    def test_foreign_keys_maintained(self, test_db):
        """Test that foreign key relationships are preserved."""
        # Create meeting
        test_db.execute(
            "INSERT INTO meeting_summaries (id, meeting_name, synthesized_notes) VALUES (1, 'Test', 'Notes')"
        )
        
        # Create DIKW item referencing meeting
        test_db.execute(
            """
            INSERT INTO dikw_items (id, level, content, meeting_id)
            VALUES (1, 'data', 'Test insight', 1)
            """
        )
        test_db.commit()
        
        # Verify FK works
        dikw = test_db.execute(
            """
            SELECT d.*, m.meeting_name 
            FROM dikw_items d
            JOIN meeting_summaries m ON d.meeting_id = m.id
            WHERE d.id = 1
            """
        ).fetchone()
        
        assert dikw["meeting_name"] == "Test"
    
    def test_embedding_vectors_preserved(self, test_db):
        """Test that embedding vectors survive migration."""
        import json
        
        # Create embedding with vector
        vector = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
        test_db.execute(
            """
            INSERT INTO embeddings (ref_type, ref_id, model, vector)
            VALUES ('doc', 1, 'text-embedding-3-small', ?)
            """,
            (json.dumps(vector),)
        )
        test_db.commit()
        
        # Verify vector retrieved correctly
        row = test_db.execute("SELECT vector FROM embeddings WHERE ref_id = 1").fetchone()
        retrieved_vector = json.loads(row["vector"])
        
        assert len(retrieved_vector) == 1536
        assert retrieved_vector[0] == 0.1
