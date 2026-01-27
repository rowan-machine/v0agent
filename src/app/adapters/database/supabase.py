# src/app/adapters/database/supabase.py
"""
Supabase Database Adapter

Implements DatabasePort interface using Supabase as the backend.
This is the primary production database adapter.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from supabase import create_client, Client

from ...core.ports.database import (
    DatabasePort,
    MeetingsRepository,
    DocumentsRepository,
    TicketsRepository,
    DIKWRepository,
    SignalsRepository,
    ConversationsRepository,
    SettingsRepository,
    NotificationsRepository,
)

logger = logging.getLogger(__name__)


class SupabaseDatabaseAdapter(DatabasePort):
    """
    Supabase implementation of DatabasePort.
    
    Uses Supabase's PostgREST API for all database operations.
    """
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize Supabase adapter.
        
        Args:
            url: Supabase project URL (defaults to SUPABASE_URL env var)
            key: Supabase anon/service key (defaults to SUPABASE_KEY env var)
        """
        self._url = url or os.getenv("SUPABASE_URL")
        self._key = key or os.getenv("SUPABASE_KEY")
        
        if not self._url or not self._key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self._client: Client = create_client(self._url, self._key)
        self._in_transaction = False
        logger.info("SupabaseDatabaseAdapter initialized")
    
    @property
    def client(self) -> Client:
        """Get the underlying Supabase client."""
        return self._client
    
    # =============================================================================
    # GENERIC CRUD OPERATIONS
    # =============================================================================
    
    def get_by_id(self, table: str, id: Any) -> Optional[Dict[str, Any]]:
        """Get a single record by ID."""
        try:
            result = self._client.table(table).select("*").eq("id", id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting {table} by id {id}: {e}")
            return None
    
    def get_all(
        self, 
        table: str, 
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all records from a table with optional filters."""
        try:
            query = self._client.table(table).select("*")
            
            if filters:
                for key, value in filters.items():
                    if value is None:
                        query = query.is_(key, "null")
                    else:
                        query = query.eq(key, value)
            
            if order_by:
                query = query.order(order_by, desc=order_desc)
            
            if limit:
                query = query.limit(limit)
            
            if offset:
                query = query.offset(offset)
            
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting all from {table}: {e}")
            return []
    
    def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record and return it with generated ID."""
        try:
            # Remove None values and id if None
            clean_data = {k: v for k, v in data.items() if v is not None and k != 'id'}
            result = self._client.table(table).insert(clean_data).execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error inserting into {table}: {e}")
            raise
    
    def insert_many(self, table: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert multiple records."""
        try:
            clean_data = [
                {k: v for k, v in row.items() if v is not None and k != 'id'}
                for row in data
            ]
            result = self._client.table(table).insert(clean_data).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error inserting many into {table}: {e}")
            raise
    
    def update(self, table: str, id: Any, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record by ID."""
        try:
            # Remove id from data if present
            clean_data = {k: v for k, v in data.items() if k != 'id'}
            result = self._client.table(table).update(clean_data).eq("id", id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error updating {table} id {id}: {e}")
            return None
    
    def upsert(
        self, 
        table: str, 
        data: Dict[str, Any], 
        conflict_columns: List[str]
    ) -> Dict[str, Any]:
        """Insert or update based on conflict columns."""
        try:
            on_conflict = ",".join(conflict_columns)
            result = self._client.table(table).upsert(
                data, 
                on_conflict=on_conflict
            ).execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error upserting into {table}: {e}")
            raise
    
    def delete(self, table: str, id: Any) -> bool:
        """Delete a record by ID."""
        try:
            self._client.table(table).delete().eq("id", id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting from {table} id {id}: {e}")
            return False
    
    def delete_where(self, table: str, filters: Dict[str, Any]) -> int:
        """Delete records matching filters. Returns count deleted."""
        try:
            query = self._client.table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            result = query.execute()
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"Error deleting from {table} with filters: {e}")
            return 0
    
    # =============================================================================
    # QUERY OPERATIONS
    # =============================================================================
    
    def count(self, table: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records in a table with optional filters."""
        try:
            query = self._client.table(table).select("id", count="exact")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            result = query.execute()
            return result.count or 0
        except Exception as e:
            logger.error(f"Error counting {table}: {e}")
            return 0
    
    def exists(self, table: str, filters: Dict[str, Any]) -> bool:
        """Check if any records match the filters."""
        return self.count(table, filters) > 0
    
    def query(
        self,
        table: str,
        select: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Flexible query builder."""
        try:
            select_str = ",".join(select) if select else "*"
            query = self._client.table(table).select(select_str)
            
            if filters:
                for key, value in filters.items():
                    if isinstance(value, dict):
                        # Handle complex filters like {'gte': 5}
                        for op, val in value.items():
                            if op == 'gte':
                                query = query.gte(key, val)
                            elif op == 'lte':
                                query = query.lte(key, val)
                            elif op == 'gt':
                                query = query.gt(key, val)
                            elif op == 'lt':
                                query = query.lt(key, val)
                            elif op == 'neq':
                                query = query.neq(key, val)
                            elif op == 'like':
                                query = query.like(key, val)
                            elif op == 'ilike':
                                query = query.ilike(key, val)
                            elif op == 'in':
                                query = query.in_(key, val)
                    elif value is None:
                        query = query.is_(key, "null")
                    else:
                        query = query.eq(key, value)
            
            if order_by:
                query = query.order(order_by, desc=order_desc)
            
            if limit:
                query = query.limit(limit)
            
            if offset:
                query = query.offset(offset)
            
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error querying {table}: {e}")
            return []
    
    # =============================================================================
    # ADVANCED QUERIES
    # =============================================================================
    
    def search_text(
        self, 
        table: str, 
        column: str, 
        search_term: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Full-text search on a column."""
        try:
            result = self._client.table(table).select("*").ilike(
                column, f"%{search_term}%"
            ).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error searching {table}.{column}: {e}")
            return []
    
    def execute_raw(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a raw SQL query via RPC."""
        logger.warning("execute_raw bypasses abstraction - use typed methods when possible")
        try:
            # Supabase requires RPC for raw SQL
            result = self._client.rpc("execute_sql", {"query": query}).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error executing raw query: {e}")
            return []
    
    # =============================================================================
    # TRANSACTION SUPPORT (Limited in Supabase)
    # =============================================================================
    
    def begin_transaction(self):
        """Begin a transaction (not fully supported in Supabase REST API)."""
        self._in_transaction = True
        logger.debug("Transaction started (note: Supabase REST has limited transaction support)")
    
    def commit(self):
        """Commit the current transaction."""
        self._in_transaction = False
        logger.debug("Transaction committed")
    
    def rollback(self):
        """Rollback the current transaction."""
        self._in_transaction = False
        logger.warning("Rollback called (note: Supabase REST has limited transaction support)")
    
    # =============================================================================
    # CONNECTION MANAGEMENT
    # =============================================================================
    
    def is_connected(self) -> bool:
        """Check if database connection is active."""
        try:
            # Simple health check query
            self._client.table("settings").select("key").limit(1).execute()
            return True
        except Exception:
            return False
    
    def close(self):
        """Close the database connection."""
        # Supabase client doesn't need explicit closing
        logger.debug("Supabase connection closed")


# =============================================================================
# DOMAIN-SPECIFIC REPOSITORIES
# =============================================================================

class SupabaseMeetingsRepository(MeetingsRepository):
    """Supabase implementation of MeetingsRepository."""
    
    def __init__(self, db: SupabaseDatabaseAdapter):
        self._db = db
    
    def get_meeting(self, meeting_id: int) -> Optional[Dict[str, Any]]:
        return self._db.get_by_id("meetings", meeting_id)
    
    def get_meetings(
        self, 
        limit: int = 50,
        with_signals: bool = False,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        filters = {}
        if start_date:
            filters['meeting_date'] = {'gte': start_date.isoformat()}
        if end_date:
            filters['meeting_date'] = filters.get('meeting_date', {})
            filters['meeting_date']['lte'] = end_date.isoformat()
        
        return self._db.query(
            "meetings",
            filters=filters if filters else None,
            order_by="meeting_date",
            order_desc=True,
            limit=limit
        )
    
    def create_meeting(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._db.insert("meetings", data)
    
    def update_meeting(self, meeting_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._db.update("meetings", meeting_id, data)
    
    def delete_meeting(self, meeting_id: int) -> bool:
        return self._db.delete("meetings", meeting_id)


class SupabaseDIKWRepository(DIKWRepository):
    """Supabase implementation of DIKWRepository."""
    
    def __init__(self, db: SupabaseDatabaseAdapter):
        self._db = db
    
    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        return self._db.get_by_id("dikw_items", item_id)
    
    def get_items(
        self,
        level: Optional[str] = None,
        status: str = "active",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        filters = {"status": status}
        if level:
            filters["level"] = level
        return self._db.query(
            "dikw_items",
            filters=filters,
            order_by="created_at",
            order_desc=True,
            limit=limit
        )
    
    def get_pyramid(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all items organized by DIKW level."""
        items = self.get_items(status="active", limit=500)
        pyramid = {
            "data": [],
            "information": [],
            "knowledge": [],
            "wisdom": []
        }
        for item in items:
            level = item.get("level", "data")
            if level in pyramid:
                pyramid[level].append(item)
        return pyramid
    
    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._db.insert("dikw_items", data)
    
    def update_item(self, item_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._db.update("dikw_items", item_id, data)
    
    def promote_item(self, item_id: int, to_level: str) -> Optional[Dict[str, Any]]:
        return self._db.update("dikw_items", item_id, {
            "level": to_level,
            "promoted_at": datetime.now().isoformat()
        })
    
    def delete_item(self, item_id: int) -> bool:
        # Soft delete by setting status
        result = self._db.update("dikw_items", item_id, {"status": "deleted"})
        return result is not None


class SupabaseSignalsRepository(SignalsRepository):
    """Supabase implementation of SignalsRepository."""
    
    def __init__(self, db: SupabaseDatabaseAdapter):
        self._db = db
    
    def get_feedback(
        self, 
        meeting_id: Optional[int] = None,
        signal_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        filters = {}
        if meeting_id:
            filters["meeting_id"] = meeting_id
        if signal_type:
            filters["signal_type"] = signal_type
        return self._db.query(
            "signal_feedback",
            filters=filters if filters else None,
            order_by="created_at",
            order_desc=True,
            limit=limit
        )
    
    def save_feedback(
        self, 
        meeting_id: int, 
        signal_type: str, 
        signal_text: str, 
        feedback: str
    ) -> Dict[str, Any]:
        return self._db.upsert(
            "signal_feedback",
            {
                "meeting_id": meeting_id,
                "signal_type": signal_type,
                "signal_text": signal_text,
                "feedback": feedback
            },
            conflict_columns=["meeting_id", "signal_type", "signal_text"]
        )
    
    def get_status(
        self, 
        meeting_id: int, 
        signal_type: str, 
        signal_text: str
    ) -> Optional[Dict[str, Any]]:
        results = self._db.query(
            "signal_status",
            filters={
                "meeting_id": meeting_id,
                "signal_type": signal_type,
                "signal_text": signal_text
            },
            limit=1
        )
        return results[0] if results else None
    
    def update_status(
        self, 
        meeting_id: int, 
        signal_type: str, 
        signal_text: str, 
        status: str
    ) -> Dict[str, Any]:
        return self._db.upsert(
            "signal_status",
            {
                "meeting_id": meeting_id,
                "signal_type": signal_type,
                "signal_text": signal_text,
                "status": status
            },
            conflict_columns=["meeting_id", "signal_type", "signal_text"]
        )


class SupabaseSettingsRepository(SettingsRepository):
    """Supabase implementation of SettingsRepository."""
    
    def __init__(self, db: SupabaseDatabaseAdapter):
        self._db = db
    
    def get(self, key: str, default: Any = None) -> Any:
        results = self._db.query("settings", filters={"key": key}, limit=1)
        if results:
            return results[0].get("value", default)
        return default
    
    def set(self, key: str, value: Any) -> None:
        self._db.upsert(
            "settings",
            {"key": key, "value": value},
            conflict_columns=["key"]
        )
    
    def get_all(self) -> Dict[str, Any]:
        results = self._db.get_all("settings")
        return {r["key"]: r["value"] for r in results}


class SupabaseNotificationsRepository(NotificationsRepository):
    """Supabase implementation of NotificationsRepository."""
    
    def __init__(self, db: SupabaseDatabaseAdapter):
        self._db = db
    
    def get_notifications(
        self, 
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        filters = {"dismissed": False}
        if unread_only:
            filters["read"] = False
        return self._db.query(
            "notifications",
            filters=filters,
            order_by="created_at",
            order_desc=True,
            limit=limit
        )
    
    def create_notification(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._db.insert("notifications", data)
    
    def mark_read(self, notification_id: int) -> bool:
        result = self._db.update("notifications", notification_id, {"read": True})
        return result is not None
    
    def mark_all_read(self) -> int:
        # Get unread notifications
        unread = self._db.query("notifications", filters={"read": False})
        for n in unread:
            self._db.update("notifications", n["id"], {"read": True})
        return len(unread)
    
    def delete_notification(self, notification_id: int) -> bool:
        result = self._db.update("notifications", notification_id, {"dismissed": True})
        return result is not None
