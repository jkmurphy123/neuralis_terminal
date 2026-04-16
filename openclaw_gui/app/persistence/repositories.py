"""Explicit SQLite repositories for core domain models."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Generic, TypeVar

from openclaw_gui.app.models.event import EventType, SessionEvent
from openclaw_gui.app.models.personality import Personality
from openclaw_gui.app.models.project import Project, utc_now
from openclaw_gui.app.models.session import SessionRecord, SessionStatus
from openclaw_gui.app.persistence.db import Database

ModelT = TypeVar("ModelT")


def _serialize_datetime(value: datetime) -> str:
    return value.isoformat()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


class BaseRepository(Generic[ModelT]):
    """Small base class providing DB access to concrete repositories."""

    table_name: str

    def __init__(self, database: Database) -> None:
        self.database = database


class ProjectRepository(BaseRepository[Project]):
    """CRUD operations for persisted projects."""

    table_name = "projects"

    def create(self, project: Project) -> Project:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    id, name, description, root_path,
                    default_personality_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.name,
                    project.description,
                    project.root_path,
                    project.default_personality_id,
                    _serialize_datetime(project.created_at),
                    _serialize_datetime(project.updated_at),
                ),
            )
            connection.commit()
        return project

    def get(self, project_id: str) -> Project | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return self._row_to_model(row) if row else None

    def list_all(self) -> list[Project]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def update(self, project: Project) -> Project:
        updated = replace(project, updated_at=utc_now())
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE projects
                SET name = ?, description = ?, root_path = ?,
                    default_personality_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.name,
                    updated.description,
                    updated.root_path,
                    updated.default_personality_id,
                    _serialize_datetime(updated.updated_at),
                    updated.id,
                ),
            )
            connection.commit()
        return updated

    def delete(self, project_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            connection.commit()

    @staticmethod
    def _row_to_model(row: object) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            root_path=row["root_path"],
            default_personality_id=row["default_personality_id"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )


class PersonalityRepository(BaseRepository[Personality]):
    """CRUD operations for personality metadata."""

    table_name = "personalities"

    def create(self, personality: Personality) -> Personality:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO personalities (
                    id, name, description, storage_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    personality.id,
                    personality.name,
                    personality.description,
                    personality.storage_path,
                    _serialize_datetime(personality.created_at),
                    _serialize_datetime(personality.updated_at),
                ),
            )
            connection.commit()
        return personality

    def get(self, personality_id: str) -> Personality | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM personalities WHERE id = ?",
                (personality_id,),
            ).fetchone()
        return self._row_to_model(row) if row else None

    def list_all(self) -> list[Personality]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM personalities ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def update(self, personality: Personality) -> Personality:
        updated = replace(personality, updated_at=utc_now())
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE personalities
                SET name = ?, description = ?, storage_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.name,
                    updated.description,
                    updated.storage_path,
                    _serialize_datetime(updated.updated_at),
                    updated.id,
                ),
            )
            connection.commit()
        return updated

    def delete(self, personality_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM personalities WHERE id = ?", (personality_id,))
            connection.commit()

    @staticmethod
    def _row_to_model(row: object) -> Personality:
        return Personality(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            storage_path=row["storage_path"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )


class SessionRepository(BaseRepository[SessionRecord]):
    """CRUD operations for session metadata."""

    table_name = "sessions"

    def create(self, session: SessionRecord) -> SessionRecord:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    id, project_id, personality_id, status, gateway_session_ref,
                    started_at, last_activity_at, transcript_path, summary_path,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.project_id,
                    session.personality_id,
                    session.status.value,
                    session.gateway_session_ref,
                    _serialize_datetime(session.started_at),
                    _serialize_datetime(session.last_activity_at),
                    session.transcript_path,
                    session.summary_path,
                    session.metadata_json,
                ),
            )
            connection.commit()
        return session

    def get(self, session_id: str) -> SessionRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return self._row_to_model(row) if row else None

    def list_by_project(self, project_id: str) -> list[SessionRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM sessions
                WHERE project_id = ?
                ORDER BY last_activity_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def update(
        self,
        session: SessionRecord,
        *,
        touch_last_activity: bool = True,
    ) -> SessionRecord:
        updated = replace(session, last_activity_at=utc_now()) if touch_last_activity else session
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET project_id = ?, personality_id = ?, status = ?,
                    gateway_session_ref = ?, last_activity_at = ?,
                    transcript_path = ?, summary_path = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    updated.project_id,
                    updated.personality_id,
                    updated.status.value,
                    updated.gateway_session_ref,
                    _serialize_datetime(updated.last_activity_at),
                    updated.transcript_path,
                    updated.summary_path,
                    updated.metadata_json,
                    updated.id,
                ),
            )
            connection.commit()
        return updated

    def delete(self, session_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            connection.commit()

    @staticmethod
    def _row_to_model(row: object) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            project_id=row["project_id"],
            personality_id=row["personality_id"],
            status=SessionStatus(row["status"]),
            gateway_session_ref=row["gateway_session_ref"],
            started_at=_parse_datetime(row["started_at"]),
            last_activity_at=_parse_datetime(row["last_activity_at"]),
            transcript_path=row["transcript_path"],
            summary_path=row["summary_path"],
            metadata_json=row["metadata_json"],
        )


class SessionEventRepository(BaseRepository[SessionEvent]):
    """CRUD operations for session events."""

    table_name = "session_events"

    def create(self, event: SessionEvent) -> SessionEvent:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO session_events (
                    id, session_id, timestamp, event_type, content, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.session_id,
                    _serialize_datetime(event.timestamp),
                    event.event_type.value,
                    event.content,
                    event.metadata_json,
                ),
            )
            connection.commit()
        return event

    def list_by_session(self, session_id: str) -> list[SessionEvent]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM session_events
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def delete_for_session(self, session_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM session_events WHERE session_id = ?",
                (session_id,),
            )
            connection.commit()

    @staticmethod
    def _row_to_model(row: object) -> SessionEvent:
        return SessionEvent(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=_parse_datetime(row["timestamp"]),
            event_type=EventType(row["event_type"]),
            content=row["content"],
            metadata_json=row["metadata_json"],
        )
