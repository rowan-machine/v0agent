# tests/conftest.py

import os
import sys
import tempfile
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app import db as app_db


@pytest.fixture()
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Point app DB to temp file
    monkeypatch.setattr(app_db, "DB_PATH", path)

    # Init schema
    app_db.init_db()

    yield path

    os.remove(path)
