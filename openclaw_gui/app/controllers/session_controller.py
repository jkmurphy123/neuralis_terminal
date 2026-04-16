"""Session controller for project-scoped lifecycle orchestration."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from typing import Any

from openclaw_gui.app.gateway.gateway_adapter import GatewayAdapter
from openclaw_gui.app.gateway.gateway_errors import GatewayError
from openclaw_gui.app.gateway.gateway_models import (
    GatewayMessageResult,
    GatewaySessionHandle,
)
from openclaw_gui.app.models.event import EventType, SessionEvent
from openclaw_gui.app.models.personality import Personality
from openclaw_gui.app.models.project import Project
from openclaw_gui.app.models.session import SessionRecord, SessionStatus
from openclaw_gui.app.persistence.file_store import FileStore
from openclaw_gui.app.persistence.repositories import (
    PersonalityRepository,
    ProjectRepository,
    SessionEventRepository,
    SessionRepository,
)


@dataclass(slots=True)
class SessionStartResult:
    """Outcome of starting or restarting a session."""

    session: SessionRecord
    gateway_session_started: bool
    note: str | None = None


@dataclass(slots=True)
class SessionSendResult:
    """Outcome of sending one message through a session."""

    session: SessionRecord
    user_event: SessionEvent
    assistant_event: SessionEvent | None = None
    error_event: SessionEvent | None = None
    gateway_result: GatewayMessageResult | None = None


@dataclass(slots=True)
class ProjectSwitchResult:
    """Outcome of switching the active project context."""

    project_id: str
    active_session: SessionRecord | None
    suspended_session: SessionRecord | None = None
    restored_existing: bool = False


class SessionController:
    """Manage project-scoped sessions, transcript events, and restore flows."""

    def __init__(
        self,
        session_repository: SessionRepository,
        event_repository: SessionEventRepository,
        file_store: FileStore,
        gateway: GatewayAdapter,
        project_repository: ProjectRepository,
        personality_repository: PersonalityRepository,
    ) -> None:
        self.session_repository = session_repository
        self.event_repository = event_repository
        self.file_store = file_store
        self.gateway = gateway
        self.project_repository = project_repository
        self.personality_repository = personality_repository

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self.session_repository.get(session_id)

    def list_project_sessions(self, project_id: str) -> list[SessionRecord]:
        return self.session_repository.list_by_project(project_id)

    def list_session_events(self, session_id: str) -> list[SessionEvent]:
        return self.event_repository.list_by_session(session_id)

    def get_latest_restorable_session(self, project_id: str) -> SessionRecord | None:
        for session in self.session_repository.list_by_project(project_id):
            if session.status in {SessionStatus.ACTIVE, SessionStatus.SUSPENDED}:
                return session
        return None

    def start_session(self, *, project_id: str, personality_id: str) -> SessionStartResult:
        project = self._require_project(project_id)
        personality = self._require_personality(personality_id)
        session_id = str(uuid.uuid4())
        files = self.file_store.initialize_session_files(project_id, session_id)

        gateway_session_started = False
        gateway_note: str | None = None
        gateway_handle: GatewaySessionHandle | None = None
        try:
            gateway_handle = self.gateway.start_session(
                self._project_context(project),
                self._personality_context(personality),
            )
        except GatewayError as exc:
            gateway_note = str(exc)
        else:
            gateway_session_started = True

        session = SessionRecord(
            id=session_id,
            project_id=project_id,
            personality_id=personality_id,
            transcript_path=str(files["transcript_md"]),
            summary_path=str(files["summary_md"]),
            gateway_session_ref=(
                gateway_handle.gateway_session_ref if gateway_handle is not None else None
            ),
            status=SessionStatus.ACTIVE,
        )
        session = self.session_repository.create(session)

        metadata = self._base_metadata(session, project, personality)
        if gateway_handle is not None:
            metadata["gateway"] = {
                "mode": "native",
                "session_key": gateway_handle.session_key,
                "gateway_session_ref": gateway_handle.gateway_session_ref,
            }
        else:
            metadata["gateway"] = {
                "mode": "local-only",
                "detail": gateway_note or "Gateway session start is unavailable.",
            }

        session = self._persist_session_state(session, metadata)
        session, _ = self.append_event(
            session=session,
            event_type=EventType.STATUS,
            content="Session started.",
            metadata_json=json.dumps({"gateway_session_started": gateway_session_started}),
        )
        if gateway_note:
            session, _ = self.append_event(
                session=session,
                event_type=EventType.SYSTEM,
                content=gateway_note,
                metadata_json=json.dumps({"source": "gateway", "operation": "start_session"}),
            )
        return SessionStartResult(
            session=session,
            gateway_session_started=gateway_session_started,
            note=gateway_note,
        )

    def append_event(
        self,
        *,
        session: SessionRecord,
        event_type: EventType,
        content: str,
        metadata_json: str | None = None,
    ) -> tuple[SessionRecord, SessionEvent]:
        current = self._require_session(session.id)
        event = SessionEvent(
            id=str(uuid.uuid4()),
            session_id=current.id,
            event_type=event_type,
            content=content,
            metadata_json=metadata_json,
        )
        self.event_repository.create(event)
        self.file_store.append_transcript_markdown(
            current.project_id,
            current.id,
            role=event.event_type.value,
            content=event.content,
            timestamp=event.timestamp.isoformat(),
        )
        self.file_store.append_transcript_event_jsonl(current.project_id, current.id, event)

        metadata = self._session_metadata(current)
        metadata["event_count"] = int(metadata.get("event_count", 0)) + 1
        metadata["last_event_type"] = event.event_type.value
        updated = self._persist_session_state(current, metadata)
        return updated, event

    def send_message(self, *, session_id: str, text: str) -> SessionSendResult:
        if not text.strip():
            raise ValueError("Message text must not be empty.")

        current = self._require_session(session_id)
        if current.status != SessionStatus.ACTIVE:
            raise ValueError(f"Cannot send a message while session is {current.status.value}.")
        current, user_event = self.append_event(
            session=current,
            event_type=EventType.USER,
            content=text.strip(),
        )

        try:
            gateway_result = self.gateway.send_message(
                self._gateway_handle_for_session(current),
                text.strip(),
            )
        except GatewayError as exc:
            current, error_event = self.append_event(
                session=current,
                event_type=EventType.ERROR,
                content=str(exc),
                metadata_json=json.dumps({"source": "gateway", "operation": "send_message"}),
            )
            return SessionSendResult(
                session=current,
                user_event=user_event,
                error_event=error_event,
            )

        current = self._sync_gateway_session_key(current, gateway_result)

        assistant_text = self._assistant_text_from_result(gateway_result)
        current, assistant_event = self.append_event(
            session=current,
            event_type=EventType.ASSISTANT,
            content=assistant_text,
            metadata_json=json.dumps({"source": "gateway"}),
        )
        return SessionSendResult(
            session=current,
            user_event=user_event,
            assistant_event=assistant_event,
            gateway_result=gateway_result,
        )

    def _sync_gateway_session_key(
        self,
        session: SessionRecord,
        gateway_result: GatewayMessageResult,
    ) -> SessionRecord:
        if not gateway_result.session_key.strip():
            return session
        current_handle = self._gateway_handle_for_session(session)
        if gateway_result.session_key == current_handle.session_key:
            return session
        metadata = self._session_metadata(session)
        gateway_data = metadata.get("gateway")
        if not isinstance(gateway_data, dict):
            gateway_data = {}
        gateway_data["session_key"] = gateway_result.session_key
        metadata["gateway"] = gateway_data
        updated = replace(session, gateway_session_ref=gateway_result.session_key)
        return self._persist_session_state(updated, metadata)

    def suspend_session(
        self,
        session_id: str,
        *,
        summary_text: str | None = None,
    ) -> SessionRecord:
        current = self._require_session(session_id)
        note: str | None = None
        try:
            self.gateway.end_session(self._gateway_handle_for_session(current))
        except GatewayError as exc:
            note = str(exc)

        updated = replace(current, status=SessionStatus.SUSPENDED)
        if summary_text is not None:
            self.file_store.write_summary(current.project_id, current.id, summary_text)
        updated = self._persist_session_state(updated)
        updated, _ = self.append_event(
            session=updated,
            event_type=EventType.STATUS,
            content="Session suspended.",
        )
        if note:
            updated, _ = self.append_event(
                session=updated,
                event_type=EventType.SYSTEM,
                content=note,
                metadata_json=json.dumps({"source": "gateway", "operation": "end_session"}),
            )
        return updated

    def restore_session(self, session_id: str) -> SessionRecord:
        current = self._require_session(session_id)
        if current.status == SessionStatus.ARCHIVED:
            raise ValueError(f"Archived session cannot be restored: {session_id}")

        metadata = self._session_metadata(current)
        note: str | None = None
        try:
            gateway_handle = self.gateway.restore_session(
                {
                    "session_id": current.id,
                    "project_id": current.project_id,
                    "personality_id": current.personality_id,
                    "metadata": metadata,
                }
            )
        except GatewayError as exc:
            gateway_handle = None
            note = str(exc)

        if gateway_handle is not None:
            metadata["gateway"] = {
                "mode": "restored",
                "session_key": gateway_handle.session_key,
                "gateway_session_ref": gateway_handle.gateway_session_ref,
            }

        restored = replace(
            current,
            status=SessionStatus.ACTIVE,
            gateway_session_ref=(
                gateway_handle.gateway_session_ref
                if gateway_handle is not None
                else current.gateway_session_ref
            ),
        )
        restored = self._persist_session_state(restored, metadata)
        restored, _ = self.append_event(
            session=restored,
            event_type=EventType.STATUS,
            content="Session restored.",
        )
        if note:
            restored, _ = self.append_event(
                session=restored,
                event_type=EventType.SYSTEM,
                content=note,
                metadata_json=json.dumps({"source": "gateway", "operation": "restore_session"}),
            )
        return restored

    def restart_session(
        self,
        session_id: str,
        *,
        personality_id: str | None = None,
    ) -> SessionStartResult:
        current = self._require_session(session_id)
        note: str | None = None
        try:
            self.gateway.end_session(self._gateway_handle_for_session(current))
        except GatewayError as exc:
            note = str(exc)
        archived = replace(current, status=SessionStatus.ARCHIVED)
        archived = self._persist_session_state(archived)
        archived, _ = self.append_event(
            session=archived,
            event_type=EventType.STATUS,
            content="Session archived during restart.",
        )
        if note:
            archived, _ = self.append_event(
                session=archived,
                event_type=EventType.SYSTEM,
                content=note,
                metadata_json=json.dumps({"source": "gateway", "operation": "end_session"}),
            )

        restarted = self.start_session(
            project_id=current.project_id,
            personality_id=personality_id or current.personality_id,
        )
        metadata = self._session_metadata(restarted.session)
        metadata["restart_of"] = current.id
        session = self._persist_session_state(restarted.session, metadata)
        session, _ = self.append_event(
            session=session,
            event_type=EventType.STATUS,
            content=f"Restarted from session {current.id}.",
            metadata_json=json.dumps({"restart_of": current.id}),
        )
        return SessionStartResult(
            session=session,
            gateway_session_started=restarted.gateway_session_started,
            note=restarted.note,
        )

    def change_session_personality(
        self,
        *,
        session_id: str,
        personality_id: str,
    ) -> SessionRecord:
        current = self._require_session(session_id)
        personality = self._require_personality(personality_id)
        if current.personality_id == personality_id:
            return current

        updated = replace(current, personality_id=personality_id)
        metadata = self._session_metadata(updated)
        metadata["personality_id"] = personality.id
        metadata["personality_name"] = personality.name
        updated = self._persist_session_state(updated, metadata)
        updated, _ = self.append_event(
            session=updated,
            event_type=EventType.PERSONALITY_CHANGE,
            content=f"Personality changed to {personality.name}.",
            metadata_json=json.dumps(
                {
                    "personality_id": personality.id,
                    "personality_name": personality.name,
                }
            ),
        )
        return updated

    def autosave_session(
        self,
        session_id: str,
        *,
        composer_draft: str = "",
    ) -> SessionRecord:
        current = self._require_session(session_id)
        metadata = self._session_metadata(current)
        metadata["composer_draft"] = composer_draft
        metadata["autosaved"] = True
        return self._persist_session_state(current, metadata)

    def switch_project(
        self,
        *,
        target_project_id: str,
        current_session_id: str | None = None,
    ) -> ProjectSwitchResult:
        self._require_project(target_project_id)
        suspended_session: SessionRecord | None = None

        if current_session_id is not None:
            current = self._require_session(current_session_id)
            if current.project_id == target_project_id:
                active_session = (
                    self.restore_session(current.id)
                    if current.status == SessionStatus.SUSPENDED
                    else current
                )
                return ProjectSwitchResult(
                    project_id=target_project_id,
                    active_session=active_session,
                    restored_existing=True,
                )
            if current.status == SessionStatus.ACTIVE:
                suspended_session = self.suspend_session(current.id)

        latest = self.get_latest_restorable_session(target_project_id)
        if latest is None:
            return ProjectSwitchResult(
                project_id=target_project_id,
                active_session=None,
                suspended_session=suspended_session,
                restored_existing=False,
            )

        if latest.status == SessionStatus.ACTIVE:
            active_session = latest
        else:
            active_session = self.restore_session(latest.id)
        return ProjectSwitchResult(
            project_id=target_project_id,
            active_session=active_session,
            suspended_session=suspended_session,
            restored_existing=True,
        )

    def _require_project(self, project_id: str) -> Project:
        project = self.project_repository.get(project_id)
        if project is None:
            raise ValueError(f"Unknown project id: {project_id}")
        return project

    def _require_personality(self, personality_id: str) -> Personality:
        personality = self.personality_repository.get(personality_id)
        if personality is None:
            raise ValueError(f"Unknown personality id: {personality_id}")
        return personality

    def _require_session(self, session_id: str) -> SessionRecord:
        session = self.session_repository.get(session_id)
        if session is None:
            raise ValueError(f"Unknown session id: {session_id}")
        return session

    def _project_context(self, project: Project) -> dict[str, object]:
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "root_path": project.root_path,
        }

    def _personality_context(self, personality: Personality) -> dict[str, object]:
        return {
            "id": personality.id,
            "name": personality.name,
            "description": personality.description,
            "storage_path": personality.storage_path,
        }

    def _base_metadata(
        self,
        session: SessionRecord,
        project: Project,
        personality: Personality,
    ) -> dict[str, object]:
        return {
            "session_id": session.id,
            "project_id": project.id,
            "project_name": project.name,
            "project_root_path": project.root_path,
            "personality_id": personality.id,
            "personality_name": personality.name,
            "status": session.status.value,
            "started_at": session.started_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat(),
            "transcript_path": session.transcript_path,
            "summary_path": session.summary_path,
            "gateway_session_ref": session.gateway_session_ref,
            "event_count": 0,
        }

    def _persist_session_state(
        self,
        session: SessionRecord,
        metadata: dict[str, object] | None = None,
    ) -> SessionRecord:
        payload = self._session_metadata(session)
        if metadata is not None:
            payload.update(metadata)
        payload.update(
            {
                "session_id": session.id,
                "project_id": session.project_id,
                "personality_id": session.personality_id,
                "status": session.status.value,
                "started_at": session.started_at.isoformat(),
                "transcript_path": session.transcript_path,
                "summary_path": session.summary_path,
                "gateway_session_ref": session.gateway_session_ref,
            }
        )
        stored = replace(
            session,
            metadata_json=json.dumps(payload, indent=2, sort_keys=True),
        )
        updated = self.session_repository.update(stored)
        payload["last_activity_at"] = updated.last_activity_at.isoformat()
        updated = replace(
            updated,
            metadata_json=json.dumps(payload, indent=2, sort_keys=True),
        )
        updated = self.session_repository.update(updated, touch_last_activity=False)
        self.file_store.write_session_metadata(updated.project_id, updated.id, payload)
        return updated

    def _session_metadata(self, session: SessionRecord) -> dict[str, object]:
        if session.metadata_json:
            try:
                loaded = json.loads(session.metadata_json)
            except json.JSONDecodeError:
                loaded = {}
            if isinstance(loaded, dict):
                return dict(loaded)
        return self.file_store.read_session_metadata(session.project_id, session.id)

    def _gateway_handle_for_session(self, session: SessionRecord) -> GatewaySessionHandle:
        metadata = self._session_metadata(session)
        gateway_data = metadata.get("gateway")
        if isinstance(gateway_data, dict):
            session_key = gateway_data.get("session_key")
            if isinstance(session_key, str) and session_key.strip():
                gateway_session_ref = gateway_data.get("gateway_session_ref")
                return GatewaySessionHandle(
                    session_key=session_key,
                    gateway_session_ref=(
                        str(gateway_session_ref) if gateway_session_ref is not None else None
                    ),
                )
        return GatewaySessionHandle(
            session_key=session.id,
            gateway_session_ref=session.gateway_session_ref,
        )

    def _assistant_text_from_result(self, result: GatewayMessageResult) -> str:
        text = self._find_text(result.raw_payload)
        if text:
            return text
        if result.raw_payload:
            return json.dumps(result.raw_payload, indent=2, sort_keys=True)
        return "Gateway response received."

    def _find_text(self, value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, dict):
            content_type = value.get("type")
            if content_type == "text":
                text_value = value.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    return text_value.strip()
            for key in ("content", "message", "text", "response", "reply"):
                candidate = value.get(key)
                found = self._find_text(candidate)
                if found:
                    return found
            for candidate in value.values():
                if not isinstance(candidate, (dict, list)):
                    continue
                found = self._find_text(candidate)
                if found:
                    return found
        if isinstance(value, list):
            for item in value:
                found = self._find_text(item)
                if found:
                    return found
        return None
