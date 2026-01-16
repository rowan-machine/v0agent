import os

DB_PATH = os.getenv("AGENT_DB_PATH", "agent.db")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")