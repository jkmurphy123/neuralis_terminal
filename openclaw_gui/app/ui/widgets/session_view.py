"""Conversation/session panel for the active project session."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.models.event import EventType, SessionEvent
from openclaw_gui.app.models.session import SessionRecord


class SessionView(QWidget):
    """Structured transcript view with banner, composer, and send action."""

    send_requested = Signal(str)

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.banner = QFrame()
        self.banner.setFrameShape(QFrame.Shape.StyledPanel)
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        self.project_label = QLabel("Project: none")
        self.personality_label = QLabel("Personality: none")
        self.session_label = QLabel("Session: none")
        self.status_label = QLabel("Status: idle")
        banner_layout.addWidget(self.project_label)
        banner_layout.addWidget(self.personality_label)
        banner_layout.addWidget(self.session_label)
        banner_layout.addStretch(1)
        banner_layout.addWidget(self.status_label)

        self.transcript_list = QListWidget()
        self.transcript_list.setAlternatingRowColors(True)
        self.transcript_list.setWordWrap(True)

        self.composer = QTextEdit()
        self.composer.setPlaceholderText("Send a message to the active session.")
        self.composer.setFixedHeight(110)

        composer_row = QHBoxLayout()
        composer_row.addWidget(self.composer, stretch=1)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self._emit_send_requested)
        composer_row.addWidget(self.send_button)

        layout.addWidget(self.banner)
        layout.addWidget(self.transcript_list, stretch=1)
        layout.addLayout(composer_row)

        self.set_context()
        self.set_events([])
        self.set_send_enabled(False)

    def set_context(
        self,
        *,
        project_name: str | None = None,
        personality_name: str | None = None,
        session: SessionRecord | None = None,
    ) -> None:
        self.project_label.setText(f"Project: {project_name or 'none'}")
        self.personality_label.setText(f"Personality: {personality_name or 'none'}")
        self.session_label.setText(f"Session: {session.id if session is not None else 'none'}")
        status = session.status.value if session is not None else "idle"
        self.status_label.setText(f"Status: {status}")

    def set_events(self, events: Iterable[SessionEvent]) -> None:
        self.transcript_list.clear()
        rendered = False
        for event in events:
            item = QListWidgetItem(self._format_event(event))
            item.setData(Qt.ItemDataRole.UserRole, event)
            item.setForeground(self._event_color(event.event_type))
            self.transcript_list.addItem(item)
            rendered = True
        if not rendered:
            self.transcript_list.addItem("No transcript yet. Start a session or restore one to continue.")
        self.transcript_list.scrollToBottom()

    def set_send_enabled(self, enabled: bool) -> None:
        self.composer.setEnabled(enabled)
        self.send_button.setEnabled(enabled)

    def clear_composer(self) -> None:
        self.composer.clear()

    def composer_text(self) -> str:
        return self.composer.toPlainText()

    def _emit_send_requested(self) -> None:
        self.send_requested.emit(self.composer.toPlainText())

    def _format_event(self, event: SessionEvent) -> str:
        timestamp = event.timestamp.astimezone().strftime("%H:%M:%S")
        role = event.event_type.value.upper()
        return f"[{timestamp}] {role}\n{event.content}"

    def _event_color(self, event_type: EventType):
        if event_type == EventType.USER:
            return QColor("#1d4ed8")
        if event_type == EventType.ASSISTANT:
            return QColor("#0f766e")
        if event_type == EventType.ERROR:
            return QColor("#b42318")
        if event_type in {EventType.STATUS, EventType.SYSTEM, EventType.PERSONALITY_CHANGE}:
            return QColor("#6b7280")
        return QColor("#111827")
