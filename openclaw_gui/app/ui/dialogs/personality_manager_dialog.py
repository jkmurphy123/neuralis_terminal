"""Personality manager dialog placeholder."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class PersonalityManagerDialog(QDialog):
    """Stub dialog reserved for personality CRUD UI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Personalities")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Personality management will be implemented in a later milestone."))
