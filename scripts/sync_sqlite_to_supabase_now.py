#!/usr/bin/env python3
"""Quick script to sync SQLite meetings to Supabase."""
import json
import sqlite3
import sys
sys.path.insert(0, '/Users/rowan/v0agent/src')

from app.infrastructure.supabase_client import get_supabase_client

def main():
    conn = sqlite3.connect('/Users/rowan/v0agent/data/agent.db')
    conn.row_factory = sqlite3.Row
    
    # Get all meetings from SQLite
    meetings = conn.execute('SELECT * FROM meeting_summaries').fetchall()
    print(f'Found {len(meetings)} meetings in SQLite')
    
    client = get_supabase_client()
    if not client:
        print('ERROR: Supabase client not available')
        return
    
    # Check existing meetings in Supabase
    existing = client.table('meetings').select('meeting_name, meeting_date').execute()
    existing_keys = set((m['meeting_name'], m.get('meeting_date')) for m in existing.data)
    print(f'Found {len(existing_keys)} meetings already in Supabase')
    
    synced = 0
    errors = 0
    for m in meetings:
        key = (m['meeting_name'], m['meeting_date'])
        if key in existing_keys:
            continue
        
        # Parse signals
        signals = {}
        if m['signals_json']:
            try:
                signals = json.loads(m['signals_json'])
            except:
                pass
        
        data = {
            'meeting_name': m['meeting_name'],
            'synthesized_notes': m['synthesized_notes'] or '',
            'meeting_date': m['meeting_date'],
            'signals': signals,
            'raw_text': m['raw_text'] or '',
        }
        
        try:
            result = client.table('meetings').insert(data).execute()
            synced += 1
            if synced % 10 == 0:
                print(f'  Synced {synced} meetings...')
        except Exception as e:
            print(f'Failed to sync "{m["meeting_name"]}": {e}')
            errors += 1
    
    print(f'\n✅ Synced {synced} new meetings to Supabase')
    if errors:
        print(f'⚠️ {errors} errors')

if __name__ == '__main__':
    main()
