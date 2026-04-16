"""Top bar widget with gateway connectivity actions."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.gateway.gateway_models import GatewayStatus


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
    """Control strip preserving the future widget boundaries."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._gateway_test_thread: QThread | None = None
        self._gateway_test_worker: GatewayConnectionWorker | None = None

        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Project"))
        layout.addWidget(QComboBox())
        layout.addWidget(QLabel("Personality"))
        layout.addWidget(QComboBox())
        for label in (
            "New Session",
            "Suspend",
            "Restore",
            "Restart",
            "Projects",
            "Personalities",
            "Open Folder",
        ):
            layout.addWidget(QPushButton(label))
        self.test_connection_button = QPushButton("Test Connection")
        self.test_connection_button.clicked.connect(self._start_gateway_connection_test)
        layout.addWidget(self.test_connection_button)
        layout.addWidget(QPushButton("Settings"))
        layout.addStretch(1)
        self.gateway_state_label = QLabel("Gateway: Idle")
        layout.addWidget(self.gateway_state_label)
        layout.addWidget(QLabel("Session: Idle"))

    def _update_gateway_state(self, state: str, *, tooltip: str | None = None) -> None:
        self.gateway_state_label.setText(f"Gateway: {state}")
        self.gateway_state_label.setToolTip(tooltip or state)

    @Slot()
    def _start_gateway_connection_test(self) -> None:
        if self._gateway_test_thread is not None:
            return

        self.test_connection_button.setEnabled(False)
        self._update_gateway_state("Testing", tooltip="Testing gateway connection...")
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
            self._update_gateway_state("Error", tooltip=message)
            self.controller.status_messages.publish_error(message, source="gateway")
            return

        summary = self.controller.gateway_status_summary()
        gateway_state = "Connected" if status is not None and status.connected else "Unavailable"
        self._update_gateway_state(gateway_state, tooltip=summary)
        if status is not None:
            self.controller.status_messages.publish_success(summary, source="gateway")
