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
  status TEXT DEFAULT 'todo',       -- todo, in_progress, in_review, blocked, done, complete
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

