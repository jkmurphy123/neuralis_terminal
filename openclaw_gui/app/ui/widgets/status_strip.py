"""Placeholder status strip widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget

from openclaw_gui.app.controllers.app_controller import AppController


class StatusStrip(QWidget):
    """Minimal bottom status strip with persisted settings context."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Project: none"))
        layout.addWidget(QLabel("Personality: none"))
        layout.addWidget(QLabel("Session: none"))
        layout.addStretch(1)
        layout.addWidget(QLabel(f"Data root: {controller.settings.data_root}"))
