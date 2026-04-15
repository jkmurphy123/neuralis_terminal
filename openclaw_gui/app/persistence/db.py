"""SQLite database bootstrap and connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        root_path TEXT NOT NULL,
        default_personality_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS personalities (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        storage_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        personality_id TEXT NOT NULL,
        status TEXT NOT NULL,
        gateway_session_ref TEXT,
        started_at TEXT NOT NULL,
        last_activity_at TEXT NOT NULL,
        transcript_path TEXT NOT NULL,
        summary_path TEXT,
        metadata_json TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(personality_id) REFERENCES personalities(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS session_events (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_session_id ON session_events(session_id)",
)


class Database:
    """Owns the SQLite file and initializes schema on demand."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        """Create the database file and schema."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            connection.commit()

    def connect(self) -> sqlite3.Connection:
        """Open a connection configured for named-column access."""
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
