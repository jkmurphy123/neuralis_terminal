"""Settings dialog placeholder."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class SettingsDialog(QDialog):
    """Stub dialog reserved for settings editing."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Settings")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings UI will be implemented in a later milestone."))
