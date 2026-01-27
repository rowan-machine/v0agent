-- Migration: Create missing tables in Supabase
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor > New Query)

-- ============================================================================
-- MEETING SUMMARIES TABLE (was missing)
-- ============================================================================
CREATE TABLE IF NOT EXISTS meeting_summaries (
    id SERIAL PRIMARY KEY,
    meeting_name TEXT NOT NULL,
    synthesized_notes TEXT NOT NULL,
    meeting_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    signals_json JSONB,
    source_document_id INTEGER REFERENCES docs(id) ON DELETE SET NULL,
    raw_text TEXT,
    pocket_ai_summary TEXT,
    pocket_mind_map TEXT,
    pocket_template_type TEXT,
    import_source TEXT,  -- 'manual', 'markdown_upload', 'pocket', 'api'
    source_url TEXT,
    synced_from_device TEXT DEFAULT 'local',
    last_modified_device TEXT DEFAULT 'local',
    last_modified_at TIMESTAMPTZ,
    sync_version INTEGER DEFAULT 0,
    embedding_status TEXT DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_meeting_summaries_date ON meeting_summaries(meeting_date);
CREATE INDEX IF NOT EXISTS idx_meeting_summaries_name ON meeting_summaries(meeting_name);
CREATE INDEX IF NOT EXISTS idx_meeting_summaries_sync_device ON meeting_summaries(synced_from_device);
CREATE INDEX IF NOT EXISTS idx_meeting_summaries_embedding_status ON meeting_summaries(embedding_status);

-- Enable Row Level Security
ALTER TABLE meeting_summaries ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- SIGNALS TABLE (was named signal_status in SQLite, standardize to signals)
-- ============================================================================
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER NOT NULL REFERENCES meeting_summaries(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,  -- 'decision', 'action_item', 'blocker', 'risk', 'idea'
    signal_text TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'archived', 'completed'
    converted_to TEXT,  -- 'ticket' if converted
    converted_ref_id INTEGER,  -- reference to ticket.id if converted
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(meeting_id, signal_type, signal_text)
);

CREATE INDEX IF NOT EXISTS idx_signals_meeting ON signals(meeting_id);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);

-- Enable Row Level Security
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- SIGNAL_FEEDBACK TABLE (for learning signal preferences)
-- ============================================================================
CREATE TABLE IF NOT EXISTS signal_feedback (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES signals(id) ON DELETE CASCADE,
    meeting_id INTEGER REFERENCES meeting_summaries(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,
    signal_text TEXT NOT NULL,
    feedback TEXT NOT NULL,  -- 'approve', 'reject', 'edit'
    edited_text TEXT,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signal_feedback_meeting ON signal_feedback(meeting_id);

-- Enable Row Level Security
ALTER TABLE signal_feedback ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- WORKFLOW_MODES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow_modes (
    id SERIAL PRIMARY KEY,
    mode_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '🎯',
    short_description TEXT,
    description TEXT,
    steps_json JSONB,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_modes_key ON workflow_modes(mode_key);

-- ============================================================================
-- MODE_SESSIONS TABLE (time tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS mode_sessions (
    id SERIAL PRIMARY KEY,
    mode TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    date DATE NOT NULL,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_mode_sessions_mode ON mode_sessions(mode);
CREATE INDEX IF NOT EXISTS idx_mode_sessions_date ON mode_sessions(date);

-- ============================================================================
-- SPRINT_SETTINGS TABLE (singleton)
-- ============================================================================
CREATE TABLE IF NOT EXISTS sprint_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    sprint_start_date DATE NOT NULL,
    sprint_length_days INTEGER DEFAULT 14,
    sprint_name TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- USER_STATUS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_status (
    id SERIAL PRIMARY KEY,
    status_text TEXT NOT NULL,
    interpreted_mode TEXT,
    interpreted_activity TEXT,
    interpreted_context TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_current BOOLEAN DEFAULT true
);

-- ============================================================================
-- EMBEDDINGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    ref_type TEXT NOT NULL,  -- 'doc', 'meeting'
    ref_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    vector JSONB NOT NULL,  -- JSON array of floats
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ref_type, ref_id, model)
);

CREATE INDEX IF NOT EXISTS idx_embeddings_ref ON embeddings(ref_type, ref_id);

-- ============================================================================
-- CAREER_PROFILES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS career_profiles (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    current_role TEXT NOT NULL,
    target_role TEXT,
    strengths TEXT,
    weaknesses TEXT,
    interests TEXT,
    goals TEXT,
    certifications TEXT,
    education TEXT,
    years_experience INTEGER,
    preferred_work_style TEXT,
    industry_focus TEXT,
    leadership_experience TEXT,
    notable_projects TEXT,
    learning_priorities TEXT,
    career_timeline TEXT,
    technical_specializations TEXT,
    soft_skills TEXT,
    work_achievements TEXT,
    career_values TEXT,
    short_term_goals TEXT,
    long_term_goals TEXT,
    mentorship TEXT,
    networking TEXT,
    languages TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- CAREER_SUGGESTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS career_suggestions (
    id SERIAL PRIMARY KEY,
    suggestion_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    rationale TEXT,
    difficulty TEXT,
    time_estimate TEXT,
    related_goal TEXT,
    status TEXT DEFAULT 'suggested',
    converted_to_ticket INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_career_suggestions_type ON career_suggestions(suggestion_type);
CREATE INDEX IF NOT EXISTS idx_career_suggestions_status ON career_suggestions(status);

-- ============================================================================
-- STANDUP_UPDATES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS standup_updates (
    id SERIAL PRIMARY KEY,
    standup_date DATE NOT NULL,
    content TEXT NOT NULL,
    feedback TEXT,
    sentiment TEXT,
    key_themes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_standup_updates_date ON standup_updates(standup_date);

-- ============================================================================
-- CAREER_MEMORIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS career_memories (
    id SERIAL PRIMARY KEY,
    memory_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    source_type TEXT,
    source_id INTEGER,
    skills TEXT,
    technologies TEXT,
    is_pinned BOOLEAN DEFAULT false,
    is_ai_work BOOLEAN DEFAULT false,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_career_memories_type ON career_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_career_memories_pinned ON career_memories(is_pinned);

-- ============================================================================
-- SKILL_TRACKER TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS skill_tracker (
    id SERIAL PRIMARY KEY,
    skill_name TEXT NOT NULL UNIQUE,
    category TEXT,
    proficiency_level INTEGER DEFAULT 0,
    tickets_count INTEGER DEFAULT 0,
    projects_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    evidence JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skill_tracker_category ON skill_tracker(category);

-- ============================================================================
-- ACCOUNTABILITY_ITEMS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS accountability_items (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    responsible_party TEXT,
    context TEXT,
    source_type TEXT,
    source_ref_id INTEGER,
    status TEXT DEFAULT 'waiting',
    due_date DATE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_accountability_items_status ON accountability_items(status);

-- ============================================================================
-- CONVERSATIONS TABLE (for AI memory)
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    context_summary TEXT,
    metadata JSONB
);

-- ============================================================================
-- AI_MEMORY TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_memory (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5,
    context TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ai_memory_conversation ON ai_memory(conversation_id);
CREATE INDEX IF NOT EXISTS idx_ai_memory_type ON ai_memory(memory_type);

-- ============================================================================
-- ENTITY_LINKS TABLE (for knowledge graph)
-- ============================================================================
CREATE TABLE IF NOT EXISTS entity_links (
    id SERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    relationship TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_type, source_id, target_type, target_id, relationship)
);

CREATE INDEX IF NOT EXISTS idx_entity_links_source ON entity_links(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_target ON entity_links(target_type, target_id);

-- ============================================================================
-- NOTIFICATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT,
    priority TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'unread',
    action_url TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(notification_type);

-- ============================================================================
-- Done! Verify tables were created
-- ============================================================================
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
