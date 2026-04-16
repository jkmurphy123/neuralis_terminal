"""Main application window for the Milestone 4 core UI."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMainWindow, QMessageBox, QVBoxLayout, QWidget

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.models.personality import Personality
from openclaw_gui.app.models.project import Project
from openclaw_gui.app.models.session import SessionRecord, SessionStatus
from openclaw_gui.app.services.restore_service import RestoreService
from openclaw_gui.app.ui.dialogs.personality_manager_dialog import PersonalityManagerDialog
from openclaw_gui.app.ui.dialogs.project_manager_dialog import ProjectManagerDialog
from openclaw_gui.app.ui.dialogs.session_history_dialog import SessionHistoryDialog
from openclaw_gui.app.ui.dialogs.settings_dialog import SettingsDialog
from openclaw_gui.app.ui.widgets.session_view import SessionView
from openclaw_gui.app.ui.widgets.status_messages_panel import StatusMessagesPanel
from openclaw_gui.app.ui.widgets.status_strip import StatusStrip
from openclaw_gui.app.ui.widgets.top_bar import TopBar


class MainWindow(QMainWindow):
    """Application shell coordinating the core UI widgets."""

    logger = logging.getLogger(__name__)

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.restore_service = RestoreService(controller.file_store)
        self.active_project: Project | None = None
        self.active_personality: Personality | None = None
        self.active_session: SessionRecord | None = None
        self.projects: list[Project] = []
        self.personalities: list[Personality] = []

        self.setWindowTitle("Neuralis Terminal")
        self.resize(1280, 860)

        central = QWidget(self)
        layout = QVBoxLayout(central)

        self.top_bar = TopBar(controller)
        self.session_view = SessionView(controller)
        self.status_strip = StatusStrip(controller)
        self.status_messages_panel = StatusMessagesPanel(controller)

        layout.addWidget(self.top_bar)
        layout.addWidget(self.session_view, stretch=1)
        layout.addWidget(self.status_strip)
        layout.addWidget(self.status_messages_panel)

        self.setCentralWidget(central)
        self._connect_signals()
        self._configure_autosave()
        self._load_initial_state()

    def _configure_autosave(self) -> None:
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave_state)
        self.autosave_timer.start(max(1, self.controller.settings.autosave_seconds) * 1000)

    def _connect_signals(self) -> None:
        self.top_bar.project_changed.connect(self._handle_project_changed)
        self.top_bar.personality_changed.connect(self._handle_personality_changed)
        self.top_bar.new_session_requested.connect(self._handle_new_session)
        self.top_bar.suspend_requested.connect(self._handle_suspend_session)
        self.top_bar.restore_requested.connect(self._handle_restore_session)
        self.top_bar.restart_requested.connect(self._handle_restart_session)
        self.top_bar.projects_requested.connect(self._open_projects_dialog)
        self.top_bar.personalities_requested.connect(self._open_personalities_dialog)
        self.top_bar.settings_requested.connect(self._open_settings_dialog)
        self.top_bar.open_folder_requested.connect(self._open_active_project_folder)
        self.top_bar.gateway_test_completed.connect(self._handle_gateway_test_completed)
        self.session_view.send_requested.connect(self._handle_send_message)
        self.session_view.history_requested.connect(self._open_session_history_dialog)

    def _load_initial_state(self) -> None:
        self.projects = self.controller.project_controller.list_projects()
        self.personalities = self.controller.personality_controller.list_personalities()
        startup_state = self.restore_service.load_startup_state()

        self.active_project = (
            self._project_by_id(startup_state.project_id) or (self.projects[0] if self.projects else None)
        )
        self.active_personality = (
            self._personality_by_id(startup_state.personality_id)
            or self._default_personality_for_project(self.active_project)
        )
        self.active_session = None
        if startup_state.session_id is not None:
            saved_session = self.controller.session_controller.get_session(startup_state.session_id)
            if saved_session is not None:
                self.active_session = saved_session
        if self.active_session is None:
            self.active_session = (
                self.controller.session_controller.get_latest_restorable_session(self.active_project.id)
                if self.active_project is not None
                else None
            )
        if self.active_session is not None:
            if self.active_session.status == SessionStatus.SUSPENDED:
                try:
                    self.active_session = self.controller.session_controller.restore_session(
                        self.active_session.id
                    )
                except Exception as exc:
                    self.logger.exception("Failed to restore startup session")
                    self.controller.status_messages.publish_error(
                        f"Failed to restore saved session on startup: {exc}",
                        source="startup",
                    )
            self.active_personality = self._personality_by_id(self.active_session.personality_id)
        self.session_view.set_composer_text(startup_state.composer_draft)
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        current_project_id = self.active_project.id if self.active_project is not None else None
        current_personality_id = (
            self.active_personality.id if self.active_personality is not None else None
        )
        self.top_bar.set_projects(self.projects, current_project_id=current_project_id)
        self.top_bar.set_personalities(
            self.personalities,
            current_personality_id=current_personality_id,
        )

        session_state = self.active_session.status.value if self.active_session is not None else "idle"
        self.top_bar.set_session_state(session_state)
        if self.controller.gateway_status is None:
            self.top_bar.set_gateway_state("Configured", tooltip=self.controller.settings.gateway_url)
        else:
            gateway_state = "Connected" if self.controller.gateway_status.connected else "Unavailable"
            self.top_bar.set_gateway_state(
                gateway_state,
                tooltip=self.controller.gateway_status_summary(),
            )

        can_restore = (
            self.active_session is not None and self.active_session.status == SessionStatus.SUSPENDED
        )
        if not can_restore and self.active_project is not None:
            latest = self.controller.session_controller.get_latest_restorable_session(self.active_project.id)
            can_restore = latest is not None and latest.status == SessionStatus.SUSPENDED

        self.top_bar.set_action_state(
            has_project=self.active_project is not None,
            has_personality=self.active_personality is not None,
            has_session=self.active_session is not None,
            can_restore=can_restore,
        )

        events = (
            self.controller.session_controller.list_session_events(self.active_session.id)
            if self.active_session is not None
            else []
        )
        self.session_view.set_context(
            project_name=self.active_project.name if self.active_project is not None else None,
            personality_name=(
                self.active_personality.name if self.active_personality is not None else None
            ),
            session=self.active_session,
        )
        self.session_view.set_events(events)
        self.session_view.set_send_enabled(
            self.active_session is not None and self.active_session.status == SessionStatus.ACTIVE
        )
        self.status_strip.update_runtime_status(
            project_name=self.active_project.name if self.active_project is not None else None,
            personality_name=(
                self.active_personality.name if self.active_personality is not None else None
            ),
            session_id=self.active_session.id if self.active_session is not None else None,
            session_status=(
                self.active_session.status.value if self.active_session is not None else None
            ),
            project_root=self.active_project.root_path if self.active_project is not None else None,
            last_activity=(
                self.active_session.last_activity_at if self.active_session is not None else None
            ),
            message_count=len(events),
            gateway_endpoint=self.controller.settings.gateway_url,
        )
        self._persist_ui_state()

    def _set_active_project(self, project_id: str | None) -> None:
        self.active_project = self._project_by_id(project_id)
        if self.active_project is None:
            self.active_session = None
        else:
            self.active_session = self.controller.session_controller.get_latest_restorable_session(
                self.active_project.id
            )
            if self.active_session is not None:
                self.active_personality = self._personality_by_id(self.active_session.personality_id)
        if self.active_project is not None and self.active_personality is None:
            self.active_personality = self._default_personality_for_project(self.active_project)

    def _handle_project_changed(self, project_id: str | None) -> None:
        if project_id is None:
            self._set_active_project(None)
            self._refresh_ui()
            return
        if self.active_project is not None and self.active_project.id == project_id:
            return
        try:
            result = self.controller.session_controller.switch_project(
                target_project_id=project_id,
                current_session_id=self.active_session.id if self.active_session is not None else None,
            )
        except Exception as exc:
            self.logger.exception("Failed to switch project")
            self._publish_error(f"Failed to switch project: {exc}")
            self._refresh_ui()
            return

        self.active_project = self._project_by_id(project_id)
        self.active_session = result.active_session
        if self.active_session is not None:
            self.active_personality = self._personality_by_id(self.active_session.personality_id)
        elif self.active_project is not None:
            self.active_personality = self._default_personality_for_project(self.active_project)
        self.controller.status_messages.publish_debug(
            f"Switched to project {self.active_project.name}.",
            source="ui",
        )
        self._refresh_ui()

    def _handle_personality_changed(self, personality_id: str | None) -> None:
        self.active_personality = self._personality_by_id(personality_id)
        if self.active_session is not None and self.active_personality is not None:
            try:
                self.active_session = self.controller.session_controller.change_session_personality(
                    session_id=self.active_session.id,
                    personality_id=self.active_personality.id,
                )
            except Exception as exc:
                self.logger.exception("Failed to change personality")
                self._publish_error(f"Failed to change personality: {exc}")
        self._refresh_ui()

    def _handle_new_session(self) -> None:
        if self.active_project is None or self.active_personality is None:
            self._publish_warning("Select both a project and a personality before starting a session.")
            return
        try:
            result = self.controller.session_controller.start_session(
                project_id=self.active_project.id,
                personality_id=self.active_personality.id,
            )
        except Exception as exc:
            self.logger.exception("Failed to start session")
            self._publish_error(f"Failed to start session: {exc}")
            return
        self.active_session = result.session
        self._refresh_ui()

    def _handle_suspend_session(self) -> None:
        if self.active_session is None:
            self._publish_warning("There is no active session to suspend.")
            return
        try:
            self.active_session = self.controller.session_controller.suspend_session(
                self.active_session.id
            )
        except Exception as exc:
            self.logger.exception("Failed to suspend session")
            self._publish_error(f"Failed to suspend session: {exc}")
            return
        self._refresh_ui()

    def _handle_restore_session(self) -> None:
        target = self.active_session
        if target is None and self.active_project is not None:
            target = self.controller.session_controller.get_latest_restorable_session(
                self.active_project.id
            )
        if target is None:
            self._publish_warning("There is no suspended session available to restore.")
            return
        try:
            self.active_session = self.controller.session_controller.restore_session(target.id)
        except Exception as exc:
            self.logger.exception("Failed to restore session")
            self._publish_error(f"Failed to restore session: {exc}")
            return
        self._refresh_ui()

    def _handle_restart_session(self) -> None:
        if self.active_session is None:
            self._publish_warning("There is no session available to restart.")
            return
        try:
            result = self.controller.session_controller.restart_session(
                self.active_session.id,
                personality_id=self.active_personality.id if self.active_personality is not None else None,
            )
        except Exception as exc:
            self.logger.exception("Failed to restart session")
            self._publish_error(f"Failed to restart session: {exc}")
            return
        self.active_session = result.session
        self._refresh_ui()

    def _handle_send_message(self, text: str) -> None:
        if not text.strip():
            return
        if self.active_session is None:
            self._handle_new_session()
        if self.active_session is None:
            return
        if self.active_session.status != SessionStatus.ACTIVE:
            self._publish_warning("Restore or start a fresh session before sending messages.")
            return
        try:
            result = self.controller.session_controller.send_message(
                session_id=self.active_session.id,
                text=text,
            )
        except Exception as exc:
            self.logger.exception("Failed to send message")
            self._publish_error(f"Failed to send message: {exc}")
            return
        self.active_session = result.session
        self.session_view.clear_composer()
        self._refresh_ui()

    def _open_projects_dialog(self) -> None:
        dialog = ProjectManagerDialog(self.controller, self)
        dialog.exec()
        self._load_initial_state()
        self._refresh_ui()

    def _open_personalities_dialog(self) -> None:
        dialog = PersonalityManagerDialog(self.controller, self)
        dialog.exec()
        self.personalities = self.controller.personality_controller.list_personalities()
        if self.active_personality is not None:
            self.active_personality = self._personality_by_id(self.active_personality.id)
        if self.active_session is not None:
            self.active_personality = self._personality_by_id(self.active_session.personality_id)
        self._refresh_ui()

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.controller, self)
        if dialog.exec():
            self.restore_service = RestoreService(self.controller.file_store)
            self.autosave_timer.start(max(1, self.controller.settings.autosave_seconds) * 1000)
            self.projects = self.controller.project_controller.list_projects()
            self.personalities = self.controller.personality_controller.list_personalities()
            self.active_project = None
            self.active_personality = None
            self.active_session = None
            self._load_initial_state()
            self._refresh_ui()

    def _open_session_history_dialog(self) -> None:
        if self.active_project is None:
            self._publish_warning("Select a project before browsing session history.")
            return
        dialog = SessionHistoryDialog(
            self.controller,
            project_id=self.active_project.id,
            parent=self,
        )
        if not dialog.exec() or dialog.selected_session_id is None:
            return

        session = self.controller.session_controller.get_session(dialog.selected_session_id)
        if session is None:
            self._publish_error("Selected session no longer exists.")
            return
        try:
            self.active_session = (
                self.controller.session_controller.restore_session(session.id)
                if dialog.restore_requested
                else session
            )
        except Exception as exc:
            self.logger.exception("Failed to open session history entry")
            self._publish_error(f"Failed to open session history entry: {exc}")
            return
        self.active_personality = self._personality_by_id(self.active_session.personality_id)
        self._refresh_ui()

    def _open_active_project_folder(self) -> None:
        if self.active_project is None:
            self._publish_warning("Select a project before opening its folder.")
            return
        root = Path(self.active_project.root_path)
        if not root.exists():
            self._publish_error(f"Project path does not exist: {root}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))

    def _autosave_state(self) -> None:
        if self.active_session is not None:
            try:
                self.active_session = self.controller.session_controller.autosave_session(
                    self.active_session.id,
                    composer_draft=self.session_view.composer_text(),
                )
            except Exception as exc:
                self.logger.exception("Autosave failed")
                self.controller.status_messages.publish_error(
                    f"Autosave failed: {exc}",
                    source="autosave",
                )
        self._persist_ui_state()

    def _handle_gateway_test_completed(
        self,
        status: object | None,
        error: object | None,
    ) -> None:
        if error is None and status is not None:
            self._refresh_ui()

    def _publish_warning(self, message: str) -> None:
        self.controller.status_messages.publish_warning(message, source="ui")
        QMessageBox.warning(self, "Neuralis Terminal", message)

    def _publish_error(self, message: str) -> None:
        self.controller.status_messages.publish_error(message, source="ui")
        QMessageBox.critical(self, "Neuralis Terminal", message)

    def _persist_ui_state(self) -> None:
        self.restore_service.save_startup_state(
            project_id=self.active_project.id if self.active_project is not None else None,
            personality_id=self.active_personality.id if self.active_personality is not None else None,
            session_id=self.active_session.id if self.active_session is not None else None,
            composer_draft=self.session_view.composer_text(),
        )

    def _project_by_id(self, project_id: str | None) -> Project | None:
        if project_id is None:
            return None
        for project in self.projects:
            if project.id == project_id:
                return project
        return None

    def _personality_by_id(self, personality_id: str | None) -> Personality | None:
        if personality_id is None:
            return None
        for personality in self.personalities:
            if personality.id == personality_id:
                return personality
        return None

    def _default_personality_for_project(self, project: Project | None) -> Personality | None:
        if not self.personalities:
            return None
        preferred_id = None
        if project is not None and project.default_personality_id is not None:
            preferred_id = project.default_personality_id
        elif self.controller.settings.default_personality_id is not None:
            preferred_id = self.controller.settings.default_personality_id
        return self._personality_by_id(preferred_id) or self.personalities[0]

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._autosave_state()
        super().closeEvent(event)
