# src/app/repositories/meetings.py
"""
Meeting Repository - Ports and Adapters

Port: MeetingRepository (abstract interface)
Adapters: SupabaseMeetingRepository, SQLiteMeetingRepository
"""

import json
import logging
from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseRepository, QueryOptions

logger = logging.getLogger(__name__)


class MeetingRepository(BaseRepository[Dict[str, Any]]):
    """
    Meeting Repository Port - defines the interface for meeting data access.
    
    Extends BaseRepository with meeting-specific operations.
    """
    
    @abstractmethod
    def get_by_date_range(
        self, start_date: str, end_date: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get meetings within a date range."""
        pass
    
    @abstractmethod
    def get_with_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get meetings that have extracted signals."""
        pass
    
    @abstractmethod
    def search(
        self, query: str, include_transcripts: bool = False, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search meetings by text content."""
        pass


# =============================================================================
# SUPABASE ADAPTER
# =============================================================================

class SupabaseMeetingRepository(MeetingRepository):
    """
    Supabase adapter for meeting repository.
    
    Reads and writes meeting data to/from Supabase cloud database.
    """
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from ..infrastructure.supabase_client import get_supabase_client
            self._client = get_supabase_client()
        return self._client
    
    def _format_row(self, row: Dict) -> Dict[str, Any]:
        """Format Supabase row to standard meeting dict."""
        return {
            "id": row.get("id"),
            "meeting_name": row.get("meeting_name", "Untitled Meeting"),
            "meeting_date": row.get("meeting_date"),
            "synthesized_notes": row.get("synthesized_notes", ""),
            "signals_json": json.dumps(row.get("signals", {})) if row.get("signals") else None,
            "signals": row.get("signals", {}),
            "raw_text": row.get("raw_text"),
            "pocket_ai_summary": row.get("pocket_ai_summary"),
            "pocket_mind_map": row.get("pocket_mind_map"),
            "import_source": row.get("import_source"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
    
    def get_all(self, options: Optional[QueryOptions] = None) -> List[Dict[str, Any]]:
        """Get all meetings from Supabase."""
        if not self.client:
            logger.warning("Supabase not available")
            return []
        
        options = options or QueryOptions()
        
        try:
            query = self.client.table("meetings").select("*")
            
            # Apply ordering
            query = query.order(options.order_by, desc=options.order_desc)
            
            # Apply pagination
            if options.offset:
                query = query.range(options.offset, options.offset + options.limit - 1)
            else:
                query = query.limit(options.limit)
            
            result = query.execute()
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get meetings: {e}")
            return []
    
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single meeting by ID."""
        if not self.client:
            return None
        
        try:
            result = self.client.table("meetings").select("*").eq("id", entity_id).single().execute()
            return self._format_row(result.data) if result.data else None
        except Exception as e:
            logger.error(f"Failed to get meeting {entity_id}: {e}")
            return None
    
    def get_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get count of meetings."""
        if not self.client:
            return 0
        
        try:
            result = self.client.table("meetings").select("id", count="exact").execute()
            return result.count or 0
        except Exception as e:
            logger.error(f"Failed to get meeting count: {e}")
            return 0
    
    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new meeting."""
        if not self.client:
            return None
        
        try:
            # Convert signals_json to signals object if present
            if "signals_json" in data and data["signals_json"]:
                data["signals"] = json.loads(data["signals_json"])
                del data["signals_json"]
            
            result = self.client.table("meetings").insert(data).execute()
            return self._format_row(result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Failed to create meeting: {e}")
            return None
    
    def update(self, entity_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing meeting."""
        if not self.client:
            return None
        
        try:
            # Convert signals_json to signals object if present
            if "signals_json" in data and data["signals_json"]:
                data["signals"] = json.loads(data["signals_json"])
                del data["signals_json"]
            
            data["updated_at"] = datetime.utcnow().isoformat()
            result = self.client.table("meetings").update(data).eq("id", entity_id).execute()
            return self._format_row(result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Failed to update meeting {entity_id}: {e}")
            return None
    
    def delete(self, entity_id: str) -> bool:
        """Delete a meeting."""
        if not self.client:
            return False
        
        try:
            self.client.table("meetings").delete().eq("id", entity_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete meeting {entity_id}: {e}")
            return False
    
    def get_by_date_range(
        self, start_date: str, end_date: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get meetings within a date range."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("meetings").select("*").gte(
                "meeting_date", start_date
            ).lte(
                "meeting_date", end_date
            ).order("meeting_date", desc=True).limit(limit).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get meetings by date range: {e}")
            return []
    
    def get_with_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get meetings that have signals extracted."""
        if not self.client:
            return []
        
        try:
            result = self.client.table("meetings").select("*").not_.is_(
                "signals", "null"
            ).order("meeting_date", desc=True).limit(limit).execute()
            
            return [self._format_row(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to get meetings with signals: {e}")
            return []
    
    def search(
        self, query: str, include_transcripts: bool = False, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search meetings by text content."""
        if not self.client:
            return []
        
        # For Supabase, we do client-side filtering (could use full-text search in future)
        all_meetings = self.get_all(QueryOptions(limit=200))
        query_lower = query.lower()
        
        results = []
        for m in all_meetings:
            match = False
            notes = (m.get("synthesized_notes") or "").lower()
            name = (m.get("meeting_name") or "").lower()
            raw = (m.get("raw_text") or "").lower() if include_transcripts else ""
            
            if query_lower in notes or query_lower in name or query_lower in raw:
                match = True
            
            if match:
                results.append(m)
                if len(results) >= limit:
                    break
        
        return results


# =============================================================================
# SQLITE ADAPTER
# =============================================================================

class SQLiteMeetingRepository(MeetingRepository):
    """
    SQLite adapter for meeting repository.
    
    Reads and writes meeting data to/from local SQLite database.
    Used as fallback when Supabase is unavailable.
    """
    
    def _get_connection(self):
        """Get SQLite connection."""
        from ..db import connect
        return connect()
    
    def _format_row(self, row) -> Dict[str, Any]:
        """Format SQLite row to standard meeting dict."""
        return {
            "id": row["id"],
            "meeting_name": row["meeting_name"],
            "meeting_date": row["meeting_date"],
            "synthesized_notes": row["synthesized_notes"],
            "signals_json": row.get("signals_json"),
            "signals": json.loads(row["signals_json"]) if row.get("signals_json") else {},
            "raw_text": row.get("raw_text"),
            "pocket_ai_summary": row.get("pocket_ai_summary"),
            "pocket_mind_map": row.get("pocket_mind_map"),
            "import_source": row.get("import_source"),
            "created_at": row.get("created_at"),
        }
    
    def get_all(self, options: Optional[QueryOptions] = None) -> List[Dict[str, Any]]:
        """Get all meetings from SQLite."""
        options = options or QueryOptions()
        order_dir = "DESC" if options.order_desc else "ASC"
        
        with self._get_connection() as conn:
            rows = conn.execute(f"""
                SELECT * FROM meeting_summaries
                ORDER BY {options.order_by} {order_dir}
                LIMIT ? OFFSET ?
            """, (options.limit, options.offset)).fetchall()
            
            return [self._format_row(row) for row in rows]
    
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single meeting by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM meeting_summaries WHERE id = ?", (entity_id,)
            ).fetchone()
            
            return self._format_row(row) if row else None
    
    def get_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get count of meetings."""
        with self._get_connection() as conn:
            result = conn.execute("SELECT COUNT(*) FROM meeting_summaries").fetchone()
            return result[0] if result else 0
    
    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new meeting."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO meeting_summaries 
                (meeting_name, synthesized_notes, meeting_date, signals_json, raw_text, import_source)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data.get("meeting_name"),
                data.get("synthesized_notes"),
                data.get("meeting_date"),
                data.get("signals_json"),
                data.get("raw_text"),
                data.get("import_source"),
            ))
            conn.commit()
            return self.get_by_id(cursor.lastrowid)
    
    def update(self, entity_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing meeting."""
        # Build dynamic update query
        fields = []
        values = []
        for key in ["meeting_name", "synthesized_notes", "meeting_date", "signals_json", "raw_text"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        
        if not fields:
            return self.get_by_id(entity_id)
        
        values.append(entity_id)
        
        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE meeting_summaries SET {', '.join(fields)} WHERE id = ?",
                values
            )
            conn.commit()
            return self.get_by_id(entity_id)
    
    def delete(self, entity_id: str) -> bool:
        """Delete a meeting."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM meeting_summaries WHERE id = ?", (entity_id,))
            conn.commit()
            return True
    
    def get_by_date_range(
        self, start_date: str, end_date: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get meetings within a date range."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM meeting_summaries
                WHERE meeting_date BETWEEN ? AND ?
                ORDER BY meeting_date DESC
                LIMIT ?
            """, (start_date, end_date, limit)).fetchall()
            
            return [self._format_row(row) for row in rows]
    
    def get_with_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get meetings that have signals extracted."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM meeting_summaries
                WHERE signals_json IS NOT NULL
                ORDER BY meeting_date DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [self._format_row(row) for row in rows]
    
    def search(
        self, query: str, include_transcripts: bool = False, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search meetings by text content."""
        like = f"%{query.lower()}%"
        
        with self._get_connection() as conn:
            if include_transcripts:
                rows = conn.execute("""
                    SELECT * FROM meeting_summaries
                    WHERE LOWER(synthesized_notes) LIKE ?
                    OR LOWER(meeting_name) LIKE ?
                    OR LOWER(raw_text) LIKE ?
                    ORDER BY meeting_date DESC
                    LIMIT ?
                """, (like, like, like, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM meeting_summaries
                    WHERE LOWER(synthesized_notes) LIKE ?
                    OR LOWER(meeting_name) LIKE ?
                    ORDER BY meeting_date DESC
                    LIMIT ?
                """, (like, like, limit)).fetchall()
            
            return [self._format_row(row) for row in rows]
