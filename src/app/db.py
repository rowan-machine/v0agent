import sqlite3

DB_PATH = "agent.db"

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS meeting_summaries (
  id INTEGER PRIMARY KEY,
  meeting_name TEXT NOT NULL,
  synthesized_notes TEXT NOT NULL,
  meeting_date TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  signals_json TEXT,
  source_document_id INTEGER,
  raw_text TEXT,
  pocket_ai_summary TEXT,
  pocket_mind_map TEXT,
  pocket_template_type TEXT,
  import_source TEXT,              -- 'manual', 'markdown_upload', 'pocket', 'api'
  source_url TEXT,                 -- Original source URL (e.g., Pocket link)
  FOREIGN KEY (source_document_id) REFERENCES docs(id) ON DELETE SET NULL
);

-- Meeting screenshots/images with AI-generated summaries
CREATE TABLE IF NOT EXISTS meeting_screenshots (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER NOT NULL,
  filename TEXT NOT NULL,
  content_type TEXT NOT NULL,
  image_summary TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (meeting_id) REFERENCES meeting_summaries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_screenshots_meeting ON meeting_screenshots(meeting_id);

CREATE TABLE IF NOT EXISTS docs (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  content TEXT NOT NULL,
  document_date TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS embeddings (
  id INTEGER PRIMARY KEY,
  ref_type TEXT NOT NULL,         -- 'doc' | 'meeting'
  ref_id INTEGER NOT NULL,
  model TEXT NOT NULL,
  vector TEXT NOT NULL,           -- JSON array of floats
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(ref_type, ref_id, model)
);

CREATE INDEX IF NOT EXISTS idx_embeddings_ref ON embeddings(ref_type, ref_id);
CREATE INDEX IF NOT EXISTS idx_docs_document_date ON docs(document_date);
CREATE INDEX IF NOT EXISTS idx_meetings_meeting_date ON meeting_summaries(meeting_date);
Create INDEX IF NOT EXISTS idx_docs_content ON docs(LOWER(content));
CREATE INDEX IF NOT EXISTS idx_meetings_notes ON meeting_summaries(LOWER(synthesized_notes));
Create INDEX IF NOT EXISTS idx_docs_source ON docs(LOWER(source));
CREATE INDEX IF NOT EXISTS idx_meetings_name ON meeting_summaries(LOWER(meeting_name));

-- Conversation Mindmaps - Store mindmap data from conversations with hierarchy
CREATE TABLE IF NOT EXISTS conversation_mindmaps (
  id INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL,
  mindmap_json TEXT NOT NULL,
  hierarchy_levels INTEGER,
  root_node_id TEXT,
  node_count INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conv_mindmaps_conversation_id ON conversation_mindmaps(conversation_id);

-- Mindmap Syntheses - AI-generated synthesis of all mindmaps
CREATE TABLE IF NOT EXISTS mindmap_syntheses (
  id INTEGER PRIMARY KEY,
  synthesis_text TEXT NOT NULL,
  hierarchy_summary TEXT,
  source_mindmap_ids TEXT,
  source_conversation_ids TEXT,
  key_topics TEXT,
  relationships TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mindmap_syntheses_updated ON mindmap_syntheses(updated_at);

-- Mindmap Synthesis History - Track evolution of syntheses
CREATE TABLE IF NOT EXISTS mindmap_synthesis_history (
  id INTEGER PRIMARY KEY,
  synthesis_id INTEGER NOT NULL,
  previous_text TEXT,
  changes_summary TEXT,
  triggered_by TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (synthesis_id) REFERENCES mindmap_syntheses(id) ON DELETE CASCADE
);

-- Workflow modes configuration
CREATE TABLE IF NOT EXISTS workflow_modes (
  id INTEGER PRIMARY KEY,
  mode_key TEXT NOT NULL UNIQUE,    -- e.g., 'mode-a', 'mode-b'
  name TEXT NOT NULL,               -- e.g., 'Context Distillation'
  icon TEXT DEFAULT '🎯',           -- emoji icon
  short_description TEXT,           -- brief summary for mode cards
  description TEXT,                 -- detailed description/subtitle
  steps_json TEXT,                  -- JSON array of checklist steps
  sort_order INTEGER DEFAULT 0,     -- display order
  is_active INTEGER DEFAULT 1,      -- whether mode is enabled
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_modes_key ON workflow_modes(mode_key);
CREATE INDEX IF NOT EXISTS idx_workflow_modes_order ON workflow_modes(sort_order);

-- Sprint settings (singleton row)
CREATE TABLE IF NOT EXISTS sprint_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  sprint_start_date TEXT NOT NULL,
  sprint_length_days INTEGER DEFAULT 14,
  sprint_name TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Assigned tickets with details and AI summaries
CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY,
  ticket_id TEXT NOT NULL UNIQUE,  -- e.g. JIRA-1234
  title TEXT NOT NULL,
  description TEXT,                 -- pasted ticket details
  status TEXT DEFAULT 'backlog',       -- backlog, todo, in_progress, in_review, blocked, done, complete
  priority TEXT,
  sprint_points INTEGER DEFAULT 0,  -- story points for sprint tracking
  in_sprint INTEGER DEFAULT 1,      -- 1 if assigned to current sprint
  ai_summary TEXT,                  -- AI-generated summary
  implementation_plan TEXT,         -- AI-generated or user-edited plan
  task_decomposition TEXT,          -- JSON array of subtasks
  tags TEXT,                        -- comma-separated tags
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Attachments (screenshots, files) for meetings, docs, tickets
CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY,
  ref_type TEXT NOT NULL,           -- 'meeting' | 'doc' | 'ticket'
  ref_id INTEGER NOT NULL,
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL,
  mime_type TEXT,
  file_size INTEGER,
  ai_description TEXT,              -- AI-generated description for chat context
  tags TEXT,                        -- comma-separated tags
  created_at TEXT DEFAULT (datetime('now'))
);

-- Signal feedback for thumbs up/down validation
CREATE TABLE IF NOT EXISTS signal_feedback (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER NOT NULL,
  signal_type TEXT NOT NULL,        -- 'decision' | 'action_item' | 'blocker' | 'risk' | 'idea'
  signal_text TEXT NOT NULL,
  feedback TEXT NOT NULL,           -- 'up' | 'down'
  include_in_chat INTEGER DEFAULT 1, -- whether to include in chat context
  notes TEXT,                       -- optional user notes
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(meeting_id, signal_type, signal_text)
);

CREATE INDEX IF NOT EXISTS idx_signal_feedback_meeting ON signal_feedback(meeting_id);
CREATE INDEX IF NOT EXISTS idx_signal_feedback_type ON signal_feedback(signal_type);

CREATE INDEX IF NOT EXISTS idx_tickets_ticket_id ON tickets(ticket_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_attachments_ref ON attachments(ref_type, ref_id);

-- Settings table for user preferences
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Import history tracking (F1: Pocket Import Pipeline)
CREATE TABLE IF NOT EXISTS import_history (
  id INTEGER PRIMARY KEY,
  filename TEXT NOT NULL,
  file_type TEXT NOT NULL,          -- 'md', 'txt', 'pdf', 'docx'
  meeting_id INTEGER,               -- Reference to created meeting (if successful)
  status TEXT DEFAULT 'pending',    -- 'pending', 'processing', 'completed', 'failed'
  error_message TEXT,               -- Error details if failed
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (meeting_id) REFERENCES meeting_summaries(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_import_history_status ON import_history(status);
CREATE INDEX IF NOT EXISTS idx_import_history_created ON import_history(created_at DESC);

-- Meeting documents: linked transcripts and summaries from multiple sources (F1b: Pocket Bundle)
-- Supports Teams transcript + Pocket transcript, Teams summary + Pocket summary
-- All documents get embeddings for holistic search
CREATE TABLE IF NOT EXISTS meeting_documents (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER NOT NULL,
  doc_type TEXT NOT NULL,           -- 'transcript' | 'summary' | 'notes'
  source TEXT NOT NULL,             -- 'teams' | 'pocket' | 'manual' | 'zoom' | 'other'
  content TEXT NOT NULL,            -- the actual transcript or summary text
  format TEXT,                      -- 'markdown' | 'txt' | 'pdf' | 'docx'
  signals_json TEXT,                -- extracted signals from this specific document
  file_path TEXT,                   -- if uploaded as file, path to original
  metadata_json TEXT,               -- additional metadata (e.g., duration, speaker count)
  is_primary INTEGER DEFAULT 0,     -- 1 if this is the primary source for this doc_type
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (meeting_id) REFERENCES meeting_summaries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_meeting_documents_meeting ON meeting_documents(meeting_id);
CREATE INDEX IF NOT EXISTS idx_meeting_documents_type ON meeting_documents(doc_type, source);

-- Signal status tracking (approve/reject/archive/complete)
CREATE TABLE IF NOT EXISTS signal_status (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER NOT NULL,
  signal_type TEXT NOT NULL,        -- 'decision' | 'action_item' | 'blocker' | 'risk' | 'idea'
  signal_text TEXT NOT NULL,
  status TEXT DEFAULT 'pending',    -- 'pending' | 'approved' | 'rejected' | 'archived' | 'completed'
  converted_to TEXT,                -- 'ticket' if converted to action item/ticket
  converted_ref_id INTEGER,         -- reference to ticket.id if converted
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(meeting_id, signal_type, signal_text)
);

CREATE INDEX IF NOT EXISTS idx_signal_status_meeting ON signal_status(meeting_id);
CREATE INDEX IF NOT EXISTS idx_signal_status_status ON signal_status(status);

-- AI memory items (approved AI responses saved for context)
CREATE TABLE IF NOT EXISTS ai_memory (
  id INTEGER PRIMARY KEY,
  source_type TEXT NOT NULL,        -- 'quick_ask' | 'chat' | 'summary'
  source_query TEXT,                -- original question/topic
  content TEXT NOT NULL,            -- AI response content
  status TEXT DEFAULT 'approved',   -- 'approved' | 'rejected' | 'archived'
  tags TEXT,                        -- comma-separated tags
  importance INTEGER DEFAULT 5,     -- 1-10 importance for retrieval
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ai_memory_status ON ai_memory(status);
CREATE INDEX IF NOT EXISTS idx_ai_memory_source ON ai_memory(source_type);

-- DIKW Pyramid: Data → Information → Knowledge → Wisdom
-- Signals get promoted through these levels as they are validated and synthesized
CREATE TABLE IF NOT EXISTS dikw_items (
  id INTEGER PRIMARY KEY,
  level TEXT NOT NULL,              -- 'data' | 'information' | 'knowledge' | 'wisdom'
  content TEXT NOT NULL,            -- the actual content/insight
  summary TEXT,                     -- AI-generated summary for this level
  source_type TEXT,                 -- 'signal' | 'ai_memory' | 'manual' | 'synthesis'
  source_ref_ids TEXT,              -- JSON array of source IDs that contributed to this item
  original_signal_type TEXT,        -- if from signal: 'decision' | 'action' | 'blocker' | 'risk' | 'idea'
  meeting_id INTEGER,               -- reference to original meeting if from signal
  tags TEXT,                        -- comma-separated tags for categorization
  confidence REAL DEFAULT 0.5,      -- 0-1 confidence score based on validations
  validation_count INTEGER DEFAULT 0, -- how many times validated/approved
  promoted_to INTEGER,              -- id of the item this was promoted to (next level)
  promoted_at TEXT,                 -- when it was promoted
  status TEXT DEFAULT 'active',     -- 'active' | 'archived' | 'merged'
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dikw_level ON dikw_items(level);
CREATE INDEX IF NOT EXISTS idx_dikw_status ON dikw_items(status);
CREATE INDEX IF NOT EXISTS idx_dikw_source ON dikw_items(source_type);
CREATE INDEX IF NOT EXISTS idx_dikw_meeting ON dikw_items(meeting_id);

-- DIKW item evolution history - tracks the journey from Data to Wisdom
CREATE TABLE IF NOT EXISTS dikw_evolution (
  id INTEGER PRIMARY KEY,
  item_id INTEGER NOT NULL,         -- the DIKW item being tracked
  event_type TEXT NOT NULL,         -- 'created' | 'promoted' | 'merged' | 'edited'
  from_level TEXT,                  -- level before (null for created)
  to_level TEXT NOT NULL,           -- level after
  source_meeting_id INTEGER,        -- meeting that sourced this
  source_meeting_name TEXT,         -- cached meeting name
  source_document_id INTEGER,       -- document that sourced this
  source_document_name TEXT,        -- cached document name
  source_item_ids TEXT,             -- JSON array of item IDs that contributed (for merges)
  content_snapshot TEXT,            -- snapshot of content at this point
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dikw_evolution_item ON dikw_evolution(item_id);
CREATE INDEX IF NOT EXISTS idx_dikw_evolution_type ON dikw_evolution(event_type);

-- Entity links for knowledge graph connections (P5.10)
-- Stores relationships between any two entities (meetings, documents, tickets, dikw_items, signals)
CREATE TABLE IF NOT EXISTS entity_links (
  id INTEGER PRIMARY KEY,
  source_type TEXT NOT NULL,        -- 'meeting' | 'document' | 'ticket' | 'dikw' | 'signal'
  source_id INTEGER NOT NULL,       -- ID of the source entity
  target_type TEXT NOT NULL,        -- 'meeting' | 'document' | 'ticket' | 'dikw' | 'signal'
  target_id INTEGER NOT NULL,       -- ID of the target entity
  link_type TEXT NOT NULL,          -- 'semantic_similar' | 'related' | 'derived_from' | 'referenced' | 'same_topic' | 'blocks' | 'depends_on'
  similarity_score REAL,            -- 0.0-1.0 for semantic links
  confidence REAL DEFAULT 0.5,      -- confidence in the link (0.0-1.0)
  is_bidirectional INTEGER DEFAULT 1,  -- 1 if link applies both ways
  metadata TEXT,                    -- JSON for additional link metadata
  created_by TEXT DEFAULT 'system', -- 'system' | 'user' | 'ai'
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(source_type, source_id, target_type, target_id, link_type)
);

CREATE INDEX IF NOT EXISTS idx_entity_links_source ON entity_links(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_target ON entity_links(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_type ON entity_links(link_type);
CREATE INDEX IF NOT EXISTS idx_entity_links_similarity ON entity_links(similarity_score);

-- Mode time tracking for productivity analytics
CREATE TABLE IF NOT EXISTS mode_sessions (
  id INTEGER PRIMARY KEY,
  mode TEXT NOT NULL,               -- 'grooming' | 'planning' | 'standup' | 'implementation'
  started_at TEXT NOT NULL,
  ended_at TEXT,
  duration_seconds INTEGER,         -- calculated when session ends
  date TEXT NOT NULL,               -- YYYY-MM-DD for daily aggregation
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_mode_sessions_mode ON mode_sessions(mode);
CREATE INDEX IF NOT EXISTS idx_mode_sessions_date ON mode_sessions(date);

-- Archived mode sessions (for completed sprints)
CREATE TABLE IF NOT EXISTS archived_mode_sessions (
  id INTEGER PRIMARY KEY,
  original_id INTEGER,              -- original mode_sessions id
  mode TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  duration_seconds INTEGER,
  date TEXT NOT NULL,
  notes TEXT,
  sprint_name TEXT,                 -- name of the sprint when archived
  sprint_start_date TEXT,           -- start date of the archived sprint
  sprint_end_date TEXT,             -- end date of the archived sprint
  archived_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_archived_sessions_mode ON archived_mode_sessions(mode);
CREATE INDEX IF NOT EXISTS idx_archived_sessions_sprint ON archived_mode_sessions(sprint_name);
CREATE INDEX IF NOT EXISTS idx_archived_sessions_date ON archived_mode_sessions(date);

-- Mode statistics (calculated periodically)
CREATE TABLE IF NOT EXISTS mode_statistics (
  id INTEGER PRIMARY KEY,
  mode TEXT NOT NULL,
  stat_type TEXT NOT NULL,          -- 'daily_avg' | 'weekly_avg' | 'total'
  period TEXT,                      -- date or week identifier
  total_seconds INTEGER DEFAULT 0,
  session_count INTEGER DEFAULT 0,
  avg_session_seconds INTEGER DEFAULT 0,
  calculated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(mode, stat_type, period)
);

CREATE INDEX IF NOT EXISTS idx_mode_stats_mode ON mode_statistics(mode);

-- User status (AI-interpreted free-form status)
CREATE TABLE IF NOT EXISTS user_status (
  id INTEGER PRIMARY KEY,
  status_text TEXT NOT NULL,
  interpreted_mode TEXT,
  interpreted_activity TEXT,
  interpreted_context TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  is_current INTEGER DEFAULT 1
);

-- Accountability items (waiting-for items that someone else needs to do)
CREATE TABLE IF NOT EXISTS accountability_items (
  id INTEGER PRIMARY KEY,
  description TEXT NOT NULL,
  responsible_party TEXT,          -- who needs to do this
  context TEXT,                    -- additional context
  source_type TEXT,                -- 'signal' | 'ai_response' | 'manual'
  source_ref_id INTEGER,           -- reference to source if applicable
  status TEXT DEFAULT 'waiting',   -- 'waiting' | 'completed' | 'cancelled'
  due_date TEXT,
  completed_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_accountability_status ON accountability_items(status);
CREATE INDEX IF NOT EXISTS idx_accountability_responsible ON accountability_items(responsible_party);

-- Career profile and growth tracking
CREATE TABLE IF NOT EXISTS career_profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  current_role TEXT NOT NULL,
  target_role TEXT,
  strengths TEXT,                  -- comma-separated or JSON
  weaknesses TEXT,                 -- areas for improvement
  interests TEXT,                  -- topics/technologies of interest
  goals TEXT,                      -- career goals description
  certifications TEXT,             -- current certifications held
  education TEXT,                  -- education background
  years_experience INTEGER,        -- years of professional experience
  preferred_work_style TEXT,       -- remote/hybrid/office, team size preferences
  industry_focus TEXT,             -- industries of interest/experience
  leadership_experience TEXT,      -- management/leadership experience
  notable_projects TEXT,           -- key projects/accomplishments
  learning_priorities TEXT,        -- current learning priorities
  career_timeline TEXT,            -- target timeline for career goals
  technical_specializations TEXT,  -- core technical domains
  soft_skills TEXT,                -- communication, leadership skills
  work_achievements TEXT,          -- quantified achievements/metrics
  career_values TEXT,              -- work-life balance, impact, compensation priorities
  short_term_goals TEXT,           -- 6-12 month goals
  long_term_goals TEXT,            -- 3-5 year vision
  mentorship TEXT,                 -- mentoring relationships
  networking TEXT,                 -- professional communities/groups
  languages TEXT,                  -- spoken and programming languages
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Career development suggestions (AI-generated growth opportunities)
CREATE TABLE IF NOT EXISTS career_suggestions (
  id INTEGER PRIMARY KEY,
  suggestion_type TEXT NOT NULL,   -- 'stretch' | 'skill_building' | 'project' | 'learning'
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  rationale TEXT,                  -- why this helps career growth
  difficulty TEXT,                 -- 'beginner' | 'intermediate' | 'advanced'
  time_estimate TEXT,              -- e.g., '2-4 weeks', '1 day'
  related_goal TEXT,               -- which career goal this supports
  status TEXT DEFAULT 'suggested', -- 'suggested' | 'accepted' | 'in_progress' | 'completed' | 'dismissed'
  converted_to_ticket INTEGER,    -- reference to ticket.id if converted
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Career chat status updates (summary for suggestion context)
CREATE TABLE IF NOT EXISTS career_chat_updates (
  id INTEGER PRIMARY KEY,
  message TEXT NOT NULL,
  response TEXT NOT NULL,
  summary TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_career_suggestions_type ON career_suggestions(suggestion_type);
CREATE INDEX IF NOT EXISTS idx_career_suggestions_status ON career_suggestions(status);

-- Standup updates for career tracking and auto-generated feedback
CREATE TABLE IF NOT EXISTS standup_updates (
  id INTEGER PRIMARY KEY,
  standup_date TEXT NOT NULL,      -- date of the standup (YYYY-MM-DD)
  content TEXT NOT NULL,           -- the standup update text
  feedback TEXT,                   -- AI-generated feedback/advice
  sentiment TEXT,                  -- 'positive' | 'neutral' | 'blocked' | 'struggling'
  key_themes TEXT,                 -- comma-separated main themes
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_standup_date ON standup_updates(standup_date);

-- Ticket files (files to be created or updated as part of a ticket)
CREATE TABLE IF NOT EXISTS ticket_files (
  id INTEGER PRIMARY KEY,
  ticket_id INTEGER NOT NULL,
  filename TEXT NOT NULL,          -- file path/name
  file_type TEXT DEFAULT 'update', -- 'new' (to create) or 'update' (to modify)
  base_content TEXT,               -- original content for 'update' files (for diffing)
  description TEXT,                -- brief description of changes needed
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
  UNIQUE(ticket_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_ticket_files_ticket ON ticket_files(ticket_id);

-- Code locker for tracking file changes per ticket throughout sprint
CREATE TABLE IF NOT EXISTS code_locker (
  id INTEGER PRIMARY KEY,
  ticket_id INTEGER,               -- which ticket this file relates to (NULL for unassigned)
  filename TEXT NOT NULL,          -- name of the file
  content TEXT NOT NULL,           -- file content/code
  version INTEGER DEFAULT 1,       -- version number (increments with each upload)
  notes TEXT,                      -- optional notes about this version
  is_initial INTEGER DEFAULT 0,   -- 1 if this is the initial/baseline version
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_code_locker_ticket ON code_locker(ticket_id);
CREATE INDEX IF NOT EXISTS idx_code_locker_filename ON code_locker(filename);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER,
  source TEXT NOT NULL,
  content TEXT NOT NULL,
  document_date TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (meeting_id) REFERENCES meeting_summaries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_meeting_id ON documents(meeting_id);

-- Career memories with pinning support
CREATE TABLE IF NOT EXISTS career_memories (
  id INTEGER PRIMARY KEY,
  memory_type TEXT NOT NULL,        -- 'completed_project' | 'skill_milestone' | 'ai_implementation' | 'achievement'
  title TEXT NOT NULL,
  description TEXT,
  source_type TEXT,                 -- 'ticket' | 'standup' | 'codebase' | 'manual'
  source_id INTEGER,                -- reference to source (ticket id, etc.)
  skills TEXT,                      -- comma-separated skills related to this memory
  technologies TEXT,                -- comma-separated technologies used
  is_pinned INTEGER DEFAULT 0,      -- 1 if pinned (protected from refresh)
  is_ai_work INTEGER DEFAULT 0,     -- 1 if this is AI implementation work
  metadata TEXT,                    -- JSON for additional metadata
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_career_memories_type ON career_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_career_memories_pinned ON career_memories(is_pinned);

-- Skills tracker for development progress
CREATE TABLE IF NOT EXISTS skill_tracker (
  id INTEGER PRIMARY KEY,
  skill_name TEXT NOT NULL UNIQUE,
  category TEXT,                    -- 'ddd' | 'python' | 'analytics' | 'backend' | 'api' | 'airflow' | 'aws' | 'ai' | 'data'
  proficiency_level INTEGER DEFAULT 0,  -- 0-100
  tickets_count INTEGER DEFAULT 0,  -- number of tickets involving this skill
  projects_count INTEGER DEFAULT 0, -- number of projects involving this skill
  last_used_at TEXT,
  evidence TEXT,                    -- JSON array of evidence (ticket ids, code files, etc.)
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_skill_tracker_category ON skill_tracker(category);
"""

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        
        # Migration: Add sprint_points column to tickets if it doesn't exist
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN sprint_points INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add in_sprint column to tickets if it doesn't exist
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN in_sprint INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add source_document_id column to meeting_summaries if it doesn't exist
        try:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN source_document_id INTEGER")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add raw_text column to meeting_summaries if it doesn't exist
        try:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN raw_text TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add pocket_ai_summary column to meeting_summaries if it doesn't exist
        try:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN pocket_ai_summary TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add pocket_template_type column to meeting_summaries if it doesn't exist
        try:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN pocket_template_type TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add pocket_mind_map column to meeting_summaries if it doesn't exist
        try:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN pocket_mind_map TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add projects_count column to skill_tracker if it doesn't exist
        try:
            conn.execute("ALTER TABLE skill_tracker ADD COLUMN projects_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add new career_profile columns if they don't exist
        career_profile_columns = [
            ("certifications", "TEXT"),
            ("education", "TEXT"),
            ("years_experience", "INTEGER"),
            ("preferred_work_style", "TEXT"),
            ("industry_focus", "TEXT"),
            ("leadership_experience", "TEXT"),
            ("notable_projects", "TEXT"),
            ("learning_priorities", "TEXT"),
            ("career_timeline", "TEXT"),
            ("technical_specializations", "TEXT"),
            ("soft_skills", "TEXT"),
            ("work_achievements", "TEXT"),
            ("career_values", "TEXT"),
            ("short_term_goals", "TEXT"),
            ("long_term_goals", "TEXT"),
            ("mentorship", "TEXT"),
            ("networking", "TEXT"),
            ("languages", "TEXT"),
        ]
        for col_name, col_type in career_profile_columns:
            try:
                conn.execute(f"ALTER TABLE career_profile ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        # Migration: Add technologies column to career_memories if it doesn't exist
        try:
            conn.execute("ALTER TABLE career_memories ADD COLUMN technologies TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration: Add meeting_id column to docs table if it doesn't exist
        try:
            conn.execute("ALTER TABLE docs ADD COLUMN meeting_id INTEGER REFERENCES meeting_summaries(id)")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration (F1): Add import_source column to meeting_summaries
        try:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN import_source TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration (F1): Add source_url column to meeting_summaries
        try:
            conn.execute("ALTER TABLE meeting_summaries ADD COLUMN source_url TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Migration (F1b): Create meeting_documents table for linked transcripts/summaries
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meeting_documents (
                id INTEGER PRIMARY KEY,
                meeting_id INTEGER NOT NULL,
                doc_type TEXT NOT NULL,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                format TEXT,
                signals_json TEXT,
                file_path TEXT,
                metadata_json TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (meeting_id) REFERENCES meeting_summaries(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meeting_documents_meeting ON meeting_documents(meeting_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meeting_documents_type ON meeting_documents(doc_type, source)")
        
        # Migration (F2): Create conversation_mindmaps table with hierarchy support
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_mindmaps (
                id INTEGER PRIMARY KEY,
                conversation_id INTEGER NOT NULL,
                mindmap_json TEXT NOT NULL,
                hierarchy_levels INTEGER,
                root_node_id TEXT,
                node_count INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_mindmaps_conversation_id ON conversation_mindmaps(conversation_id)")
        
        # Migration (F2): Create mindmap_syntheses table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mindmap_syntheses (
                id INTEGER PRIMARY KEY,
                synthesis_text TEXT NOT NULL,
                hierarchy_summary TEXT,
                source_mindmap_ids TEXT,
                source_conversation_ids TEXT,
                key_topics TEXT,
                relationships TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mindmap_syntheses_updated ON mindmap_syntheses(updated_at)")
        
        # Migration (F2): Create mindmap_synthesis_history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mindmap_synthesis_history (
                id INTEGER PRIMARY KEY,
                synthesis_id INTEGER NOT NULL,
                previous_text TEXT,
                changes_summary TEXT,
                triggered_by TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (synthesis_id) REFERENCES mindmap_syntheses(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_synthesis_history_synthesis_id ON mindmap_synthesis_history(synthesis_id)")
        
        # Initialize default career profile
        conn.execute("""
            INSERT OR IGNORE INTO career_profile (id, current_role, target_role, strengths, weaknesses, interests, goals)
            VALUES (1, 
                'Senior Data Engineer', 
                'Knowledge Engineer',
                'Systems thinking, data architecture, enterprise solutions',
                'Need more experience with knowledge graphs, semantic web technologies',
                'Data lineage, data catalog, enterprise data solutions, knowledge management',
                'Transition from Senior Data Engineer to Knowledge Engineer role by developing expertise in knowledge graphs, semantic technologies, and enterprise knowledge management systems'
            )
        """)

