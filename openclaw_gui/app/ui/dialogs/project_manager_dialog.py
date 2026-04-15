"""Project manager dialog placeholder."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class ProjectManagerDialog(QDialog):
    """Stub dialog reserved for project CRUD UI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Projects")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Project management will be implemented in a later milestone."))
