# src/app/adapters/database/sqlite.py
"""
SQLite Database Adapter

Implements DatabasePort interface using SQLite as the backend.
This adapter is for local development or privacy-focused deployments.
"""

import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

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


class SQLiteDatabaseAdapter(DatabasePort):
    """
    SQLite implementation of DatabasePort.
    
    Uses a local SQLite file for all database operations.
    Useful for local development, testing, or privacy-focused deployments.
    """
    
    def __init__(self, db_path: str = "agent.db"):
        """
        Initialize SQLite adapter.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self._db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._in_transaction = False
        logger.info(f"SQLiteDatabaseAdapter initialized with {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with row_factory set."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            if not self._in_transaction:
                conn.close()
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite3.Row to a dictionary."""
        return dict(row) if row else {}
    
    # =============================================================================
    # GENERIC CRUD OPERATIONS
    # =============================================================================
    
    def get_by_id(self, table: str, id: Any) -> Optional[Dict[str, Any]]:
        """Get a single record by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (id,))
                row = cursor.fetchone()
                return self._row_to_dict(row) if row else None
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
            query = f"SELECT * FROM {table}"
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if value is None:
                        conditions.append(f"{key} IS NULL")
                    else:
                        conditions.append(f"{key} = ?")
                        params.append(value)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            if order_by:
                direction = "DESC" if order_desc else "ASC"
                query += f" ORDER BY {order_by} {direction}"
            
            if limit:
                query += f" LIMIT {limit}"
            
            if offset:
                query += f" OFFSET {offset}"
            
            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                return [self._row_to_dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting all from {table}: {e}")
            return []
    
    def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record and return it with generated ID."""
        try:
            # Remove None values and id if None
            clean_data = {k: v for k, v in data.items() if v is not None and k != 'id'}
            
            columns = ", ".join(clean_data.keys())
            placeholders = ", ".join(["?" for _ in clean_data])
            values = list(clean_data.values())
            
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                    values
                )
                conn.commit()
                new_id = cursor.lastrowid
                return self.get_by_id(table, new_id) or {"id": new_id, **clean_data}
        except Exception as e:
            logger.error(f"Error inserting into {table}: {e}")
            raise
    
    def insert_many(self, table: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert multiple records."""
        results = []
        for row in data:
            results.append(self.insert(table, row))
        return results
    
    def update(self, table: str, id: Any, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record by ID."""
        try:
            clean_data = {k: v for k, v in data.items() if k != 'id'}
            if not clean_data:
                return self.get_by_id(table, id)
            
            set_clause = ", ".join([f"{k} = ?" for k in clean_data.keys()])
            values = list(clean_data.values()) + [id]
            
            with self._get_connection() as conn:
                conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                conn.commit()
                return self.get_by_id(table, id)
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
            columns = list(data.keys())
            placeholders = ", ".join(["?" for _ in columns])
            column_str = ", ".join(columns)
            
            # Build ON CONFLICT clause
            conflict_str = ", ".join(conflict_columns)
            update_cols = [c for c in columns if c not in conflict_columns]
            update_str = ", ".join([f"{c} = excluded.{c}" for c in update_cols])
            
            query = f"""
                INSERT INTO {table} ({column_str}) VALUES ({placeholders})
                ON CONFLICT({conflict_str}) DO UPDATE SET {update_str}
            """
            
            with self._get_connection() as conn:
                conn.execute(query, list(data.values()))
                conn.commit()
                
                # Fetch the upserted record
                conditions = " AND ".join([f"{c} = ?" for c in conflict_columns])
                values = [data[c] for c in conflict_columns]
                cursor = conn.execute(
                    f"SELECT * FROM {table} WHERE {conditions}",
                    values
                )
                row = cursor.fetchone()
                return self._row_to_dict(row) if row else data
        except Exception as e:
            logger.error(f"Error upserting into {table}: {e}")
            raise
    
    def delete(self, table: str, id: Any) -> bool:
        """Delete a record by ID."""
        try:
            with self._get_connection() as conn:
                conn.execute(f"DELETE FROM {table} WHERE id = ?", (id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting from {table} id {id}: {e}")
            return False
    
    def delete_where(self, table: str, filters: Dict[str, Any]) -> int:
        """Delete records matching filters. Returns count deleted."""
        try:
            conditions = " AND ".join([f"{k} = ?" for k in filters.keys()])
            values = list(filters.values())
            
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"DELETE FROM {table} WHERE {conditions}",
                    values
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Error deleting from {table} with filters: {e}")
            return 0
    
    # =============================================================================
    # QUERY OPERATIONS
    # =============================================================================
    
    def count(self, table: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records in a table with optional filters."""
        try:
            query = f"SELECT COUNT(*) as count FROM {table}"
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if value is None:
                        conditions.append(f"{key} IS NULL")
                    else:
                        conditions.append(f"{key} = ?")
                        params.append(value)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                return row["count"] if row else 0
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
            select_str = ", ".join(select) if select else "*"
            query = f"SELECT {select_str} FROM {table}"
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, dict):
                        for op, val in value.items():
                            if op == 'gte':
                                conditions.append(f"{key} >= ?")
                                params.append(val)
                            elif op == 'lte':
                                conditions.append(f"{key} <= ?")
                                params.append(val)
                            elif op == 'gt':
                                conditions.append(f"{key} > ?")
                                params.append(val)
                            elif op == 'lt':
                                conditions.append(f"{key} < ?")
                                params.append(val)
                            elif op == 'neq':
                                conditions.append(f"{key} != ?")
                                params.append(val)
                            elif op == 'like':
                                conditions.append(f"{key} LIKE ?")
                                params.append(val)
                            elif op == 'ilike':
                                conditions.append(f"LOWER({key}) LIKE LOWER(?)")
                                params.append(val)
                            elif op == 'in':
                                placeholders = ", ".join(["?" for _ in val])
                                conditions.append(f"{key} IN ({placeholders})")
                                params.extend(val)
                    elif value is None:
                        conditions.append(f"{key} IS NULL")
                    else:
                        conditions.append(f"{key} = ?")
                        params.append(value)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            if order_by:
                direction = "DESC" if order_desc else "ASC"
                query += f" ORDER BY {order_by} {direction}"
            
            if limit:
                query += f" LIMIT {limit}"
            
            if offset:
                query += f" OFFSET {offset}"
            
            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                return [self._row_to_dict(row) for row in cursor.fetchall()]
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
            with self._get_connection() as conn:
                cursor = conn.execute(
                    f"SELECT * FROM {table} WHERE {column} LIKE ? LIMIT ?",
                    (f"%{search_term}%", limit)
                )
                return [self._row_to_dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error searching {table}.{column}: {e}")
            return []
    
    def execute_raw(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a raw SQL query."""
        logger.warning("execute_raw should be used sparingly")
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, params or ())
                if query.strip().upper().startswith("SELECT"):
                    return [self._row_to_dict(row) for row in cursor.fetchall()]
                conn.commit()
                return []
        except Exception as e:
            logger.error(f"Error executing raw query: {e}")
            return []
    
    # =============================================================================
    # TRANSACTION SUPPORT
    # =============================================================================
    
    def begin_transaction(self):
        """Begin a transaction."""
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row
        self._in_transaction = True
        logger.debug("Transaction started")
    
    def commit(self):
        """Commit the current transaction."""
        if self._connection:
            self._connection.commit()
            self._connection.close()
            self._connection = None
        self._in_transaction = False
        logger.debug("Transaction committed")
    
    def rollback(self):
        """Rollback the current transaction."""
        if self._connection:
            self._connection.rollback()
            self._connection.close()
            self._connection = None
        self._in_transaction = False
        logger.debug("Transaction rolled back")
    
    # =============================================================================
    # CONNECTION MANAGEMENT
    # =============================================================================
    
    def is_connected(self) -> bool:
        """Check if database connection is active."""
        return os.path.exists(self._db_path)
    
    def close(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
        logger.debug("SQLite connection closed")


# Note: Domain-specific repositories (SQLiteMeetingsRepository, etc.)
# would follow the same pattern as the Supabase repositories.
# For brevity, they can reuse the same interface and logic since
# they all use the DatabasePort abstraction.
