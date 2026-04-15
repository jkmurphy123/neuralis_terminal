"""Session history dialog placeholder."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class SessionHistoryDialog(QDialog):
    """Stub dialog reserved for browsing session history."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Session History")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Session history UI will be implemented in a later milestone."))
