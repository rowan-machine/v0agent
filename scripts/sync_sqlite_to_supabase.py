#!/usr/bin/env python3
"""
Sync SQLite data TO Supabase.

This script migrates meetings and documents from local SQLite to Supabase
to ensure all data is in the cloud before we remove SQLite dependency.
"""

import os
import sys
import json
import sqlite3
import httpx
from datetime import datetime, timezone

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def get_supabase_client():
    """Create httpx client for Supabase REST API."""
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SECRET_KEY') or os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SECRET_KEY")
        sys.exit(1)
    
    return httpx.Client(
        base_url=f'{url}/rest/v1',
        headers={
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        },
        timeout=60.0
    )


def get_existing_supabase_meetings(client):
    """Get set of (meeting_name, meeting_date) from Supabase."""
    resp = client.get('/meetings', params={'select': 'meeting_name,meeting_date'})
    resp.raise_for_status()
    return {(m['meeting_name'], m.get('meeting_date')) for m in resp.json()}


def get_existing_supabase_documents(client):
    """Get set of source names from Supabase."""
    resp = client.get('/documents', params={'select': 'source'})
    resp.raise_for_status()
    return {d['source'] for d in resp.json()}


def sync_meetings(client, dry_run=True):
    """Sync meetings from SQLite to Supabase."""
    print("\n📅 Syncing Meetings...")
    
    # Get existing in Supabase
    existing = get_existing_supabase_meetings(client)
    print(f"   Supabase has {len(existing)} meetings")
    
    # Get all from SQLite
    conn = sqlite3.connect('agent.db')
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, meeting_name, synthesized_notes, meeting_date, 
               created_at, signals_json, raw_text, pocket_ai_summary,
               pocket_mind_map, pocket_template_type, import_source, source_url
        FROM meeting_summaries
    """).fetchall()
    print(f"   SQLite has {len(rows)} meetings")
    
    # Find missing
    to_insert = []
    for row in rows:
        key = (row['meeting_name'], row['meeting_date'])
        if key not in existing:
            # Parse signals_json
            signals = None
            if row['signals_json']:
                try:
                    signals = json.loads(row['signals_json'])
                except:
                    signals = row['signals_json']
            
            # Only include columns that exist in Supabase schema
            # Supabase columns: id, meeting_name, synthesized_notes, meeting_date,
            #                   signals, raw_text, source_document_id, user_id,
            #                   device_id, created_at, updated_at, synced_at, fts
            to_insert.append({
                'meeting_name': row['meeting_name'],
                'synthesized_notes': row['synthesized_notes'] or '',
                'meeting_date': row['meeting_date'],
                'signals': signals,
                'raw_text': row['raw_text'],
            })
    
    conn.close()
    
    print(f"   Missing from Supabase: {len(to_insert)} meetings")
    
    if not to_insert:
        print("   ✅ All meetings already synced!")
        return 0
    
    if dry_run:
        print("   [DRY RUN] Would insert:")
        for m in to_insert[:10]:
            print(f"      - {m['meeting_name']} ({m['meeting_date']})")
        if len(to_insert) > 10:
            print(f"      ... and {len(to_insert) - 10} more")
        return len(to_insert)
    
    # Insert in batches
    inserted = 0
    batch_size = 20
    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i:i+batch_size]
        try:
            resp = client.post('/meetings', json=batch)
            resp.raise_for_status()
            inserted += len(batch)
            print(f"   ✅ Inserted batch {i//batch_size + 1}: {len(batch)} meetings")
        except Exception as e:
            print(f"   ❌ Error inserting batch: {e}")
            if hasattr(resp, 'text'):
                print(f"      Response: {resp.text[:500]}")
    
    print(f"   ✅ Total inserted: {inserted} meetings")
    return inserted


def sync_documents(client, dry_run=True):
    """Sync documents from SQLite to Supabase."""
    print("\n📄 Syncing Documents...")
    
    # Get existing in Supabase
    existing = get_existing_supabase_documents(client)
    print(f"   Supabase has {len(existing)} documents")
    
    # Get all from SQLite
    conn = sqlite3.connect('agent.db')
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, source, content, document_date, created_at
        FROM docs
    """).fetchall()
    print(f"   SQLite has {len(rows)} documents")
    
    # Find missing
    to_insert = []
    for row in rows:
        if row['source'] not in existing:
            to_insert.append({
                'source': row['source'],
                'content': row['content'] or '',
                'document_date': row['document_date'],
            })
    
    conn.close()
    
    print(f"   Missing from Supabase: {len(to_insert)} documents")
    
    if not to_insert:
        print("   ✅ All documents already synced!")
        return 0
    
    if dry_run:
        print("   [DRY RUN] Would insert:")
        for d in to_insert[:10]:
            print(f"      - {d['source']} ({d['document_date']})")
        if len(to_insert) > 10:
            print(f"      ... and {len(to_insert) - 10} more")
        return len(to_insert)
    
    # Insert in batches
    inserted = 0
    batch_size = 20
    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i:i+batch_size]
        try:
            resp = client.post('/documents', json=batch)
            resp.raise_for_status()
            inserted += len(batch)
            print(f"   ✅ Inserted batch {i//batch_size + 1}: {len(batch)} documents")
        except Exception as e:
            print(f"   ❌ Error inserting batch: {e}")
    
    print(f"   ✅ Total inserted: {inserted} documents")
    return inserted


def get_existing_supabase_notifications(client):
    """Get set of notification IDs from Supabase."""
    resp = client.get('/notifications', params={'select': 'id'})
    resp.raise_for_status()
    return {n['id'] for n in resp.json()}


def sync_notifications(client, dry_run=True):
    """Sync notifications from SQLite to Supabase."""
    print("\n🔔 Syncing Notifications...")
    
    # Get existing in Supabase
    existing = get_existing_supabase_notifications(client)
    print(f"   Supabase has {len(existing)} notifications")
    
    # Get all from SQLite
    conn = sqlite3.connect('agent.db')
    conn.row_factory = sqlite3.Row
    
    # Check if notifications table exists
    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
    ).fetchone()
    
    if not table_check:
        print("   No notifications table in SQLite")
        conn.close()
        return 0
    
    rows = conn.execute("""
        SELECT id, notification_type, title, body, priority, data,
               read, created_at, actioned, action_taken, expires_at
        FROM notifications
    """).fetchall()
    print(f"   SQLite has {len(rows)} notifications")
    
    # Find missing
    to_insert = []
    for row in rows:
        if row['id'] not in existing:
            metadata = None
            if row['data']:
                try:
                    metadata = json.loads(row['data']) if isinstance(row['data'], str) else row['data']
                except:
                    metadata = {'raw': row['data']}
            
            # Supabase schema columns:
            # id, user_id, type, priority, title, body, metadata, read_at, actioned_at, action_taken, expires_at, created_at, updated_at
            # Map SQLite columns to Supabase columns
            notif = {
                'id': row['id'],
                'type': row['notification_type'],
                'title': row['title'],
                'body': row['body'],
                'priority': row['priority'] or 'normal',
                'metadata': metadata,
                'created_at': row['created_at'],
                'expires_at': row['expires_at'],
            }
            
            # Map read (boolean) -> read_at (timestamp)
            if row['read']:
                notif['read_at'] = row['created_at']  # Use created_at as approximate read time
            
            # Map actioned (boolean) -> actioned_at (timestamp)  
            if row['actioned']:
                notif['actioned_at'] = row['created_at']
                notif['action_taken'] = row['action_taken']
            
            to_insert.append(notif)
    
    conn.close()
    
    print(f"   Missing from Supabase: {len(to_insert)} notifications")
    
    if not to_insert:
        print("   ✅ All notifications already synced!")
        return 0
    
    if dry_run:
        print("   [DRY RUN] Would insert:")
        for n in to_insert[:10]:
            print(f"      - {n['title'][:50]}... (type: {n['type']})")
        if len(to_insert) > 10:
            print(f"      ... and {len(to_insert) - 10} more")
        return len(to_insert)
    
    # Insert one at a time for notifications (usually small count)
    inserted = 0
    for notif in to_insert:
        try:
            resp = client.post('/notifications', json=notif)
            resp.raise_for_status()
            inserted += 1
            print(f"   ✅ Inserted: {notif['title'][:50]}...")
        except Exception as e:
            print(f"   ❌ Error inserting notification: {e}")
            if hasattr(resp, 'text'):
                print(f"      Response: {resp.text[:500]}")
    
    print(f"   ✅ Total inserted: {inserted} notifications")
    return inserted


def get_existing_supabase_conversations(client):
    """Get set of conversation titles from Supabase."""
    resp = client.get('/conversations', params={'select': 'id,title,created_at'})
    resp.raise_for_status()
    # Return dict of title+created_at to uuid for mapping
    return {(c.get('title') or '', c.get('created_at', '')[:10]): c['id'] for c in resp.json()}


def sync_conversations(client, dry_run=True):
    """Sync conversations and messages from SQLite to Supabase."""
    print("\n💬 Syncing Conversations...")
    
    # Get existing in Supabase
    existing = get_existing_supabase_conversations(client)
    print(f"   Supabase has {len(existing)} conversations")
    
    # Get all from SQLite
    conn = sqlite3.connect('agent.db')
    conn.row_factory = sqlite3.Row
    
    # Check if conversations table exists
    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
    ).fetchone()
    
    if not table_check:
        print("   No conversations table in SQLite")
        conn.close()
        return 0
    
    conversations = conn.execute("""
        SELECT id, title, summary, created_at, archived, meeting_id, document_id
        FROM conversations
    """).fetchall()
    print(f"   SQLite has {len(conversations)} conversations")
    
    # Track SQLite ID to Supabase UUID mapping
    id_mapping = {}
    
    # Find missing conversations
    to_insert = []
    for conv in conversations:
        key = (conv['title'] or '', (conv['created_at'] or '')[:10])
        if key not in existing:
            import uuid
            new_uuid = str(uuid.uuid4())
            id_mapping[conv['id']] = new_uuid
            
            to_insert.append({
                'id': new_uuid,
                'title': conv['title'],
                'context': conv['summary'],  # Map summary to context
                'created_at': conv['created_at'],
                'archived': bool(conv['archived']) if conv['archived'] is not None else False,
                'is_active': True,
            })
        else:
            # Map existing conversation
            id_mapping[conv['id']] = existing[key]
    
    print(f"   Missing from Supabase: {len(to_insert)} conversations")
    
    if to_insert and not dry_run:
        # Insert conversations
        for conv in to_insert:
            try:
                resp = client.post('/conversations', json=conv)
                resp.raise_for_status()
                print(f"   ✅ Inserted conversation: {conv['title'][:40] if conv['title'] else '(untitled)'}...")
            except Exception as e:
                print(f"   ❌ Error inserting conversation: {e}")
                if hasattr(resp, 'text'):
                    print(f"      Response: {resp.text[:500]}")
    
    # Now sync messages
    messages = conn.execute("""
        SELECT id, conversation_id, role, content, created_at
        FROM messages
        ORDER BY conversation_id, created_at
    """).fetchall()
    conn.close()
    
    print(f"   SQLite has {len(messages)} messages")
    
    # Get existing messages
    resp = client.get('/messages', params={'select': 'id,conversation_id,created_at'})
    resp.raise_for_status()
    existing_msgs = {(m['conversation_id'], m.get('created_at', '')[:19]) for m in resp.json()}
    
    # Find missing messages
    msgs_to_insert = []
    for msg in messages:
        conv_uuid = id_mapping.get(msg['conversation_id'])
        if not conv_uuid:
            continue  # Skip if conversation wasn't mapped
        
        key = (conv_uuid, (msg['created_at'] or '')[:19])
        if key not in existing_msgs:
            import uuid
            msgs_to_insert.append({
                'id': str(uuid.uuid4()),
                'conversation_id': conv_uuid,
                'role': msg['role'],
                'content': msg['content'],
                'created_at': msg['created_at'],
            })
    
    print(f"   Missing from Supabase: {len(msgs_to_insert)} messages")
    
    if msgs_to_insert and not dry_run:
        # Insert messages in batches
        batch_size = 50
        inserted = 0
        for i in range(0, len(msgs_to_insert), batch_size):
            batch = msgs_to_insert[i:i+batch_size]
            try:
                resp = client.post('/messages', json=batch)
                resp.raise_for_status()
                inserted += len(batch)
                print(f"   ✅ Inserted batch {i//batch_size + 1}: {len(batch)} messages")
            except Exception as e:
                print(f"   ❌ Error inserting messages batch: {e}")
                if hasattr(resp, 'text'):
                    print(f"      Response: {resp.text[:500]}")
        print(f"   ✅ Total messages inserted: {inserted}")
    
    return len(to_insert)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Sync SQLite data to Supabase')
    parser.add_argument('--execute', action='store_true', help='Actually execute the sync (default is dry run)')

    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Use --execute to actually sync data")
    else:
        print("⚡ EXECUTE MODE - Will sync data to Supabase")
    
    client = get_supabase_client()
    
    try:
        meetings_synced = sync_meetings(client, dry_run=dry_run)
        docs_synced = sync_documents(client, dry_run=dry_run)
        notifications_synced = sync_notifications(client, dry_run=dry_run)
        conversations_synced = sync_conversations(client, dry_run=dry_run)
        
        print("\n" + "="*50)
        if dry_run:
            print(f"📊 DRY RUN SUMMARY:")
            print(f"   Would sync {meetings_synced} meetings")
            print(f"   Would sync {docs_synced} documents")
            print(f"   Would sync {notifications_synced} notifications")
            print(f"   Would sync {conversations_synced} conversations (with messages)")
            print("\nRun with --execute to perform the sync")
        else:
            print(f"📊 SYNC COMPLETE:")
            print(f"   Synced {meetings_synced} meetings")
            print(f"   Synced {docs_synced} documents")
            print(f"   Synced {notifications_synced} notifications")
            print(f"   Synced {conversations_synced} conversations (with messages)")
    finally:
        client.close()


if __name__ == '__main__':
    main()
