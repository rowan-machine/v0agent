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
"""

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)

