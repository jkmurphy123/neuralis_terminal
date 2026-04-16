from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt

from openclaw_gui.app.models.status_message import StatusMessageLevel
from openclaw_gui.app.services.status_message_bus import StatusMessageBus
from openclaw_gui.app.ui.widgets.status_strip import StatusStrip


def test_status_strip_shows_placeholder_until_messages_arrive(qapp) -> None:
    controller = SimpleNamespace(status_messages=StatusMessageBus())
    strip = StatusStrip(controller)

    assert strip.message_list.count() == 1
    assert strip.message_list.item(0).text() == "No status messages yet."


def test_status_strip_renders_published_messages(qapp) -> None:
    bus = StatusMessageBus()
    controller = SimpleNamespace(status_messages=bus)
    strip = StatusStrip(controller)

    bus.publish_success("Gateway connection established.", source="gateway")
    qapp.processEvents()

    assert strip.message_list.count() == 1
    item = strip.message_list.item(0)
    message = item.data(Qt.ItemDataRole.UserRole)
    assert message.level == StatusMessageLevel.SUCCESS
    assert "gateway: Gateway connection established." in item.text()
