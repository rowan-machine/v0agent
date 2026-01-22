#!/usr/bin/env python3
"""
Complete data migration from SQLite to Supabase.
Migrates all tables with proper ID mapping and embedding sync.
"""

import sqlite3
import os
import sys
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()


def main():
    print("=" * 60)
    print("Complete SQLite → Supabase Migration")
    print("=" * 60)
    
    # Connect to SQLite
    conn = sqlite3.connect(str(project_root / 'agent.db'))
    conn.row_factory = sqlite3.Row
    
    # Connect to Supabase
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_KEY")
        sys.exit(1)
    
    from supabase import create_client
    sb = create_client(url, key)
    
    # Track ID mappings for embeddings
    id_map = {
        'meeting': {},  # sqlite_id -> supabase_uuid
        'doc': {},
        'ticket': {},
    }
    
    # ============================================================
    # 1. MIGRATE MEETINGS
    # ============================================================
    print("\n🚀 Migrating Meetings...")
    meetings = conn.execute('''
        SELECT id, meeting_name, synthesized_notes, meeting_date, raw_text, signals_json, created_at
        FROM meeting_summaries
    ''').fetchall()
    
    # Get existing Supabase meetings
    existing = sb.table('meetings').select('id, meeting_name').execute()
    existing_names = {m['meeting_name']: m['id'] for m in existing.data}
    
    migrated = 0
    for m in meetings:
        name = m['meeting_name']
        
        if name in existing_names:
            # Already exists, map the ID
            id_map['meeting'][m['id']] = existing_names[name]
        else:
            # Insert new
            try:
                signals = json.loads(m['signals_json']) if m['signals_json'] else {}
            except:
                signals = {}
            
            result = sb.table('meetings').insert({
                'meeting_name': name,
                'synthesized_notes': m['synthesized_notes'],
                'meeting_date': m['meeting_date'],
                'raw_text': m['raw_text'],
                'signals': signals,
                'created_at': m['created_at'] or datetime.now().isoformat(),
            }).execute()
            
            if result.data:
                id_map['meeting'][m['id']] = result.data[0]['id']
                migrated += 1
    
    print(f"   ✅ Migrated {migrated} new meetings (total mapped: {len(id_map['meeting'])})")
    
    # ============================================================
    # 2. MIGRATE DOCUMENTS
    # ============================================================
    print("\n🚀 Migrating Documents...")
    docs = conn.execute('''
        SELECT id, source, content, document_date, created_at
        FROM docs
    ''').fetchall()
    
    existing = sb.table('documents').select('id, source').execute()
    existing_sources = {d['source']: d['id'] for d in existing.data}
    
    migrated = 0
    for d in docs:
        source = d['source']
        
        if source in existing_sources:
            id_map['doc'][d['id']] = existing_sources[source]
        else:
            result = sb.table('documents').insert({
                'source': source,
                'content': d['content'],
                'document_date': d['document_date'],
                'created_at': d['created_at'] or datetime.now().isoformat(),
            }).execute()
            
            if result.data:
                id_map['doc'][d['id']] = result.data[0]['id']
                migrated += 1
    
    print(f"   ✅ Migrated {migrated} new documents (total mapped: {len(id_map['doc'])})")
    
    # ============================================================
    # 3. MIGRATE TICKETS
    # ============================================================
    print("\n🚀 Migrating Tickets...")
    tickets = conn.execute('''
        SELECT id, ticket_id, title, description, status, priority, 
               sprint_points, in_sprint, ai_summary, implementation_plan,
               task_decomposition, tags, created_at
        FROM tickets
    ''').fetchall()
    
    existing = sb.table('tickets').select('id, ticket_id').execute()
    existing_ids = {t['ticket_id']: t['id'] for t in existing.data}
    
    migrated = 0
    for t in tickets:
        tid = t['ticket_id']
        
        if tid in existing_ids:
            id_map['ticket'][t['id']] = existing_ids[tid]
        else:
            try:
                decomp = json.loads(t['task_decomposition']) if t['task_decomposition'] else None
            except:
                decomp = None
            
            tags = t['tags'].split(',') if t['tags'] else []
            
            result = sb.table('tickets').insert({
                'ticket_id': tid,
                'title': t['title'],
                'description': t['description'],
                'status': t['status'] or 'backlog',
                'priority': t['priority'],
                'sprint_points': t['sprint_points'] or 0,
                'in_sprint': bool(t['in_sprint']),
                'ai_summary': t['ai_summary'],
                'implementation_plan': t['implementation_plan'],
                'task_decomposition': decomp,
                'tags': tags,
                'created_at': t['created_at'] or datetime.now().isoformat(),
            }).execute()
            
            if result.data:
                id_map['ticket'][t['id']] = result.data[0]['id']
                migrated += 1
    
    print(f"   ✅ Migrated {migrated} new tickets (total mapped: {len(id_map['ticket'])})")
    
    # ============================================================
    # 4. MIGRATE CAREER DATA
    # ============================================================
    print("\n🚀 Migrating Career Data...")
    
    # Career Profile
    profile = conn.execute('SELECT * FROM career_profile LIMIT 1').fetchone()
    if profile:
        existing = sb.table('career_profiles').select('id').execute()
        if not existing.data:
            try:
                strengths = json.loads(profile['strengths']) if profile['strengths'] else []
            except:
                strengths = profile['strengths'].split(',') if profile['strengths'] else []
            
            try:
                weaknesses = json.loads(profile['weaknesses']) if profile['weaknesses'] else []
            except:
                weaknesses = profile['weaknesses'].split(',') if profile['weaknesses'] else []
            
            try:
                interests = json.loads(profile['interests']) if profile['interests'] else []
            except:
                interests = profile['interests'].split(',') if profile['interests'] else []
            
            sb.table('career_profiles').insert({
                'role_current': profile['current_role'],
                'role_target': profile['target_role'],
                'strengths': strengths,
                'weaknesses': weaknesses,
                'interests': interests,
                'goals': profile['goals'],
                'skills': {},  # Not in SQLite schema
                'years_experience': profile['years_experience'],
            }).execute()
            print("   ✅ Migrated career profile")
        else:
            print("   ⏭️ Career profile already exists")
    
    # Career Suggestions
    suggestions = conn.execute('SELECT * FROM career_suggestions').fetchall()
    existing = sb.table('career_suggestions').select('id, title').execute()
    existing_titles = {s['title'] for s in existing.data}
    
    migrated = 0
    for s in suggestions:
        if s['title'] not in existing_titles:
            sb.table('career_suggestions').insert({
                'suggestion_type': s['suggestion_type'] or 'skill_building',
                'title': s['title'],
                'description': s['description'],
                'rationale': s['rationale'],
                'difficulty': s['difficulty'],
                'time_estimate': s['time_estimate'],
                'related_goal': s['related_goal'],
                'status': s['status'] or 'active',
                'source': 'ai',  # Not in SQLite
                'created_at': s['created_at'] or datetime.now().isoformat(),
            }).execute()
            migrated += 1
    print(f"   ✅ Migrated {migrated} career suggestions")
    
    # Career Memories
    memories = conn.execute('SELECT * FROM career_memories').fetchall()
    existing = sb.table('career_memories').select('id, title').execute()
    existing_titles = {m['title'] for m in existing.data}
    
    migrated = 0
    for m in memories:
        if m['title'] not in existing_titles:
            try:
                skills = json.loads(m['skills']) if m['skills'] else []
            except:
                skills = m['skills'].split(',') if m['skills'] else []
            
            try:
                metadata = json.loads(m['metadata']) if m['metadata'] else {}
            except:
                metadata = {}
            
            sb.table('career_memories').insert({
                'memory_type': m['memory_type'] or 'learning',
                'title': m['title'],
                'description': m['description'],
                'skills': skills,
                'source_type': m['source_type'],
                'is_pinned': bool(m['is_pinned']),
                'is_ai_work': bool(m['is_ai_work']),
                'metadata': metadata,
                'created_at': m['created_at'] or datetime.now().isoformat(),
            }).execute()
            migrated += 1
    print(f"   ✅ Migrated {migrated} career memories")
    
    # ============================================================
    # 5. MIGRATE SKILLS
    # ============================================================
    print("\n🚀 Migrating Skills...")
    skills = conn.execute('SELECT * FROM skill_tracker').fetchall()
    existing = sb.table('skill_tracker').select('id, skill_name').execute()
    existing_names = {s['skill_name'] for s in existing.data}
    
    migrated = 0
    for s in skills:
        if s['skill_name'] not in existing_names:
            try:
                evidence = json.loads(s['evidence']) if s['evidence'] else []
            except:
                evidence = []
            
            sb.table('skill_tracker').insert({
                'skill_name': s['skill_name'],
                'category': s['category'] or 'general',
                'proficiency_level': s['proficiency_level'] or 0,
                'evidence': evidence,
                'projects_count': s['projects_count'] or 0,
                'tickets_count': s['tickets_count'] or 0,
                'last_used_at': s['last_used_at'],
                'created_at': s['created_at'] or datetime.now().isoformat(),
            }).execute()
            migrated += 1
    print(f"   ✅ Migrated {migrated} skills")
    
    # ============================================================
    # 6. MIGRATE STANDUPS
    # ============================================================
    print("\n🚀 Migrating Standups...")
    standups = conn.execute('SELECT * FROM standup_updates').fetchall()
    existing = sb.table('standup_updates').select('id, created_at').execute()
    existing_times = {s['created_at'] for s in existing.data}
    
    migrated = 0
    for s in standups:
        created = s['created_at']
        if created not in existing_times:
            try:
                themes = json.loads(s['key_themes']) if s['key_themes'] else []
            except:
                themes = s['key_themes'].split(',') if s['key_themes'] else []
            
            try:
                analysis = json.loads(s['ai_analysis']) if s['ai_analysis'] else None
            except:
                analysis = None
            
            sb.table('standup_updates').insert({
                'content': s['content'],
                'sentiment': s['sentiment'],
                'key_themes': themes,
                'feedback': s['feedback'],
                'ai_analysis': analysis,
                'sprint_date': s['sprint_date'],
                'created_at': created or datetime.now().isoformat(),
            }).execute()
            migrated += 1
    print(f"   ✅ Migrated {migrated} standups")
    
    # ============================================================
    # 7. MIGRATE DIKW ITEMS
    # ============================================================
    print("\n🚀 Migrating DIKW Items...")
    dikw = conn.execute('SELECT * FROM dikw_items').fetchall()
    existing = sb.table('dikw_items').select('id, content').execute()
    existing_content = {d['content'][:100] for d in existing.data}  # First 100 chars
    
    migrated = 0
    for d in dikw:
        content_key = (d['content'] or '')[:100]
        if content_key and content_key not in existing_content:
            try:
                tags = json.loads(d['tags']) if d['tags'] else []
            except:
                tags = d['tags'].split(',') if d['tags'] else []
            
            sb.table('dikw_items').insert({
                'level': d['level'] or 'data',
                'content': d['content'],
                'summary': d['summary'],
                'source_type': d['source_type'],
                'original_signal_type': d['original_signal_type'],
                'tags': tags,
                'confidence': d['confidence'] or 0.5,
                'validation_count': d['validation_count'] or 0,
                'status': d['status'] or 'active',
                'created_at': d['created_at'] or datetime.now().isoformat(),
            }).execute()
            migrated += 1
    print(f"   ✅ Migrated {migrated} DIKW items")
    
    # ============================================================
    # 8. MIGRATE ALL EMBEDDINGS
    # ============================================================
    print("\n🚀 Migrating Embeddings...")
    
    # Clear existing embeddings to avoid duplicates
    sb.table('embeddings').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    print("   🗑️ Cleared existing embeddings")
    
    embeddings = conn.execute('SELECT * FROM embeddings').fetchall()
    
    migrated = 0
    skipped = 0
    
    for e in embeddings:
        ref_type = e['ref_type']
        ref_id = e['ref_id']
        
        # Map to Supabase UUID
        supabase_ref_id = None
        supabase_ref_type = ref_type
        
        if ref_type == 'meeting':
            supabase_ref_id = id_map['meeting'].get(ref_id)
        elif ref_type == 'doc':
            supabase_ref_id = id_map['doc'].get(ref_id)
            supabase_ref_type = 'document'
        elif ref_type == 'ticket':
            supabase_ref_id = id_map['ticket'].get(ref_id)
        
        if not supabase_ref_id:
            skipped += 1
            continue
        
        vector = json.loads(e['vector'])
        
        try:
            sb.table('embeddings').insert({
                'ref_type': supabase_ref_type,
                'ref_id': supabase_ref_id,
                'model': e['model'],
                'embedding': vector,
            }).execute()
            migrated += 1
        except Exception as ex:
            print(f"   ❌ Error: {ex}")
            skipped += 1
    
    print(f"   ✅ Migrated {migrated} embeddings, skipped {skipped}")
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 60)
    print("📊 Migration Complete!")
    print("=" * 60)
    print(f"   Meetings mapped: {len(id_map['meeting'])}")
    print(f"   Documents mapped: {len(id_map['doc'])}")
    print(f"   Tickets mapped: {len(id_map['ticket'])}")
    
    conn.close()


if __name__ == "__main__":
    main()
