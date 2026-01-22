#!/usr/bin/env python3
"""
Complete Data Migration Script - SQLite to Supabase

Migrates all data from local SQLite database to Supabase cloud:
- Meetings (meeting_summaries)
- Documents (docs)
- Tickets
- DIKW Items
- Embeddings (with pgvector conversion)
- Career Profile
- Career Suggestions
- Career Memories
- Skill Tracker
- Standup Updates
- Career Chat History

Uses service role key to bypass RLS for migration.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import hashlib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"📁 Loaded environment from {env_file}")
except ImportError:
    pass

# Supabase client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("❌ supabase package not installed. Run: pip install supabase")


def get_db_path() -> Path:
    """Get path to SQLite database."""
    return Path(__file__).parent.parent.parent.parent / "agent.db"


def connect_sqlite() -> sqlite3.Connection:
    """Connect to SQLite database."""
    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_supabase_client() -> Optional[Client]:
    """Get Supabase client with service role key."""
    if not SUPABASE_AVAILABLE:
        return None
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        print("   Set environment variables:")
        print("   export SUPABASE_URL='https://your-project.supabase.co'")
        print("   export SUPABASE_SERVICE_ROLE_KEY='your-service-role-key'")
        return None
    
    return create_client(url, key)


class DataMigrator:
    """Handles migration of all data from SQLite to Supabase."""
    
    def __init__(self, sqlite_conn: sqlite3.Connection, supabase: Client, user_id: str = None):
        self.sqlite = sqlite_conn
        self.supabase = supabase
        self.user_id = user_id
        
        # ID mapping for foreign key references
        self.id_map: Dict[str, Dict[int, str]] = {
            "meetings": {},
            "documents": {},
            "tickets": {},
            "dikw_items": {},
        }
        
        self.stats = {
            "meetings": {"migrated": 0, "skipped": 0, "errors": 0},
            "documents": {"migrated": 0, "skipped": 0, "errors": 0},
            "tickets": {"migrated": 0, "skipped": 0, "errors": 0},
            "dikw_items": {"migrated": 0, "skipped": 0, "errors": 0},
            "embeddings": {"migrated": 0, "skipped": 0, "errors": 0},
            "career_profile": {"migrated": 0, "skipped": 0, "errors": 0},
            "career_suggestions": {"migrated": 0, "skipped": 0, "errors": 0},
            "career_memories": {"migrated": 0, "skipped": 0, "errors": 0},
            "skill_tracker": {"migrated": 0, "skipped": 0, "errors": 0},
            "standup_updates": {"migrated": 0, "skipped": 0, "errors": 0},
            "career_chat": {"migrated": 0, "skipped": 0, "errors": 0},
        }
    
    def migrate_all(self) -> Dict[str, Any]:
        """Run full migration."""
        print("🚀 Starting full data migration...")
        print(f"   User ID: {self.user_id or 'None (will be null)'}")
        print()
        
        # Order matters for foreign key dependencies
        self.migrate_meetings()
        self.migrate_documents()
        self.migrate_tickets()
        self.migrate_dikw_items()
        self.migrate_embeddings()
        self.migrate_career_profile()
        self.migrate_career_suggestions()
        self.migrate_career_memories()
        self.migrate_skill_tracker()
        self.migrate_standup_updates()
        self.migrate_career_chat()
        
        return self.stats
    
    def migrate_meetings(self):
        """Migrate meeting_summaries to Supabase meetings table."""
        print("📅 Migrating meetings...")
        
        rows = self.sqlite.execute("""
            SELECT id, meeting_name, synthesized_notes, date, raw_text, signals
            FROM meeting_summaries
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Parse signals from JSON if stored as string
                signals = row["signals"]
                if isinstance(signals, str):
                    try:
                        signals = json.loads(signals)
                    except json.JSONDecodeError:
                        signals = {}
                
                # Parse date
                meeting_date = None
                if row["date"]:
                    try:
                        meeting_date = datetime.fromisoformat(row["date"].replace("Z", "+00:00")).isoformat()
                    except:
                        meeting_date = row["date"]
                
                data = {
                    "user_id": self.user_id,
                    "meeting_name": row["meeting_name"],
                    "synthesized_notes": row["synthesized_notes"],
                    "meeting_date": meeting_date,
                    "raw_text": row["raw_text"],
                    "signals": signals or {},
                    "device_id": "sqlite_migration",
                }
                
                result = self.supabase.table("meetings").insert(data).execute()
                
                if result.data:
                    self.id_map["meetings"][row["id"]] = result.data[0]["id"]
                    self.stats["meetings"]["migrated"] += 1
                else:
                    self.stats["meetings"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating meeting {row['id']}: {e}")
                self.stats["meetings"]["errors"] += 1
        
        print(f"   ✅ Meetings: {self.stats['meetings']['migrated']} migrated, {self.stats['meetings']['errors']} errors")
    
    def migrate_documents(self):
        """Migrate docs to Supabase documents table."""
        print("📄 Migrating documents...")
        
        rows = self.sqlite.execute("""
            SELECT id, source, content, date, meeting_id
            FROM docs
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Map meeting_id if it exists
                meeting_id = None
                if row["meeting_id"] and row["meeting_id"] in self.id_map["meetings"]:
                    meeting_id = self.id_map["meetings"][row["meeting_id"]]
                
                # Parse date
                doc_date = None
                if row["date"]:
                    try:
                        doc_date = datetime.fromisoformat(row["date"].replace("Z", "+00:00")).isoformat()
                    except:
                        doc_date = row["date"]
                
                data = {
                    "user_id": self.user_id,
                    "source": row["source"],
                    "content": row["content"],
                    "document_date": doc_date,
                    "meeting_id": meeting_id,
                    "device_id": "sqlite_migration",
                }
                
                result = self.supabase.table("documents").insert(data).execute()
                
                if result.data:
                    self.id_map["documents"][row["id"]] = result.data[0]["id"]
                    self.stats["documents"]["migrated"] += 1
                else:
                    self.stats["documents"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating document {row['id']}: {e}")
                self.stats["documents"]["errors"] += 1
        
        print(f"   ✅ Documents: {self.stats['documents']['migrated']} migrated, {self.stats['documents']['errors']} errors")
    
    def migrate_tickets(self):
        """Migrate tickets to Supabase."""
        print("🎫 Migrating tickets...")
        
        rows = self.sqlite.execute("""
            SELECT id, ticket_id, title, description, status, priority, 
                   sprint_points, in_sprint, ai_summary, implementation_plan,
                   task_decomposition, tags
            FROM tickets
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Parse task_decomposition
                task_decomp = row["task_decomposition"]
                if isinstance(task_decomp, str):
                    try:
                        task_decomp = json.loads(task_decomp)
                    except:
                        task_decomp = None
                
                # Parse tags
                tags = row["tags"]
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
                
                # Normalize status
                status = row["status"] or "backlog"
                if status not in ["backlog", "todo", "in_progress", "in_review", "blocked", "done"]:
                    status = "backlog"
                
                data = {
                    "user_id": self.user_id,
                    "ticket_id": row["ticket_id"],
                    "title": row["title"],
                    "description": row["description"],
                    "status": status,
                    "priority": row["priority"],
                    "sprint_points": row["sprint_points"] or 0,
                    "in_sprint": bool(row["in_sprint"]),
                    "ai_summary": row["ai_summary"],
                    "implementation_plan": row["implementation_plan"],
                    "task_decomposition": task_decomp,
                    "tags": tags if tags else None,
                    "device_id": "sqlite_migration",
                }
                
                result = self.supabase.table("tickets").insert(data).execute()
                
                if result.data:
                    self.id_map["tickets"][row["id"]] = result.data[0]["id"]
                    self.stats["tickets"]["migrated"] += 1
                else:
                    self.stats["tickets"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating ticket {row['id']}: {e}")
                self.stats["tickets"]["errors"] += 1
        
        print(f"   ✅ Tickets: {self.stats['tickets']['migrated']} migrated, {self.stats['tickets']['errors']} errors")
    
    def migrate_dikw_items(self):
        """Migrate DIKW items to Supabase."""
        print("🔺 Migrating DIKW items...")
        
        rows = self.sqlite.execute("""
            SELECT id, level, content, summary, source_type, original_signal_type,
                   meeting_id, tags, confidence, validation_count, status
            FROM dikw_items
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Map meeting_id
                meeting_id = None
                if row["meeting_id"] and row["meeting_id"] in self.id_map["meetings"]:
                    meeting_id = self.id_map["meetings"][row["meeting_id"]]
                
                # Parse tags
                tags = row["tags"]
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
                
                # Normalize level
                level = row["level"]
                if level not in ["data", "information", "knowledge", "wisdom"]:
                    level = "data"
                
                # Normalize status
                status = row["status"] or "active"
                if status not in ["active", "archived", "merged"]:
                    status = "active"
                
                data = {
                    "user_id": self.user_id,
                    "level": level,
                    "content": row["content"],
                    "summary": row["summary"],
                    "source_type": row["source_type"],
                    "original_signal_type": row["original_signal_type"],
                    "meeting_id": meeting_id,
                    "tags": tags if tags else None,
                    "confidence": row["confidence"] or 0.5,
                    "validation_count": row["validation_count"] or 0,
                    "status": status,
                }
                
                result = self.supabase.table("dikw_items").insert(data).execute()
                
                if result.data:
                    self.id_map["dikw_items"][row["id"]] = result.data[0]["id"]
                    self.stats["dikw_items"]["migrated"] += 1
                else:
                    self.stats["dikw_items"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating DIKW item {row['id']}: {e}")
                self.stats["dikw_items"]["errors"] += 1
        
        print(f"   ✅ DIKW items: {self.stats['dikw_items']['migrated']} migrated, {self.stats['dikw_items']['errors']} errors")
    
    def migrate_embeddings(self):
        """Migrate embeddings to Supabase with pgvector."""
        print("🧮 Migrating embeddings...")
        
        rows = self.sqlite.execute("""
            SELECT id, ref_type, ref_id, model, vector, updated_at
            FROM embeddings
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Map ref_id based on ref_type
                ref_id = None
                if row["ref_type"] == "meeting" and row["ref_id"] in self.id_map["meetings"]:
                    ref_id = self.id_map["meetings"][row["ref_id"]]
                elif row["ref_type"] == "doc" and row["ref_id"] in self.id_map["documents"]:
                    ref_id = self.id_map["documents"][row["ref_id"]]
                elif row["ref_type"] == "document" and row["ref_id"] in self.id_map["documents"]:
                    ref_id = self.id_map["documents"][row["ref_id"]]
                
                if not ref_id:
                    self.stats["embeddings"]["skipped"] += 1
                    continue
                
                # Parse vector from JSON string
                vector = row["vector"]
                if isinstance(vector, str):
                    try:
                        vector = json.loads(vector)
                    except:
                        self.stats["embeddings"]["errors"] += 1
                        continue
                
                # Ensure it's a list of floats
                if not isinstance(vector, list) or len(vector) != 1536:
                    print(f"   ⚠️ Invalid vector dimension for embedding {row['id']}: {len(vector) if isinstance(vector, list) else 'not a list'}")
                    self.stats["embeddings"]["skipped"] += 1
                    continue
                
                # Generate content hash
                content_hash = hashlib.md5(str(vector[:10]).encode()).hexdigest()
                
                data = {
                    "user_id": self.user_id,
                    "ref_type": row["ref_type"],
                    "ref_id": ref_id,
                    "model": row["model"] or "text-embedding-3-small",
                    "embedding": vector,  # pgvector accepts list directly
                    "content_hash": content_hash,
                }
                
                result = self.supabase.table("embeddings").insert(data).execute()
                
                if result.data:
                    self.stats["embeddings"]["migrated"] += 1
                else:
                    self.stats["embeddings"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating embedding {row['id']}: {e}")
                self.stats["embeddings"]["errors"] += 1
        
        print(f"   ✅ Embeddings: {self.stats['embeddings']['migrated']} migrated, {self.stats['embeddings']['skipped']} skipped, {self.stats['embeddings']['errors']} errors")
    
    def migrate_career_profile(self):
        """Migrate career profile to Supabase."""
        print("👤 Migrating career profile...")
        
        row = self.sqlite.execute("""
            SELECT current_role, target_role, strengths, weaknesses, 
                   interests, goals, years_experience
            FROM career_profile
            WHERE id = 1
        """).fetchone()
        
        if not row:
            print("   ⚠️ No career profile found")
            return
        
        try:
            # Parse arrays from comma-separated strings
            strengths = row["strengths"]
            if isinstance(strengths, str):
                strengths = [s.strip() for s in strengths.split(",") if s.strip()]
            
            weaknesses = row["weaknesses"]
            if isinstance(weaknesses, str):
                weaknesses = [w.strip() for w in weaknesses.split(",") if w.strip()]
            
            interests = row["interests"]
            if isinstance(interests, str):
                interests = [i.strip() for i in interests.split(",") if i.strip()]
            
            data = {
                "user_id": self.user_id,
                "role_current": row["current_role"],
                "role_target": row["target_role"],
                "strengths": strengths if strengths else None,
                "weaknesses": weaknesses if weaknesses else None,
                "interests": interests if interests else None,
                "goals": row["goals"],
                "years_experience": row["years_experience"],
            }
            
            # Check if profile exists
            existing = self.supabase.table("career_profiles").select("id").eq("user_id", self.user_id).execute()
            
            if existing.data:
                # Update existing
                result = self.supabase.table("career_profiles").update(data).eq("user_id", self.user_id).execute()
            else:
                result = self.supabase.table("career_profiles").insert(data).execute()
            
            if result.data:
                self.stats["career_profile"]["migrated"] += 1
            else:
                self.stats["career_profile"]["errors"] += 1
                
        except Exception as e:
            print(f"   ❌ Error migrating career profile: {e}")
            self.stats["career_profile"]["errors"] += 1
        
        print(f"   ✅ Career profile: {self.stats['career_profile']['migrated']} migrated")
    
    def migrate_career_suggestions(self):
        """Migrate career suggestions to Supabase."""
        print("💡 Migrating career suggestions...")
        
        rows = self.sqlite.execute("""
            SELECT suggestion_type, title, description, rationale, 
                   difficulty, time_estimate, related_goal, status, source
            FROM career_suggestions
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Normalize suggestion_type
                sug_type = row["suggestion_type"] or "learning"
                if sug_type not in ["stretch", "skill_building", "project", "learning"]:
                    sug_type = "learning"
                
                # Normalize difficulty
                difficulty = row["difficulty"]
                if difficulty not in ["beginner", "intermediate", "advanced"]:
                    difficulty = None
                
                # Normalize status
                status = row["status"] or "active"
                if status not in ["active", "accepted", "rejected", "completed"]:
                    status = "active"
                
                data = {
                    "user_id": self.user_id,
                    "suggestion_type": sug_type,
                    "title": row["title"],
                    "description": row["description"],
                    "rationale": row["rationale"],
                    "difficulty": difficulty,
                    "time_estimate": row["time_estimate"],
                    "related_goal": row["related_goal"],
                    "status": status,
                    "source": row["source"] or "ai",
                }
                
                result = self.supabase.table("career_suggestions").insert(data).execute()
                
                if result.data:
                    self.stats["career_suggestions"]["migrated"] += 1
                else:
                    self.stats["career_suggestions"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating suggestion: {e}")
                self.stats["career_suggestions"]["errors"] += 1
        
        print(f"   ✅ Career suggestions: {self.stats['career_suggestions']['migrated']} migrated")
    
    def migrate_career_memories(self):
        """Migrate career memories to Supabase."""
        print("🧠 Migrating career memories...")
        
        rows = self.sqlite.execute("""
            SELECT memory_type, title, description, skills, source_type,
                   is_pinned, is_ai_work
            FROM career_memories
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Normalize memory_type
                mem_type = row["memory_type"] or "learning"
                if mem_type not in ["completed_project", "ai_implementation", "skill_milestone", "achievement", "learning"]:
                    mem_type = "learning"
                
                # Parse skills
                skills = row["skills"]
                if isinstance(skills, str):
                    skills = [s.strip() for s in skills.split(",") if s.strip()]
                
                data = {
                    "user_id": self.user_id,
                    "memory_type": mem_type,
                    "title": row["title"],
                    "description": row["description"],
                    "skills": skills if skills else None,
                    "source_type": row["source_type"],
                    "is_pinned": bool(row["is_pinned"]),
                    "is_ai_work": bool(row["is_ai_work"]),
                }
                
                result = self.supabase.table("career_memories").insert(data).execute()
                
                if result.data:
                    self.stats["career_memories"]["migrated"] += 1
                else:
                    self.stats["career_memories"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating memory: {e}")
                self.stats["career_memories"]["errors"] += 1
        
        print(f"   ✅ Career memories: {self.stats['career_memories']['migrated']} migrated")
    
    def migrate_skill_tracker(self):
        """Migrate skill tracker to Supabase."""
        print("📊 Migrating skill tracker...")
        
        rows = self.sqlite.execute("""
            SELECT skill_name, category, proficiency_level, evidence,
                   projects_count, tickets_count, last_used_at
            FROM skill_tracker
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Parse evidence
                evidence = row["evidence"]
                if isinstance(evidence, str):
                    try:
                        evidence = json.loads(evidence)
                    except:
                        evidence = []
                
                data = {
                    "user_id": self.user_id,
                    "skill_name": row["skill_name"],
                    "category": row["category"] or "general",
                    "proficiency_level": row["proficiency_level"] or 0,
                    "evidence": evidence if evidence else [],
                    "projects_count": row["projects_count"] or 0,
                    "tickets_count": row["tickets_count"] or 0,
                    "last_used_at": row["last_used_at"],
                }
                
                result = self.supabase.table("skill_tracker").insert(data).execute()
                
                if result.data:
                    self.stats["skill_tracker"]["migrated"] += 1
                else:
                    self.stats["skill_tracker"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating skill: {e}")
                self.stats["skill_tracker"]["errors"] += 1
        
        print(f"   ✅ Skill tracker: {self.stats['skill_tracker']['migrated']} migrated")
    
    def migrate_standup_updates(self):
        """Migrate standup updates to Supabase."""
        print("📝 Migrating standup updates...")
        
        rows = self.sqlite.execute("""
            SELECT content, sentiment, key_themes, feedback, date
            FROM standup_updates
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                # Parse key_themes
                themes = row["key_themes"]
                if isinstance(themes, str):
                    try:
                        themes = json.loads(themes)
                    except:
                        themes = [t.strip() for t in themes.split(",") if t.strip()]
                
                # Normalize sentiment
                sentiment = row["sentiment"]
                if sentiment not in ["positive", "neutral", "blocked", "struggling"]:
                    sentiment = None
                
                data = {
                    "user_id": self.user_id,
                    "content": row["content"],
                    "sentiment": sentiment,
                    "key_themes": themes if themes else None,
                    "feedback": row["feedback"],
                    "sprint_date": row["date"],
                }
                
                result = self.supabase.table("standup_updates").insert(data).execute()
                
                if result.data:
                    self.stats["standup_updates"]["migrated"] += 1
                else:
                    self.stats["standup_updates"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating standup: {e}")
                self.stats["standup_updates"]["errors"] += 1
        
        print(f"   ✅ Standup updates: {self.stats['standup_updates']['migrated']} migrated")
    
    def migrate_career_chat(self):
        """Migrate career chat history to Supabase."""
        print("💬 Migrating career chat history...")
        
        rows = self.sqlite.execute("""
            SELECT message, response, summary
            FROM career_chat_updates
            ORDER BY id
        """).fetchall()
        
        for row in rows:
            try:
                data = {
                    "user_id": self.user_id,
                    "message": row["message"],
                    "response": row["response"],
                    "summary": row["summary"],
                }
                
                result = self.supabase.table("career_chat_updates").insert(data).execute()
                
                if result.data:
                    self.stats["career_chat"]["migrated"] += 1
                else:
                    self.stats["career_chat"]["errors"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error migrating chat: {e}")
                self.stats["career_chat"]["errors"] += 1
        
        print(f"   ✅ Career chat: {self.stats['career_chat']['migrated']} migrated")


def main():
    """Run the migration."""
    print("=" * 60)
    print("SQLite to Supabase Data Migration")
    print("=" * 60)
    print()
    
    # Check database exists
    db_path = get_db_path()
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print(f"📂 Source: {db_path}")
    
    # Connect to SQLite
    sqlite_conn = connect_sqlite()
    
    # Get Supabase client
    supabase = get_supabase_client()
    if not supabase:
        return
    
    print(f"☁️  Target: Supabase (using service role key)")
    print()
    
    # Get user ID if available
    user_id = os.environ.get("SUPABASE_USER_ID")
    if not user_id:
        print("⚠️  SUPABASE_USER_ID not set - data will have null user_id")
        print("   Set with: export SUPABASE_USER_ID='your-user-uuid'")
        print()
    
    # Confirm migration
    print("This will migrate data from SQLite to Supabase.")
    print("Existing Supabase data will NOT be deleted, but may cause duplicates.")
    print()
    
    response = input("Proceed with migration? [y/N] ").strip().lower()
    if response != "y":
        print("Migration cancelled.")
        return
    
    print()
    
    # Run migration
    migrator = DataMigrator(sqlite_conn, supabase, user_id)
    stats = migrator.migrate_all()
    
    # Print summary
    print()
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    
    total_migrated = 0
    total_errors = 0
    
    for table, counts in stats.items():
        migrated = counts.get("migrated", 0)
        errors = counts.get("errors", 0)
        skipped = counts.get("skipped", 0)
        total_migrated += migrated
        total_errors += errors
        
        status = "✅" if errors == 0 else "⚠️"
        print(f"  {status} {table}: {migrated} migrated", end="")
        if skipped:
            print(f", {skipped} skipped", end="")
        if errors:
            print(f", {errors} errors", end="")
        print()
    
    print()
    print(f"Total: {total_migrated} records migrated, {total_errors} errors")
    
    if total_errors == 0:
        print("✅ Migration completed successfully!")
    else:
        print("⚠️  Migration completed with some errors. Check logs above.")
    
    sqlite_conn.close()


if __name__ == "__main__":
    main()
