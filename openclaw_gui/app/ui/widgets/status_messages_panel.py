"""Bottom panel for reusable application status messages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.models.status_message import StatusMessage, StatusMessageLevel


class StatusMessagesPanel(QWidget):
    """Display shared application status messages in a dedicated bottom panel."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.header_label = QLabel("Status Messages")
        self.message_list = QListWidget()
        self.message_list.setAlternatingRowColors(True)
        self.message_list.setWordWrap(True)
        self.placeholder_item = QListWidgetItem("No status messages yet.")
        self.message_list.addItem(self.placeholder_item)

        layout.addWidget(self.header_label)
        layout.addWidget(self.message_list)

        for message in controller.status_messages.messages:
            self._append_message(message)
        controller.status_messages.message_added.connect(self._append_message)

    def _append_message(self, message: StatusMessage) -> None:
        if self.placeholder_item is not None:
            self.message_list.takeItem(self.message_list.row(self.placeholder_item))
            self.placeholder_item = None
        item = QListWidgetItem(self._format_message(message))
        item.setData(Qt.ItemDataRole.UserRole, message)
        item.setForeground(self._level_color(message.level))
        self.message_list.addItem(item)
        self.message_list.scrollToBottom()

    def _format_message(self, message: StatusMessage) -> str:
        timestamp = message.timestamp.strftime("%H:%M:%S")
        return f"[{timestamp}] {message.level.value.upper():7} {message.source}: {message.text}"

    def _level_color(self, level: StatusMessageLevel):
        from PySide6.QtGui import QColor

        if level == StatusMessageLevel.ERROR:
            return QColor("#b42318")
        if level == StatusMessageLevel.WARNING:
            return QColor("#b54708")
        if level == StatusMessageLevel.SUCCESS:
            return QColor("#027a48")
        return QColor("#475467")
