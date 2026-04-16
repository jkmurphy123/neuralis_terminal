"""Dialog for browsing and reopening project session history."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.models.session import SessionRecord, SessionStatus


class SessionHistoryDialog(QDialog):
    """Browse persisted sessions for one project and choose one to reopen or restore."""

    def __init__(
        self,
        controller: AppController,
        *,
        project_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.project_id = project_id
        self.selected_session_id: str | None = None
        self.restore_requested = False
        self.setWindowTitle("Session History")
        self.resize(980, 560)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.session_list = QListWidget()
        self.session_list.currentItemChanged.connect(self._load_selected_session)
        splitter.addWidget(self.session_list)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.meta_label = QLabel("Select a session to inspect its details.")
        self.transcript_preview = QTextEdit()
        self.transcript_preview.setReadOnly(True)
        detail_layout.addWidget(self.meta_label)
        detail_layout.addWidget(self.transcript_preview, stretch=1)

        button_row = QHBoxLayout()
        self.open_button = QPushButton("Open Selected")
        self.open_button.clicked.connect(self._accept_open)
        button_row.addWidget(self.open_button)

        self.restore_button = QPushButton("Restore Selected")
        self.restore_button.clicked.connect(self._accept_restore)
        button_row.addWidget(self.restore_button)

        button_row.addStretch(1)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        button_row.addWidget(self.close_button)
        detail_layout.addLayout(button_row)

        splitter.addWidget(detail)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self._update_action_state(None)
        self._reload_sessions()

    def _reload_sessions(self) -> None:
        sessions = self.controller.session_controller.list_project_sessions(self.project_id)
        self.session_list.clear()
        for session in sessions:
            label = (
                f"{session.status.value.upper()}  "
                f"{session.last_activity_at.astimezone().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            item.setToolTip(session.id)
            self.session_list.addItem(item)
        if self.session_list.count():
            self.session_list.setCurrentRow(0)

    def _load_selected_session(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,  # noqa: ARG002
    ) -> None:
        if current is None:
            self.selected_session_id = None
            self.meta_label.setText("Select a session to inspect its details.")
            self.transcript_preview.clear()
            self._update_action_state(None)
            return

        session_id = current.data(Qt.ItemDataRole.UserRole)
        session = self.controller.session_controller.get_session(session_id)
        if session is None:
            self.selected_session_id = None
            self._update_action_state(None)
            return

        self.selected_session_id = session.id
        events = self.controller.session_controller.list_session_events(session.id)
        self.meta_label.setText(
            " | ".join(
                [
                    f"Session {session.id}",
                    f"Status {session.status.value}",
                    f"Personality {session.personality_id}",
                    f"Events {len(events)}",
                ]
            )
        )
        preview = []
        for event in events:
            timestamp = event.timestamp.astimezone().strftime("%H:%M:%S")
            preview.append(f"[{timestamp}] {event.event_type.value.upper()}\n{event.content}")
        self.transcript_preview.setPlainText("\n\n".join(preview) or "No events recorded.")
        self._update_action_state(session)

    def _update_action_state(self, session: SessionRecord | None) -> None:
        enabled = session is not None
        self.open_button.setEnabled(enabled)
        self.restore_button.setEnabled(
            session is not None and session.status == SessionStatus.SUSPENDED
        )

    def _accept_open(self) -> None:
        if self.selected_session_id is None:
            return
        self.restore_requested = False
        self.accept()

    def _accept_restore(self) -> None:
        if self.selected_session_id is None:
            return
        self.restore_requested = True
        self.accept()
