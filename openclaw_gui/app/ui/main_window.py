"""Minimal main window for the Milestone 1 shell."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.ui.widgets.session_view import SessionView
from openclaw_gui.app.ui.widgets.status_strip import StatusStrip
from openclaw_gui.app.ui.widgets.top_bar import TopBar


class MainWindow(QMainWindow):
    """Minimal 3-region window that proves the app boots cleanly."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Neuralis Terminal")
        self.resize(1200, 800)

        central = QWidget(self)
        layout = QVBoxLayout(central)

        self.top_bar = TopBar(controller)
        self.session_view = SessionView(controller)
        self.status_strip = StatusStrip(controller)

        layout.addWidget(self.top_bar)
        layout.addWidget(self.session_view, stretch=1)
        layout.addWidget(self.status_strip)

        self.setCentralWidget(central)
