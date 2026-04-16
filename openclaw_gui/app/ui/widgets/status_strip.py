"""Runtime status strip for current project, session, and gateway details."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from openclaw_gui.app.controllers.app_controller import AppController


class StatusStrip(QWidget):
    """Show compact runtime/session metadata separate from the message log."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.project_value = self._add_row(layout, 0, "Project")
        self.personality_value = self._add_row(layout, 0, "Personality", column_offset=2)
        self.session_value = self._add_row(layout, 1, "Session ID")
        self.session_status_value = self._add_row(layout, 1, "Session Status", column_offset=2)
        self.project_root_value = self._add_row(layout, 2, "Project Root")
        self.last_activity_value = self._add_row(layout, 2, "Last Activity", column_offset=2)
        self.message_count_value = self._add_row(layout, 3, "Message Count")
        self.gateway_value = self._add_row(layout, 3, "Gateway Endpoint", column_offset=2)

        self.update_runtime_status()

    def update_runtime_status(
        self,
        *,
        project_name: str | None = None,
        personality_name: str | None = None,
        session_id: str | None = None,
        session_status: str | None = None,
        project_root: str | None = None,
        last_activity: datetime | None = None,
        message_count: int | None = None,
        gateway_endpoint: str | None = None,
    ) -> None:
        self.project_value.setText(project_name or "none")
        self.personality_value.setText(personality_name or "none")
        self.session_value.setText(session_id or "none")
        self.session_status_value.setText(session_status or "idle")
        self.project_root_value.setText(project_root or "none")
        self.last_activity_value.setText(
            last_activity.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            if last_activity is not None
            else "n/a"
        )
        self.message_count_value.setText(str(message_count) if message_count is not None else "0")
        self.gateway_value.setText(gateway_endpoint or self.controller.settings.gateway_url)

    def _add_row(
        self,
        layout: QGridLayout,
        row: int,
        label_text: str,
        *,
        column_offset: int = 0,
    ) -> QLabel:
        layout.addWidget(QLabel(f"{label_text}:"), row, column_offset)
        value = QLabel()
        value.setTextInteractionFlags(value.textInteractionFlags())
        layout.addWidget(value, row, column_offset + 1)
        return value
