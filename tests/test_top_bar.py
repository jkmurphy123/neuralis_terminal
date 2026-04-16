from __future__ import annotations

import time
from dataclasses import dataclass

from openclaw_gui.app.gateway.gateway_models import GatewayCapabilities, GatewayStatus
from openclaw_gui.app.ui.widgets.top_bar import TopBar


@dataclass
class FakeController:
    gateway_status: GatewayStatus | None = None
    error: Exception | None = None
    calls: int = 0

    def test_gateway_connection(self) -> GatewayStatus:
        self.calls += 1
        if self.error is not None:
            raise self.error
        self.gateway_status = GatewayStatus(
            connected=True,
            endpoint="http://gateway.test",
            detail="HTTP health endpoint is live.",
            auth_configured=True,
            capabilities=GatewayCapabilities(health_endpoint=True),
        )
        return self.gateway_status

    def gateway_status_summary(self) -> str:
        if self.gateway_status is None:
            return "Configured: http://gateway.test"
        return self.gateway_status.detail


def wait_for_button_enabled(qapp, bar: TopBar, timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not bar.test_connection_button.isEnabled():
        qapp.processEvents()
        if time.monotonic() >= deadline:
            raise AssertionError("Timed out waiting for gateway test to finish")
        time.sleep(0.01)
    qapp.processEvents()


def test_top_bar_test_connection_success_updates_gateway_label(monkeypatch, qapp) -> None:
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "openclaw_gui.app.ui.widgets.top_bar.QMessageBox.information",
        lambda parent, title, message: messages.append((title, message)),
    )
    controller = FakeController()
    bar = TopBar(controller)

    bar.test_connection_button.click()
    wait_for_button_enabled(qapp, bar)

    assert controller.calls == 1
    assert "HTTP health endpoint is live." in bar.gateway_label.text()
    assert messages == [("Gateway Connection", "HTTP health endpoint is live.")]


def test_top_bar_test_connection_failure_shows_warning(monkeypatch, qapp) -> None:
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "openclaw_gui.app.ui.widgets.top_bar.QMessageBox.warning",
        lambda parent, title, message: warnings.append((title, message)),
    )
    controller = FakeController(error=RuntimeError("connection refused"))
    bar = TopBar(controller)

    bar.test_connection_button.click()
    wait_for_button_enabled(qapp, bar)

    assert controller.calls == 1
    assert "Gateway connection check failed: connection refused" in bar.gateway_label.text()
    assert warnings == [
        ("Gateway Connection Failed", "Gateway connection check failed: connection refused")
    ]
