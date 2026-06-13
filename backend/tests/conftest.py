"""Test configuration — force mock providers, SQLite, and a temp storage dir.

Environment variables are set *before* any app module is imported so the cached
settings and SQLAlchemy engine pick them up.
"""

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="beshno-test-")

os.environ["LLM_PROVIDER"] = "mock"
os.environ["SEARCH_PROVIDER"] = "mock"
os.environ["TTS_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_DIR"] = _tmp
os.environ["MAX_REVISIONS"] = "2"
