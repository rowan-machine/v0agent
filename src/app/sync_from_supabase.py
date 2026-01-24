"""
Sync data from Supabase to SQLite on startup.

This module handles pulling data from Supabase into the local SQLite database
for production deployments where Supabase is the source of truth.
"""

import json
import logging
import os
from typing import Dict, List, Optional

from .db import connect, table_exists
from .infrastructure.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def sync_meetings_from_supabase() -> int:
    """
    Pull meetings from Supabase and insert into local SQLite.
    
    Returns:
        Number of meetings synced
    """
    client = get_supabase_client()
    if not client:
        logger.warning("⚠️ Supabase client not available, skipping sync")
        return 0
    
    try:
        # Fetch meetings from Supabase
        response = client.table("meetings").select("*").order("created_at", desc=True).limit(100).execute()
        
        if not response.data:
            logger.info("No meetings found in Supabase")
            return 0
        
        synced = 0
        with connect() as conn:
            for meeting in response.data:
                # Convert signals JSONB to JSON string
                signals = meeting.get("signals", {})
                signals_json = json.dumps(signals) if signals else None
                
                # Check if already exists (by supabase_id in raw_text as marker)
                existing = conn.execute(
                    "SELECT id FROM meeting_summaries WHERE id = ?",
                    (meeting["id"],)
                ).fetchone()
                
                if existing:
                    continue
                
                # Map Supabase meeting to SQLite schema
                try:
                    conn.execute("""
                        INSERT INTO meeting_summaries 
                        (id, meeting_name, synthesized_notes, meeting_date, signals_json, raw_text, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        meeting["id"],  # Use UUID as string ID
                        meeting.get("meeting_name", "Untitled Meeting"),
                        meeting.get("synthesized_notes", ""),
                        meeting.get("meeting_date"),
                        signals_json,
                        meeting.get("raw_text"),
                        meeting.get("created_at"),
                    ))
                    synced += 1
                except Exception as e:
                    logger.warning(f"Failed to sync meeting {meeting.get('id')}: {e}")
            
            conn.commit()
        
        logger.info(f"✅ Synced {synced} meetings from Supabase to SQLite")
        return synced
        
    except Exception as e:
        logger.error(f"❌ Failed to sync meetings from Supabase: {e}")
        return 0


def sync_tickets_from_supabase() -> int:
    """
    Pull tickets from Supabase and insert into local SQLite.
    
    Returns:
        Number of tickets synced
    """
    client = get_supabase_client()
    if not client:
        return 0
    
    try:
        response = client.table("tickets").select("*").order("created_at", desc=True).limit(100).execute()
        
        if not response.data:
            return 0
        
        synced = 0
        with connect() as conn:
            for ticket in response.data:
                existing = conn.execute(
                    "SELECT id FROM tickets WHERE ticket_id = ?",
                    (ticket.get("ticket_id"),)
                ).fetchone()
                
                if existing:
                    continue
                
                try:
                    conn.execute("""
                        INSERT INTO tickets 
                        (ticket_id, title, description, status, priority, sprint_points, 
                         in_sprint, ai_summary, implementation_plan, task_decomposition, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticket.get("ticket_id"),
                        ticket.get("title", ""),
                        ticket.get("description"),
                        ticket.get("status", "backlog"),
                        ticket.get("priority"),
                        ticket.get("sprint_points", 0),
                        1 if ticket.get("in_sprint") else 0,
                        ticket.get("ai_summary"),
                        ticket.get("implementation_plan"),
                        json.dumps(ticket.get("task_decomposition")) if ticket.get("task_decomposition") else None,
                        ticket.get("created_at"),
                    ))
                    synced += 1
                except Exception as e:
                    logger.warning(f"Failed to sync ticket {ticket.get('ticket_id')}: {e}")
            
            conn.commit()
        
        logger.info(f"✅ Synced {synced} tickets from Supabase to SQLite")
        return synced
        
    except Exception as e:
        logger.error(f"❌ Failed to sync tickets from Supabase: {e}")
        return 0


def sync_dikw_from_supabase() -> int:
    """
    Pull DIKW items from Supabase and insert into local SQLite.
    
    Returns:
        Number of items synced
    """
    client = get_supabase_client()
    if not client:
        return 0
    
    try:
        response = client.table("dikw_items").select("*").order("created_at", desc=True).limit(200).execute()
        
        if not response.data:
            return 0
        
        synced = 0
        with connect() as conn:
            # Ensure table exists
            if not table_exists(conn, "dikw_items"):
                logger.warning("dikw_items table not found in SQLite")
                return 0
            
            for item in response.data:
                existing = conn.execute(
                    "SELECT id FROM dikw_items WHERE id = ?",
                    (item["id"],)
                ).fetchone()
                
                if existing:
                    continue
                
                try:
                    tags = item.get("tags", [])
                    tags_json = json.dumps(tags) if tags else None
                    
                    conn.execute("""
                        INSERT INTO dikw_items 
                        (id, level, content, summary, source_type, meeting_id, 
                         tags, confidence, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item["id"],
                        item.get("level", "data"),
                        item.get("content", ""),
                        item.get("summary"),
                        item.get("source_type"),
                        item.get("meeting_id"),
                        tags_json,
                        item.get("confidence", 0.5),
                        item.get("status", "active"),
                        item.get("created_at"),
                    ))
                    synced += 1
                except Exception as e:
                    logger.warning(f"Failed to sync DIKW item {item.get('id')}: {e}")
            
            conn.commit()
        
        logger.info(f"✅ Synced {synced} DIKW items from Supabase to SQLite")
        return synced
        
    except Exception as e:
        logger.error(f"❌ Failed to sync DIKW items from Supabase: {e}")
        return 0


def sync_signal_status_from_supabase() -> int:
    """
    Pull signal status from Supabase and insert into local SQLite.
    
    Returns:
        Number of items synced
    """
    client = get_supabase_client()
    if not client:
        return 0
    
    try:
        response = client.table("signal_status").select("*").order("created_at", desc=True).limit(200).execute()
        
        if not response.data:
            return 0
        
        synced = 0
        with connect() as conn:
            if not table_exists(conn, "signal_status"):
                logger.warning("signal_status table not found in SQLite")
                return 0
            
            for status in response.data:
                existing = conn.execute(
                    "SELECT id FROM signal_status WHERE id = ?",
                    (status["id"],)
                ).fetchone()
                
                if existing:
                    continue
                
                try:
                    conn.execute("""
                        INSERT INTO signal_status 
                        (id, meeting_id, signal_type, signal_text, status, 
                         converted_to, converted_ref_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        status["id"],
                        status.get("meeting_id"),
                        status.get("signal_type"),
                        status.get("signal_text"),
                        status.get("status", "pending"),
                        status.get("converted_to"),
                        status.get("converted_ref_id"),
                        status.get("created_at"),
                    ))
                    synced += 1
                except Exception as e:
                    logger.warning(f"Failed to sync signal status {status.get('id')}: {e}")
            
            conn.commit()
        
        logger.info(f"✅ Synced {synced} signal statuses from Supabase to SQLite")
        return synced
        
    except Exception as e:
        logger.error(f"❌ Failed to sync signal status from Supabase: {e}")
        return 0


def sync_all_from_supabase() -> Dict[str, int]:
    """
    Sync all data from Supabase to SQLite.
    
    Returns:
        Dict of table names to number of items synced
    """
    results = {}
    
    # Only sync in production or if explicitly enabled
    env = os.environ.get("ENVIRONMENT", "development")
    force_sync = os.environ.get("FORCE_SUPABASE_SYNC", "").lower() == "true"
    
    if env != "production" and not force_sync:
        logger.info("Skipping Supabase→SQLite sync (not in production)")
        return results
    
    logger.info("🔄 Starting Supabase → SQLite sync...")
    
    results["meetings"] = sync_meetings_from_supabase()
    results["tickets"] = sync_tickets_from_supabase()
    results["dikw_items"] = sync_dikw_from_supabase()
    results["signal_status"] = sync_signal_status_from_supabase()
    
    total = sum(results.values())
    logger.info(f"✅ Sync complete: {total} items synced from Supabase")
    
    return results
