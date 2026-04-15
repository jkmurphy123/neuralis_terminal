from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_gui.app.persistence.db import Database
from openclaw_gui.app.persistence.file_store import FileStore


@pytest.fixture
def file_store(tmp_path: Path) -> FileStore:
    store = FileStore(tmp_path / "data")
    store.initialize()
    return store


@pytest.fixture
def database(file_store: FileStore) -> Database:
    db = Database(file_store.database_path)
    db.initialize()
    return db
