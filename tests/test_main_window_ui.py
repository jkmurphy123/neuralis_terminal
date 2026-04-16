from __future__ import annotations

import threading
import time

import httpx

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.controllers.personality_controller import PersonalityController
from openclaw_gui.app.controllers.project_controller import ProjectController
from openclaw_gui.app.controllers.session_controller import SessionController
from openclaw_gui.app.gateway.gateway_adapter import GatewayAdapter
from openclaw_gui.app.gateway.gateway_client import GatewayClient
from openclaw_gui.app.gateway.gateway_models import (
    GatewayCapabilities,
    GatewayDiscovery,
    GatewayMessageResult,
    GatewaySessionHandle,
    GatewayStatus,
)
from openclaw_gui.app.models.personality import Personality
from openclaw_gui.app.models.project import Project
from openclaw_gui.app.models.settings import AppSettings, SettingsStore
from openclaw_gui.app.persistence.repositories import (
    PersonalityRepository,
    ProjectRepository,
    SessionEventRepository,
    SessionRepository,
)
from openclaw_gui.app.services.status_message_bus import StatusMessageBus
from openclaw_gui.app.ui.main_window import MainWindow


class BlockingGateway(GatewayAdapter):
    def __init__(self) -> None:
        self.release_send = threading.Event()
        self.started_sessions: list[str] = []
        self.sent_messages: list[tuple[str, str]] = []

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
        session_key = f"{project_context['id']}-{personality_context['id']}"
        self.started_sessions.append(session_key)
        return GatewaySessionHandle(session_key=session_key, gateway_session_ref=session_key)

    def send_message(self, session_handle: GatewaySessionHandle, text: str) -> GatewayMessageResult:
        self.sent_messages.append((session_handle.session_key, text))
        self.release_send.wait(timeout=2.0)
        return GatewayMessageResult(
            session_key=session_handle.session_key,
            raw_payload={
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Background reply"}],
                }
            },
        )

    def restore_session(self, saved_state: dict[str, object]) -> GatewaySessionHandle:
        return GatewaySessionHandle(session_key=str(saved_state.get("session_id", "restored")))

    def end_session(self, session_handle: GatewaySessionHandle) -> None:
        return None


def build_controller(database, file_store, gateway_client: GatewayAdapter | None = None) -> AppController:
    settings = AppSettings(
        gateway_url="http://gateway.test",
        data_root=str(file_store.data_root),
    )
    if gateway_client is None:
        gateway_client = GatewayClient(
            "http://gateway.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"ok": True, "status": "live"})
            ),
        )
    project_repository = ProjectRepository(database)
    personality_repository = PersonalityRepository(database)
    session_repository = SessionRepository(database)
    event_repository = SessionEventRepository(database)
    return AppController(
        bootstrap_settings_store=SettingsStore(file_store.data_root / "bootstrap-settings.json"),
        settings_store=SettingsStore(file_store.settings_path),
        settings=settings,
        file_store=file_store,
        database=database,
        gateway_client=gateway_client,
        gateway_status=None,
        status_messages=StatusMessageBus(),
        project_controller=ProjectController(project_repository),
        personality_controller=PersonalityController(personality_repository, file_store),
        session_controller=SessionController(
            session_repository,
            event_repository,
            file_store,
            gateway_client,
            project_repository,
            personality_repository,
        ),
    )


def seed_project_and_personalities(controller: AppController) -> None:
    controller.project_controller.create_project(
        name="Alpha",
        root_path=str(controller.file_store.data_root),
        description="Primary project",
    )
    controller.project_controller.create_project(
        name="Beta",
        root_path=str(controller.file_store.data_root),
        description="Secondary project",
    )
    controller.personality_controller.create_personality(
        name="Default",
        description="Default personality",
        soul_text="Soul",
        agents_text="Agents",
        identity_text="Identity",
    )


def test_main_window_populates_runtime_state(database, file_store, qapp) -> None:
    controller = build_controller(database, file_store)
    seed_project_and_personalities(controller)

    window = MainWindow(controller)
    qapp.processEvents()

    assert window.top_bar.project_combo.count() == 3
    assert window.top_bar.personality_combo.count() == 2
    assert window.status_strip.project_value.text() == "Alpha"
    assert window.status_strip.personality_value.text() == "Default"


def test_main_window_switches_project_and_starts_session(database, file_store, qapp) -> None:
    controller = build_controller(database, file_store)
    seed_project_and_personalities(controller)

    window = MainWindow(controller)
    qapp.processEvents()

    window.top_bar.project_combo.setCurrentIndex(2)
    qapp.processEvents()
    assert window.status_strip.project_value.text() == "Beta"

    window.top_bar.new_session_button.click()
    qapp.processEvents()

    assert window.active_session is not None
    assert window.status_strip.session_status_value.text() == "active"
    assert window.session_view.status_label.text() == "Status: active"


def test_main_window_autosave_and_startup_restore(database, file_store, qapp) -> None:
    controller = build_controller(database, file_store)
    seed_project_and_personalities(controller)

    window = MainWindow(controller)
    qapp.processEvents()

    window.top_bar.new_session_button.click()
    qapp.processEvents()
    assert window.active_session is not None

    window.session_view.set_composer_text("Draft message")
    saved_session_id = window.active_session.id
    window._autosave_state()

    restored_controller = build_controller(database, file_store)
    restored_window = MainWindow(restored_controller)
    qapp.processEvents()

    assert restored_window.active_session is not None
    assert restored_window.active_session.id == saved_session_id
    assert restored_window.session_view.composer_text() == "Draft message"


def test_main_window_sends_message_without_blocking_ui(database, file_store, qapp) -> None:
    gateway = BlockingGateway()
    controller = build_controller(database, file_store, gateway_client=gateway)
    seed_project_and_personalities(controller)

    window = MainWindow(controller)
    qapp.processEvents()

    window.top_bar.new_session_button.click()
    qapp.processEvents()
    assert window.active_session is not None

    try:
        window.session_view.set_composer_text("Hello background gateway")
        window.session_view.send_button.click()
        for _ in range(50):
            qapp.processEvents()
            if window._send_thread is not None and gateway.sent_messages:
                break
            time.sleep(0.01)

        assert window._send_thread is not None
        assert window.session_view.send_button.text() == "Sending..."
        assert window.session_view.send_button.isEnabled() is False
        assert gateway.sent_messages

        gateway.release_send.set()
        for _ in range(50):
            qapp.processEvents()
            if window._send_thread is None:
                break
            time.sleep(0.01)

        assert window._send_thread is None
        assert window.session_view.send_button.text() == "Send"
        assert window.session_view.send_button.isEnabled() is True
        assert window.session_view.composer_text() == ""
        assert window.session_view.transcript_list.count() >= 3
        assert "Background reply" in window.session_view.transcript_list.item(
            window.session_view.transcript_list.count() - 1
        ).text()
    finally:
        gateway.release_send.set()
        for _ in range(50):
            qapp.processEvents()
            if window._send_thread is None:
                break
            time.sleep(0.01)
        window.close()
