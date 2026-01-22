#!/usr/bin/env python3
"""
Migrate embeddings from SQLite to Supabase pgvector - Phase 5.1

This script exports embeddings from the local SQLite database 
and imports them into Supabase with pgvector.

Usage:
    # From project root
    python -m src.app.scripts.migrate_embeddings_to_supabase
    
    # Or directly
    cd /Users/rowan/v0agent
    python src/app/scripts/migrate_embeddings_to_supabase.py

Requirements:
    - SUPABASE_URL and SUPABASE_KEY environment variables set
    - Local agent.db SQLite database with embeddings table
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import hashlib

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


def get_sqlite_connection(db_path: str = None) -> sqlite3.Connection:
    """Get SQLite connection."""
    if db_path is None:
        db_path = project_root / "agent.db"
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_sqlite_embeddings(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Fetch all embeddings from SQLite."""
    cursor = conn.execute("""
        SELECT id, ref_type, ref_id, model, vector, updated_at
        FROM embeddings
    """)
    
    embeddings = []
    for row in cursor.fetchall():
        # Parse JSON vector string to list
        vector = json.loads(row["vector"])
        
        embeddings.append({
            "sqlite_id": row["id"],
            "ref_type": row["ref_type"],  # 'doc' or 'meeting'
            "ref_id": row["ref_id"],
            "model": row["model"],
            "vector": vector,
            "updated_at": row["updated_at"],
        })
    
    return embeddings


def create_id_mapping(conn: sqlite3.Connection, supabase_client) -> Dict[str, Dict[int, str]]:
    """
    Create mapping from SQLite IDs to Supabase UUIDs.
    
    This is needed because SQLite uses INTEGER IDs and Supabase uses UUIDs.
    We'll match by content hash or other unique identifiers.
    """
    mapping = {
        "meeting": {},
        "doc": {},
    }
    
    # Get meetings from SQLite
    sqlite_meetings = conn.execute("""
        SELECT id, meeting_name, synthesized_notes
        FROM meeting_summaries
    """).fetchall()
    
    # Get meetings from Supabase
    supabase_meetings = supabase_client.table("meetings").select("id, meeting_name").execute()
    
    # Match by meeting name (simple approach)
    supabase_meeting_map = {m["meeting_name"]: m["id"] for m in supabase_meetings.data}
    
    for meeting in sqlite_meetings:
        name = meeting["meeting_name"]
        if name in supabase_meeting_map:
            mapping["meeting"][meeting["id"]] = supabase_meeting_map[name]
    
    # Get docs from SQLite
    sqlite_docs = conn.execute("""
        SELECT id, source, content
        FROM docs
    """).fetchall()
    
    # Get documents from Supabase
    supabase_docs = supabase_client.table("documents").select("id, source").execute()
    
    # Match by source
    supabase_doc_map = {d["source"]: d["id"] for d in supabase_docs.data}
    
    for doc in sqlite_docs:
        source = doc["source"]
        if source in supabase_doc_map:
            mapping["doc"][doc["id"]] = supabase_doc_map[source]
    
    return mapping


def migrate_embeddings(
    embeddings: List[Dict[str, Any]],
    id_mapping: Dict[str, Dict[int, str]],
    supabase_client,
    batch_size: int = 50,
) -> Dict[str, int]:
    """
    Migrate embeddings to Supabase.
    
    Args:
        embeddings: List of embedding dicts from SQLite
        id_mapping: Mapping from SQLite IDs to Supabase UUIDs
        supabase_client: Supabase client
        batch_size: Number of embeddings to insert per batch
        
    Returns:
        Stats dict with counts
    """
    stats = {
        "total": len(embeddings),
        "migrated": 0,
        "skipped_no_mapping": 0,
        "errors": 0,
    }
    
    batch = []
    
    for emb in embeddings:
        # Map ref_type
        ref_type_map = {
            "meeting": "meeting",
            "doc": "document",  # Rename for Supabase
        }
        
        supabase_ref_type = ref_type_map.get(emb["ref_type"], emb["ref_type"])
        
        # Get Supabase UUID for the reference
        ref_uuid = id_mapping.get(emb["ref_type"], {}).get(emb["ref_id"])
        
        if not ref_uuid:
            stats["skipped_no_mapping"] += 1
            print(f"⚠️ No mapping for {emb['ref_type']}:{emb['ref_id']}")
            continue
        
        # Create content hash
        content_hash = hashlib.sha256(json.dumps(emb["vector"][:10]).encode()).hexdigest()[:16]
        
        batch.append({
            "ref_type": supabase_ref_type,
            "ref_id": ref_uuid,
            "model": emb["model"],
            "embedding": emb["vector"],
            "content_hash": content_hash,
        })
        
        # Insert batch
        if len(batch) >= batch_size:
            try:
                supabase_client.table("embeddings").insert(batch).execute()
                stats["migrated"] += len(batch)
                print(f"✅ Migrated {stats['migrated']}/{stats['total']} embeddings")
            except Exception as e:
                stats["errors"] += len(batch)
                print(f"❌ Batch insert failed: {e}")
            batch = []
    
    # Insert remaining
    if batch:
        try:
            supabase_client.table("embeddings").insert(batch).execute()
            stats["migrated"] += len(batch)
        except Exception as e:
            stats["errors"] += len(batch)
            print(f"❌ Final batch insert failed: {e}")
    
    return stats


def main():
    """Main migration function."""
    print("=" * 60)
    print("SignalFlow Embeddings Migration: SQLite → Supabase pgvector")
    print("=" * 60)
    
    # Check environment
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY environment variables required")
        print("   Set them in .env file or environment")
        sys.exit(1)
    
    print(f"📡 Supabase URL: {supabase_url}")
    
    # Connect to SQLite
    db_path = project_root / "agent.db"
    if not db_path.exists():
        print(f"❌ Error: SQLite database not found at {db_path}")
        sys.exit(1)
    
    print(f"📁 SQLite DB: {db_path}")
    
    conn = get_sqlite_connection(str(db_path))
    
    # Get embeddings from SQLite
    print("\n📊 Fetching embeddings from SQLite...")
    embeddings = get_sqlite_embeddings(conn)
    print(f"   Found {len(embeddings)} embeddings")
    
    if not embeddings:
        print("✅ No embeddings to migrate")
        return
    
    # Show embedding stats
    by_type = {}
    for emb in embeddings:
        ref_type = emb["ref_type"]
        by_type[ref_type] = by_type.get(ref_type, 0) + 1
    
    print("   By type:")
    for ref_type, count in by_type.items():
        print(f"   - {ref_type}: {count}")
    
    # Get vector dimensions
    sample_dim = len(embeddings[0]["vector"])
    print(f"   Vector dimensions: {sample_dim}")
    
    # Connect to Supabase
    print("\n📡 Connecting to Supabase...")
    try:
        from supabase import create_client
        supabase_client = create_client(supabase_url, supabase_key)
        print("   ✅ Connected")
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        sys.exit(1)
    
    # First, sync meetings and docs if not already synced
    print("\n🔗 Creating ID mappings...")
    id_mapping = create_id_mapping(conn, supabase_client)
    
    meeting_count = len(id_mapping.get("meeting", {}))
    doc_count = len(id_mapping.get("doc", {}))
    print(f"   Mapped {meeting_count} meetings")
    print(f"   Mapped {doc_count} documents")
    
    if meeting_count == 0 and doc_count == 0:
        print("\n⚠️ Warning: No ID mappings found!")
        print("   This means no meetings or documents have been synced to Supabase yet.")
        print("   Run the data migration first, then re-run this script.")
        print("\n   You can manually sync data or use the /api/admin/sync endpoint.")
        
        # Ask to continue anyway (for testing)
        response = input("\n   Continue with available mappings? [y/N]: ")
        if response.lower() != "y":
            sys.exit(0)
    
    # Migrate embeddings
    print("\n🚀 Migrating embeddings...")
    stats = migrate_embeddings(embeddings, id_mapping, supabase_client)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Migration Summary")
    print("=" * 60)
    print(f"   Total embeddings: {stats['total']}")
    print(f"   ✅ Migrated: {stats['migrated']}")
    print(f"   ⚠️ Skipped (no mapping): {stats['skipped_no_mapping']}")
    print(f"   ❌ Errors: {stats['errors']}")
    print("=" * 60)
    
    conn.close()


if __name__ == "__main__":
    main()
