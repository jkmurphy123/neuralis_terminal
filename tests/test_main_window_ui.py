from __future__ import annotations

import httpx

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.controllers.personality_controller import PersonalityController
from openclaw_gui.app.controllers.project_controller import ProjectController
from openclaw_gui.app.controllers.session_controller import SessionController
from openclaw_gui.app.gateway.gateway_client import GatewayClient
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


def build_controller(database, file_store) -> AppController:
    settings = AppSettings(
        gateway_url="http://gateway.test",
        data_root=str(file_store.data_root),
    )
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
