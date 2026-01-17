import sqlite3

DB_PATH = "agent.db"

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS meeting_summaries (
  id INTEGER PRIMARY KEY,
  meeting_name TEXT NOT NULL,
  synthesized_notes TEXT NOT NULL,
  meeting_date TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

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
"""

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)

