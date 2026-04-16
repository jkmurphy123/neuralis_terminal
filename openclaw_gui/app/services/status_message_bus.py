"""Shared in-process status message bus for UI alerts."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from openclaw_gui.app.models.status_message import StatusMessage, StatusMessageLevel


class StatusMessageBus(QObject):
    """Publish reusable status messages to interested UI components."""

    message_added = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._messages: list[StatusMessage] = []

    @property
    def messages(self) -> tuple[StatusMessage, ...]:
        return tuple(self._messages)

    def publish(
        self,
        *,
        level: StatusMessageLevel,
        text: str,
        source: str = "app",
    ) -> StatusMessage:
        message = StatusMessage(level=level, text=text, source=source)
        self._messages.append(message)
        self.message_added.emit(message)
        return message

    def publish_error(self, text: str, *, source: str = "app") -> StatusMessage:
        return self.publish(level=StatusMessageLevel.ERROR, text=text, source=source)

    def publish_warning(self, text: str, *, source: str = "app") -> StatusMessage:
        return self.publish(level=StatusMessageLevel.WARNING, text=text, source=source)

    def publish_success(self, text: str, *, source: str = "app") -> StatusMessage:
        return self.publish(level=StatusMessageLevel.SUCCESS, text=text, source=source)

    def publish_debug(self, text: str, *, source: str = "app") -> StatusMessage:
        return self.publish(level=StatusMessageLevel.DEBUG, text=text, source=source)
