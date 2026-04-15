"""Placeholder session view widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from openclaw_gui.app.controllers.app_controller import AppController


class SessionView(QWidget):
    """Minimal conversation panel placeholder."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Session View"))
        transcript = QTextEdit()
        transcript.setReadOnly(True)
        transcript.setPlainText(
            "Milestone 1 foundation loaded.\n\n"
            "Persistence, settings, and controllers are ready for later UI work."
        )
        composer = QTextEdit()
        composer.setPlaceholderText("Message input will be wired in a later milestone.")
        layout.addWidget(transcript, stretch=1)
        layout.addWidget(composer)
