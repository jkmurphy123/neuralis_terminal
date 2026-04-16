from __future__ import annotations

import json
from pathlib import Path

from openclaw_gui.app.controllers.session_controller import SessionController
from openclaw_gui.app.gateway.gateway_adapter import GatewayAdapter
from openclaw_gui.app.gateway.gateway_errors import GatewayUnsupportedOperationError
from openclaw_gui.app.gateway.gateway_models import (
    GatewayCapabilities,
    GatewayDiscovery,
    GatewayMessageResult,
    GatewaySessionHandle,
    GatewayStatus,
)
from openclaw_gui.app.models.event import EventType
from openclaw_gui.app.models.personality import Personality
from openclaw_gui.app.models.project import Project
from openclaw_gui.app.models.session import SessionStatus
from openclaw_gui.app.persistence.repositories import (
    PersonalityRepository,
    ProjectRepository,
    SessionEventRepository,
    SessionRepository,
)


class FakeGateway(GatewayAdapter):
    def __init__(
        self,
        *,
        start_handle: GatewaySessionHandle | None = None,
        restore_handle: GatewaySessionHandle | None = None,
        message_result: GatewayMessageResult | None = None,
        start_error: Exception | None = None,
        send_error: Exception | None = None,
        restore_error: Exception | None = None,
        end_error: Exception | None = None,
    ) -> None:
        self.start_handle = start_handle
        self.restore_handle = restore_handle
        self.message_result = message_result
        self.start_error = start_error
        self.send_error = send_error
        self.restore_error = restore_error
        self.end_error = end_error

    def ping(self) -> bool:
        return True

    def get_status(self) -> GatewayStatus:
        return GatewayStatus(
            connected=True,
            endpoint="http://gateway.test",
            capabilities=GatewayCapabilities(),
            discovery=GatewayDiscovery(gateway_url="http://gateway.test"),
        )

    def list_capabilities(self) -> GatewayCapabilities:
        return GatewayCapabilities()

    def start_session(
        self,
        project_context: dict[str, object],
        personality_context: dict[str, object],
    ) -> GatewaySessionHandle:
        if self.start_error is not None:
            raise self.start_error
        return self.start_handle or GatewaySessionHandle(session_key="default-start")

    def send_message(self, session_handle: GatewaySessionHandle, text: str) -> GatewayMessageResult:
        if self.send_error is not None:
            raise self.send_error
        return self.message_result or GatewayMessageResult(
            session_key=session_handle.session_key,
            raw_payload={"content": f"echo:{text}"},
        )

    def restore_session(self, saved_state: dict[str, object]) -> GatewaySessionHandle:
        if self.restore_error is not None:
            raise self.restore_error
        return self.restore_handle or GatewaySessionHandle(session_key="default-restore")

    def end_session(self, session_handle: GatewaySessionHandle) -> None:
        if self.end_error is not None:
            raise self.end_error


def make_session_controller(database, file_store, gateway: GatewayAdapter) -> SessionController:
    project_repository = ProjectRepository(database)
    personality_repository = PersonalityRepository(database)
    return SessionController(
        SessionRepository(database),
        SessionEventRepository(database),
        file_store,
        gateway,
        project_repository,
        personality_repository,
    )


def seed_project_and_personality(database, file_store: Path) -> tuple[str, str]:
    project_repository = ProjectRepository(database)
    personality_repository = PersonalityRepository(database)
    project_repository.create(Project(id="project-1", name="Alpha", root_path=str(file_store)))
    personality_repository.create(
        Personality(
            id="persona-1",
            name="Default",
            storage_path=str(file_store),
        )
    )
    return "project-1", "persona-1"


def test_start_session_persists_gateway_metadata(database, file_store) -> None:
    project_id, personality_id = seed_project_and_personality(database, file_store.data_root)
    controller = make_session_controller(
        database,
        file_store,
        FakeGateway(start_handle=GatewaySessionHandle("session-key-1", "gateway-ref-1")),
    )

    result = controller.start_session(project_id=project_id, personality_id=personality_id)

    assert result.gateway_session_started is True
    assert result.session.gateway_session_ref == "gateway-ref-1"
    metadata = file_store.read_session_metadata(project_id, result.session.id)
    assert metadata["status"] == "active"
    assert metadata["gateway"]["session_key"] == "session-key-1"
    events = controller.list_session_events(result.session.id)
    assert events[0].event_type == EventType.STATUS
    assert events[0].content == "Session started."


def test_send_message_records_gateway_error_without_losing_user_message(database, file_store) -> None:
    project_id, personality_id = seed_project_and_personality(database, file_store.data_root)
    controller = make_session_controller(
        database,
        file_store,
        FakeGateway(
            start_handle=GatewaySessionHandle("session-key-2", "gateway-ref-2"),
            send_error=GatewayUnsupportedOperationError(
                "chat.send is unavailable",
                operation="send_message",
                endpoint="http://gateway.test",
            ),
        ),
    )
    session = controller.start_session(project_id=project_id, personality_id=personality_id).session

    result = controller.send_message(session_id=session.id, text="Hello gateway")

    assert result.user_event.content == "Hello gateway"
    assert result.assistant_event is None
    assert result.error_event is not None
    assert result.error_event.event_type == EventType.ERROR
    events = controller.list_session_events(session.id)
    assert [event.event_type for event in events] == [
        EventType.STATUS,
        EventType.USER,
        EventType.ERROR,
    ]


def test_suspend_restore_and_restart_update_session_lifecycle(database, file_store) -> None:
    project_id, personality_id = seed_project_and_personality(database, file_store.data_root)
    controller = make_session_controller(
        database,
        file_store,
        FakeGateway(
            start_handle=GatewaySessionHandle("session-key-3", "gateway-ref-3"),
            restore_error=GatewayUnsupportedOperationError(
                "restore is unavailable",
                operation="restore_session",
                endpoint="http://gateway.test",
            ),
            end_error=GatewayUnsupportedOperationError(
                "end is unavailable",
                operation="end_session",
                endpoint="http://gateway.test",
            ),
        ),
    )

    started = controller.start_session(project_id=project_id, personality_id=personality_id).session
    suspended = controller.suspend_session(started.id, summary_text="## Summary")
    restored = controller.restore_session(started.id)
    restarted = controller.restart_session(started.id)

    assert suspended.status == SessionStatus.SUSPENDED
    assert file_store.session_dir(project_id, started.id).joinpath("summary.md").read_text(encoding="utf-8") == "## Summary"
    assert restored.status == SessionStatus.ACTIVE
    assert controller.get_session(started.id).status == SessionStatus.ARCHIVED
    assert restarted.session.status == SessionStatus.ACTIVE

    restarted_metadata = json.loads(restarted.session.metadata_json or "{}")
    assert restarted_metadata["restart_of"] == started.id


def test_switch_project_suspends_current_and_restores_target_session(database, file_store) -> None:
    project_repository = ProjectRepository(database)
    personality_repository = PersonalityRepository(database)
    project_repository.create(Project(id="project-1", name="Alpha", root_path=str(file_store.data_root)))
    project_repository.create(Project(id="project-2", name="Beta", root_path=str(file_store.data_root)))
    personality_repository.create(
        Personality(
            id="persona-1",
            name="Default",
            storage_path=str(file_store.data_root),
        )
    )
    controller = make_session_controller(
        database,
        file_store,
        FakeGateway(start_handle=GatewaySessionHandle("session-key-4")),
    )

    current = controller.start_session(project_id="project-1", personality_id="persona-1").session
    target = controller.start_session(project_id="project-2", personality_id="persona-1").session
    controller.suspend_session(target.id)

    result = controller.switch_project(
        target_project_id="project-2",
        current_session_id=current.id,
    )

    assert result.suspended_session is not None
    assert result.suspended_session.project_id == "project-1"
    assert result.suspended_session.status == SessionStatus.SUSPENDED
    assert result.active_session is not None
    assert result.active_session.id == target.id
    assert result.active_session.status == SessionStatus.ACTIVE
    assert result.restored_existing is True
