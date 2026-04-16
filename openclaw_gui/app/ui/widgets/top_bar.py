"""Top bar widget with gateway connectivity actions."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
        self.gateway_label = QLabel()
        self._update_gateway_label(controller.gateway_status_summary())
        layout.addWidget(self.gateway_label)
        layout.addWidget(QLabel("Session: Idle"))

    def _update_gateway_label(self, summary: str) -> None:
        text = f"Gateway: {summary}"
        self.gateway_label.setText(text)
        self.gateway_label.setToolTip(summary)

    @Slot()
    def _start_gateway_connection_test(self) -> None:
        if self._gateway_test_thread is not None:
            return

        self.test_connection_button.setEnabled(False)
        self._update_gateway_label("Testing connection...")

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
            self._update_gateway_label(message)
            QMessageBox.warning(self, "Gateway Connection Failed", message)
            return

        summary = self.controller.gateway_status_summary()
        self._update_gateway_label(summary)
        if status is not None:
            QMessageBox.information(self, "Gateway Connection", summary)
