"""Placeholder top bar widget."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from openclaw_gui.app.controllers.app_controller import AppController


class TopBar(QWidget):
    """Minimal control strip preserving the future widget boundaries."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller

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
            "Settings",
            "Open Folder",
        ):
            layout.addWidget(QPushButton(label))
        layout.addStretch(1)
        self.gateway_label = QLabel(f"Gateway: {controller.gateway_status_summary()}")
        layout.addWidget(self.gateway_label)
        layout.addWidget(QLabel("Session: Idle"))
