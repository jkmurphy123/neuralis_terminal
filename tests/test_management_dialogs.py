from __future__ import annotations

import httpx

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.controllers.personality_controller import PersonalityController
from openclaw_gui.app.controllers.project_controller import ProjectController
from openclaw_gui.app.controllers.session_controller import SessionController
from openclaw_gui.app.gateway.gateway_client import GatewayClient
from openclaw_gui.app.models.settings import AppSettings, SettingsStore
from openclaw_gui.app.persistence.repositories import (
    PersonalityRepository,
    ProjectRepository,
    SessionEventRepository,
    SessionRepository,
)
from openclaw_gui.app.services.status_message_bus import StatusMessageBus
from openclaw_gui.app.ui.dialogs.personality_manager_dialog import PersonalityManagerDialog
from openclaw_gui.app.ui.dialogs.project_manager_dialog import ProjectManagerDialog
from openclaw_gui.app.ui.dialogs.session_history_dialog import SessionHistoryDialog


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


def seed_project_and_personality(controller: AppController) -> tuple[str, str]:
    project = controller.project_controller.create_project(
        name="Alpha",
        root_path=str(controller.file_store.data_root),
        description="Primary project",
    )
    personality = controller.personality_controller.create_personality(
        name="Default",
        description="Default personality",
        soul_text="Soul",
        agents_text="Agents",
        identity_text="Identity",
    )
    return project.id, personality.id


def test_project_manager_dialog_can_create_project(database, file_store, qapp) -> None:
    controller = build_controller(database, file_store)
    dialog = ProjectManagerDialog(controller)
    dialog.name_edit.setText("Alpha")
    dialog.description_edit.setPlainText("Primary project")
    dialog.root_path_edit.setText(str(file_store.data_root))

    dialog._save_project()
    qapp.processEvents()

    projects = controller.project_controller.list_projects()
    assert len(projects) == 1
    assert projects[0].name == "Alpha"
    assert dialog.project_list.count() == 1


def test_personality_manager_dialog_can_create_bundle(database, file_store, qapp) -> None:
    controller = build_controller(database, file_store)
    dialog = PersonalityManagerDialog(controller)
    dialog.name_edit.setText("Default")
    dialog.description_edit.setPlainText("Primary personality")
    dialog.soul_edit.setPlainText("Soul text")
    dialog.agents_edit.setPlainText("Agents text")
    dialog.identity_edit.setPlainText("Identity text")

    dialog._save_personality()
    qapp.processEvents()

    personalities = controller.personality_controller.list_personalities()
    assert len(personalities) == 1
    bundle = controller.personality_controller.load_bundle(personalities[0].id)
    assert bundle["SOUL.md"] == "Soul text"
    assert bundle["AGENTS.md"] == "Agents text"
    assert bundle["IDENTITY.md"] == "Identity text"


def test_session_history_dialog_lists_sessions_and_enables_restore(database, file_store, qapp) -> None:
    controller = build_controller(database, file_store)
    project_id, personality_id = seed_project_and_personality(controller)
    session = controller.session_controller.start_session(
        project_id=project_id,
        personality_id=personality_id,
    ).session
    controller.session_controller.suspend_session(session.id)

    dialog = SessionHistoryDialog(controller, project_id=project_id)
    qapp.processEvents()

    assert dialog.session_list.count() == 1
    assert dialog.selected_session_id == session.id
    assert dialog.restore_button.isEnabled() is True
    assert "Session" in dialog.meta_label.text()
