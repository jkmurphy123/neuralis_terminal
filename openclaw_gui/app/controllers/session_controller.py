"""Session controller for persistence-first lifecycle scaffolding."""

from __future__ import annotations

import json
import uuid

from openclaw_gui.app.models.event import EventType, SessionEvent
from openclaw_gui.app.models.session import SessionRecord, SessionStatus
from openclaw_gui.app.persistence.file_store import FileStore
from openclaw_gui.app.persistence.repositories import (
    SessionEventRepository,
    SessionRepository,
)


class SessionController:
    """Manage session records and local transcript state."""

    def __init__(
        self,
        session_repository: SessionRepository,
        event_repository: SessionEventRepository,
        file_store: FileStore,
    ) -> None:
        self.session_repository = session_repository
        self.event_repository = event_repository
        self.file_store = file_store

    def create_session(self, *, project_id: str, personality_id: str) -> SessionRecord:
        session_id = str(uuid.uuid4())
        files = self.file_store.initialize_session_files(project_id, session_id)
        session = SessionRecord(
            id=session_id,
            project_id=project_id,
            personality_id=personality_id,
            transcript_path=str(files["transcript_md"]),
            summary_path=str(files["summary_md"]),
            metadata_json=json.dumps({"project_id": project_id, "personality_id": personality_id}),
            status=SessionStatus.ACTIVE,
        )
        self.file_store.write_session_metadata(
            project_id,
            session_id,
            {"project_id": project_id, "personality_id": personality_id, "status": session.status.value},
        )
        return self.session_repository.create(session)

    def append_event(
        self,
        *,
        session: SessionRecord,
        event_type: EventType,
        content: str,
        metadata_json: str | None = None,
    ) -> SessionEvent:
        event = SessionEvent(
            id=str(uuid.uuid4()),
            session_id=session.id,
            event_type=event_type,
            content=content,
            metadata_json=metadata_json,
        )
        self.event_repository.create(event)
        self.file_store.append_transcript_markdown(
            session.project_id,
            session.id,
            role=event.event_type.value,
            content=event.content,
            timestamp=event.timestamp.isoformat(),
        )
        self.file_store.append_transcript_event_jsonl(session.project_id, session.id, event)
        return event

    def list_project_sessions(self, project_id: str) -> list[SessionRecord]:
        return self.session_repository.list_by_project(project_id)

    def suspend_session(self, session: SessionRecord) -> SessionRecord:
        suspended = SessionRecord(
            id=session.id,
            project_id=session.project_id,
            personality_id=session.personality_id,
            status=SessionStatus.SUSPENDED,
            gateway_session_ref=session.gateway_session_ref,
            started_at=session.started_at,
            last_activity_at=session.last_activity_at,
            transcript_path=session.transcript_path,
            summary_path=session.summary_path,
            metadata_json=session.metadata_json,
        )
        self.file_store.write_session_metadata(
            session.project_id,
            session.id,
            {"status": SessionStatus.SUSPENDED.value},
        )
        return self.session_repository.update(suspended)
