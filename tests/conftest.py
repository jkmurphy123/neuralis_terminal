from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

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


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
