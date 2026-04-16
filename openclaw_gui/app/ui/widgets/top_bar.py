"""Top control bar for the main window."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject, QSignalBlocker, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.gateway.gateway_models import GatewayStatus
from openclaw_gui.app.models.personality import Personality
from openclaw_gui.app.models.project import Project


class GatewayConnectionWorker(QObject):
    """Run the synchronous gateway test away from the GUI thread."""

    finished = Signal(object, object)

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller

    @Slot()
    def run(self) -> None:
        try:
            status = self.controller.test_gateway_connection()
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self.finished.emit(None, exc)
            return
        self.finished.emit(status, None)


class TopBar(QWidget):
    """Interactive control strip for selecting context and session actions."""

    project_changed = Signal(object)
    personality_changed = Signal(object)
    new_session_requested = Signal()
    suspend_requested = Signal()
    restore_requested = Signal()
    restart_requested = Signal()
    projects_requested = Signal()
    personalities_requested = Signal()
    settings_requested = Signal()
    open_folder_requested = Signal()
    gateway_test_completed = Signal(object, object)

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._gateway_test_thread: QThread | None = None
        self._gateway_test_worker: GatewayConnectionWorker | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Project"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(180)
        self.project_combo.currentIndexChanged.connect(self._emit_project_changed)
        layout.addWidget(self.project_combo)

        layout.addWidget(QLabel("Personality"))
        self.personality_combo = QComboBox()
        self.personality_combo.setMinimumWidth(180)
        self.personality_combo.currentIndexChanged.connect(self._emit_personality_changed)
        layout.addWidget(self.personality_combo)

        self.new_session_button = QPushButton("New Session")
        self.new_session_button.clicked.connect(self.new_session_requested)
        layout.addWidget(self.new_session_button)

        self.suspend_button = QPushButton("Suspend")
        self.suspend_button.clicked.connect(self.suspend_requested)
        layout.addWidget(self.suspend_button)

        self.restore_button = QPushButton("Restore")
        self.restore_button.clicked.connect(self.restore_requested)
        layout.addWidget(self.restore_button)

        self.restart_button = QPushButton("Restart")
        self.restart_button.clicked.connect(self.restart_requested)
        layout.addWidget(self.restart_button)

        self.projects_button = QPushButton("Projects...")
        self.projects_button.clicked.connect(self.projects_requested)
        layout.addWidget(self.projects_button)

        self.personalities_button = QPushButton("Personalities...")
        self.personalities_button.clicked.connect(self.personalities_requested)
        layout.addWidget(self.personalities_button)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.settings_requested)
        layout.addWidget(self.settings_button)

        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.clicked.connect(self.open_folder_requested)
        layout.addWidget(self.open_folder_button)

        self.test_connection_button = QPushButton("Test Connection")
        self.test_connection_button.clicked.connect(self._start_gateway_connection_test)
        layout.addWidget(self.test_connection_button)

        layout.addStretch(1)

        self.gateway_state_label = QLabel("Gateway: Idle")
        self.gateway_state_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.gateway_state_label)

        self.session_state_label = QLabel("Session: Idle")
        self.session_state_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.session_state_label)

    def set_projects(
        self,
        projects: Iterable[Project],
        *,
        current_project_id: str | None,
    ) -> None:
        blocker = QSignalBlocker(self.project_combo)
        self.project_combo.clear()
        self.project_combo.addItem("Select project", None)
        selected_index = 0
        for index, project in enumerate(projects, start=1):
            self.project_combo.addItem(project.name, project.id)
            if project.id == current_project_id:
                selected_index = index
        self.project_combo.setCurrentIndex(selected_index)
        del blocker

    def set_personalities(
        self,
        personalities: Iterable[Personality],
        *,
        current_personality_id: str | None,
    ) -> None:
        blocker = QSignalBlocker(self.personality_combo)
        self.personality_combo.clear()
        self.personality_combo.addItem("Select personality", None)
        selected_index = 0
        for index, personality in enumerate(personalities, start=1):
            self.personality_combo.addItem(personality.name, personality.id)
            if personality.id == current_personality_id:
                selected_index = index
        self.personality_combo.setCurrentIndex(selected_index)
        del blocker

    def set_gateway_state(self, state: str, *, tooltip: str | None = None) -> None:
        self.gateway_state_label.setText(f"Gateway: {state}")
        self.gateway_state_label.setToolTip(tooltip or state)

    def set_session_state(self, state: str, *, tooltip: str | None = None) -> None:
        self.session_state_label.setText(f"Session: {state}")
        self.session_state_label.setToolTip(tooltip or state)

    def set_action_state(
        self,
        *,
        has_project: bool,
        has_personality: bool,
        has_session: bool,
        can_restore: bool,
    ) -> None:
        can_start = has_project and has_personality
        self.new_session_button.setEnabled(can_start)
        self.suspend_button.setEnabled(has_session)
        self.restore_button.setEnabled(can_restore)
        self.restart_button.setEnabled(has_session and can_start)
        self.open_folder_button.setEnabled(has_project)

    @Slot()
    def _emit_project_changed(self) -> None:
        self.project_changed.emit(self.project_combo.currentData())

    @Slot()
    def _emit_personality_changed(self) -> None:
        self.personality_changed.emit(self.personality_combo.currentData())

    @Slot()
    def _start_gateway_connection_test(self) -> None:
        if self._gateway_test_thread is not None:
            return

        self.test_connection_button.setEnabled(False)
        self.set_gateway_state("Testing", tooltip="Testing gateway connection...")
        self.controller.status_messages.publish_debug(
            "Testing gateway connection.",
            source="gateway",
        )

        thread = QThread(self)
        worker = GatewayConnectionWorker(self.controller)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_gateway_connection_result)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_gateway_test_thread)

        self._gateway_test_thread = thread
        self._gateway_test_worker = worker
        thread.start()

    @Slot()
    def _clear_gateway_test_thread(self) -> None:
        self._gateway_test_thread = None
        self._gateway_test_worker = None

    @Slot(object, object)
    def _handle_gateway_connection_result(
        self,
        status: GatewayStatus | None,
        error: Exception | None,
    ) -> None:
        self.test_connection_button.setEnabled(True)
        if error is not None:
            message = f"Gateway connection check failed: {error}"
            self.set_gateway_state("Error", tooltip=message)
            self.controller.status_messages.publish_error(message, source="gateway")
            self.gateway_test_completed.emit(None, error)
            return

        summary = self.controller.gateway_status_summary()
        gateway_state = "Connected" if status is not None and status.connected else "Unavailable"
        self.set_gateway_state(gateway_state, tooltip=summary)
        if status is not None:
            self.controller.status_messages.publish_success(summary, source="gateway")
        self.gateway_test_completed.emit(status, None)
