-- Migration: Add missing tables from SQLite to Supabase
-- Tables: conversation_mindmaps, mindmap_syntheses, meeting_summaries (legacy), docs
-- Also ensures workflow_modes and code_locker exist with correct schema
-- Date: 2026-01-26

-- =============================================================================
-- CONVERSATION MINDMAPS - Hierarchical mindmaps from conversations
-- =============================================================================
CREATE TABLE IF NOT EXISTS conversation_mindmaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    mindmap_json JSONB NOT NULL DEFAULT '{}',
    hierarchy_levels INTEGER DEFAULT 1,
    root_node_id TEXT,
    node_count INTEGER DEFAULT 0,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE conversation_mindmaps IS 'Hierarchical mindmaps generated from conversation threads for knowledge visualization';
COMMENT ON COLUMN conversation_mindmaps.mindmap_json IS 'Full mindmap structure as JSON with nodes, edges, and metadata';
COMMENT ON COLUMN conversation_mindmaps.hierarchy_levels IS 'Number of levels in the mindmap hierarchy';
COMMENT ON COLUMN conversation_mindmaps.root_node_id IS 'ID of the root/central node in the mindmap';

-- Index for faster conversation lookups
CREATE INDEX IF NOT EXISTS idx_conversation_mindmaps_conversation 
    ON conversation_mindmaps(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversation_mindmaps_user 
    ON conversation_mindmaps(user_id);

-- RLS Policy
ALTER TABLE conversation_mindmaps ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own mindmaps" ON conversation_mindmaps;
CREATE POLICY "Users can view own mindmaps" ON conversation_mindmaps
    FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);

DROP POLICY IF EXISTS "Users can insert own mindmaps" ON conversation_mindmaps;
CREATE POLICY "Users can insert own mindmaps" ON conversation_mindmaps
    FOR INSERT WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

DROP POLICY IF EXISTS "Users can update own mindmaps" ON conversation_mindmaps;
CREATE POLICY "Users can update own mindmaps" ON conversation_mindmaps
    FOR UPDATE USING (auth.uid() = user_id OR user_id IS NULL);

DROP POLICY IF EXISTS "Users can delete own mindmaps" ON conversation_mindmaps;
CREATE POLICY "Users can delete own mindmaps" ON conversation_mindmaps
    FOR DELETE USING (auth.uid() = user_id OR user_id IS NULL);


-- =============================================================================
-- MINDMAP SYNTHESES - AI-generated knowledge syntheses from mindmaps
-- =============================================================================
CREATE TABLE IF NOT EXISTS mindmap_syntheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    mindmap_id UUID REFERENCES conversation_mindmaps(id) ON DELETE SET NULL,
    synthesis_text TEXT NOT NULL,
    synthesis_type TEXT DEFAULT 'summary' CHECK (synthesis_type IN ('summary', 'insights', 'actions', 'knowledge', 'full')),
    input_text TEXT,
    model_used TEXT DEFAULT 'gpt-4o-mini',
    tokens_used INTEGER,
    confidence_score REAL DEFAULT 0.8,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE mindmap_syntheses IS 'AI-generated syntheses and insights extracted from mindmaps and meeting content';
COMMENT ON COLUMN mindmap_syntheses.synthesis_type IS 'Type of synthesis: summary, insights, actions, knowledge, or full';
COMMENT ON COLUMN mindmap_syntheses.confidence_score IS 'AI confidence in the synthesis quality (0.0-1.0)';

CREATE INDEX IF NOT EXISTS idx_mindmap_syntheses_meeting ON mindmap_syntheses(meeting_id);
CREATE INDEX IF NOT EXISTS idx_mindmap_syntheses_mindmap ON mindmap_syntheses(mindmap_id);
CREATE INDEX IF NOT EXISTS idx_mindmap_syntheses_user ON mindmap_syntheses(user_id);
CREATE INDEX IF NOT EXISTS idx_mindmap_syntheses_type ON mindmap_syntheses(synthesis_type);

-- RLS Policy
ALTER TABLE mindmap_syntheses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage own syntheses" ON mindmap_syntheses;
CREATE POLICY "Users can manage own syntheses" ON mindmap_syntheses
    FOR ALL USING (auth.uid() = user_id OR user_id IS NULL);


-- =============================================================================
-- MINDMAP SYNTHESIS HISTORY - Track evolution of syntheses over time
-- =============================================================================
CREATE TABLE IF NOT EXISTS mindmap_synthesis_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    synthesis_id UUID REFERENCES mindmap_syntheses(id) ON DELETE CASCADE,
    previous_text TEXT,
    new_text TEXT,
    change_type TEXT DEFAULT 'update' CHECK (change_type IN ('create', 'update', 'merge', 'promote')),
    change_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE mindmap_synthesis_history IS 'Audit trail for mindmap synthesis changes and evolution';

CREATE INDEX IF NOT EXISTS idx_synthesis_history_synthesis ON mindmap_synthesis_history(synthesis_id);

ALTER TABLE mindmap_synthesis_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own synthesis history" ON mindmap_synthesis_history;
CREATE POLICY "Users can view own synthesis history" ON mindmap_synthesis_history
    FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);


-- =============================================================================
-- DOCS - Legacy document storage (different from documents table)
-- =============================================================================
CREATE TABLE IF NOT EXISTS docs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    document_date TIMESTAMPTZ,
    meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
    device_id TEXT,
    synced_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    -- Full-text search
    fts tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(source, '') || ' ' || coalesce(content, ''))
    ) STORED
);

COMMENT ON TABLE docs IS 'Legacy document storage for imported notes and pastes (use documents table for new data)';

CREATE INDEX IF NOT EXISTS idx_docs_user ON docs(user_id);
CREATE INDEX IF NOT EXISTS idx_docs_meeting ON docs(meeting_id);
CREATE INDEX IF NOT EXISTS idx_docs_fts ON docs USING GIN(fts);

ALTER TABLE docs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage own docs" ON docs;
CREATE POLICY "Users can manage own docs" ON docs
    FOR ALL USING (auth.uid() = user_id OR user_id IS NULL);


-- =============================================================================
-- SKILL IMPORT TRACKING - Track skill imports from external sources
-- =============================================================================
CREATE TABLE IF NOT EXISTS skill_import_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    source TEXT NOT NULL,
    source_id TEXT,
    skill_name TEXT NOT NULL,
    imported_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE skill_import_tracking IS 'Tracks skills imported from external sources to avoid duplicates';

CREATE INDEX IF NOT EXISTS idx_skill_import_source ON skill_import_tracking(source, source_id);
CREATE INDEX IF NOT EXISTS idx_skill_import_user ON skill_import_tracking(user_id);

ALTER TABLE skill_import_tracking ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage own skill imports" ON skill_import_tracking;
CREATE POLICY "Users can manage own skill imports" ON skill_import_tracking
    FOR ALL USING (auth.uid() = user_id OR user_id IS NULL);


-- =============================================================================
-- SESSIONS - User sessions (if needed for web auth)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    token TEXT UNIQUE NOT NULL,
    user_agent TEXT,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_active TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ
);

COMMENT ON TABLE sessions IS 'User session tokens for web authentication';

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own sessions" ON sessions;
CREATE POLICY "Users can view own sessions" ON sessions
    FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);


-- =============================================================================
-- Add pocket_mind_map and pocket_template_type to meetings if missing
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'meetings' AND column_name = 'pocket_ai_summary'
    ) THEN
        ALTER TABLE meetings ADD COLUMN pocket_ai_summary TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'meetings' AND column_name = 'pocket_mind_map'
    ) THEN
        ALTER TABLE meetings ADD COLUMN pocket_mind_map TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'meetings' AND column_name = 'pocket_template_type'
    ) THEN
        ALTER TABLE meetings ADD COLUMN pocket_template_type TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'meetings' AND column_name = 'import_source'
    ) THEN
        ALTER TABLE meetings ADD COLUMN import_source TEXT;
    END IF;
END
$$;


-- =============================================================================
-- Verify workflow_modes has correct schema (already exists in Supabase)
-- Just add any missing columns
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'workflow_modes' AND column_name = 'short_description'
    ) THEN
        ALTER TABLE workflow_modes ADD COLUMN short_description TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'workflow_modes' AND column_name = 'steps'
    ) THEN
        -- Already has 'steps' as JSONB
        NULL;
    END IF;
END
$$;


-- =============================================================================
-- Update code_locker to ensure it has all needed columns
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'code_locker' AND column_name = 'notes'
    ) THEN
        ALTER TABLE code_locker ADD COLUMN notes TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'code_locker' AND column_name = 'is_initial'
    ) THEN
        ALTER TABLE code_locker ADD COLUMN is_initial BOOLEAN DEFAULT false;
    END IF;
END
$$;


-- =============================================================================
-- GRANT PERMISSIONS (for service role)
-- =============================================================================
GRANT ALL ON conversation_mindmaps TO service_role;
GRANT ALL ON mindmap_syntheses TO service_role;
GRANT ALL ON mindmap_synthesis_history TO service_role;
GRANT ALL ON docs TO service_role;
GRANT ALL ON skill_import_tracking TO service_role;
GRANT ALL ON sessions TO service_role;

-- For anon role (read-only where appropriate)
GRANT SELECT ON conversation_mindmaps TO anon;
GRANT SELECT ON mindmap_syntheses TO anon;
