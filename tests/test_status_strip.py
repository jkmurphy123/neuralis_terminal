from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from PySide6.QtCore import Qt

from openclaw_gui.app.models.status_message import StatusMessageLevel
from openclaw_gui.app.services.status_message_bus import StatusMessageBus
from openclaw_gui.app.ui.widgets.status_messages_panel import StatusMessagesPanel
from openclaw_gui.app.ui.widgets.status_strip import StatusStrip


def test_status_strip_renders_runtime_fields(qapp) -> None:
    controller = SimpleNamespace(settings=SimpleNamespace(gateway_url="http://gateway.test"))
    strip = StatusStrip(controller)

    strip.update_runtime_status(
        project_name="Alpha",
        personality_name="Default",
        session_id="session-1",
        session_status="active",
        project_root="/tmp/alpha",
        last_activity=datetime(2026, 4, 16, 12, 30, tzinfo=timezone.utc),
        message_count=4,
        gateway_endpoint="http://gateway.test",
    )

    assert strip.project_value.text() == "Alpha"
    assert strip.personality_value.text() == "Default"
    assert strip.session_value.text() == "session-1"
    assert strip.session_status_value.text() == "active"
    assert strip.project_root_value.text() == "/tmp/alpha"
    assert strip.message_count_value.text() == "4"
    assert strip.gateway_value.text() == "http://gateway.test"


def test_status_messages_panel_shows_placeholder_until_messages_arrive(qapp) -> None:
    controller = SimpleNamespace(status_messages=StatusMessageBus())
    panel = StatusMessagesPanel(controller)

    assert panel.message_list.count() == 1
    assert panel.message_list.item(0).text() == "No status messages yet."


def test_status_messages_panel_renders_published_messages(qapp) -> None:
    bus = StatusMessageBus()
    controller = SimpleNamespace(status_messages=bus)
    panel = StatusMessagesPanel(controller)

    bus.publish_success("Gateway connection established.", source="gateway")
    qapp.processEvents()

    assert panel.message_list.count() == 1
    item = panel.message_list.item(0)
    message = item.data(Qt.ItemDataRole.UserRole)
    assert message.level == StatusMessageLevel.SUCCESS
    assert "gateway: Gateway connection established." in item.text()
