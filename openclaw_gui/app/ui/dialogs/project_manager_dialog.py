"""Project manager dialog with CRUD controls."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from openclaw_gui.app.controllers.app_controller import AppController
class ProjectManagerDialog(QDialog):
    """Manage project references without touching on-disk project folders."""

    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.current_project_id: str | None = None
        self.setWindowTitle("Projects")
        self.resize(920, 520)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._load_selected_project)
        splitter.addWidget(self.project_list)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        form.addRow("Name", self.name_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setFixedHeight(100)
        form.addRow("Description", self.description_edit)

        root_row = QHBoxLayout()
        self.root_path_edit = QLineEdit()
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_root_path)
        root_row.addWidget(self.root_path_edit, stretch=1)
        root_row.addWidget(browse_button)
        root_widget = QWidget()
        root_widget.setLayout(root_row)
        form.addRow("Root Path", root_widget)

        self.default_personality_combo = QComboBox()
        self._reload_personality_options()
        form.addRow("Default Personality", self.default_personality_combo)

        editor_layout.addLayout(form)
        editor_layout.addWidget(
            QLabel("Deleting a project here removes only the GUI reference, not the actual folder.")
        )

        button_row = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._prepare_new_project)
        button_row.addWidget(self.new_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_project)
        button_row.addWidget(self.save_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_project)
        button_row.addWidget(self.delete_button)

        button_row.addStretch(1)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.close_button)
        editor_layout.addLayout(button_row)

        splitter.addWidget(editor)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self._reload_projects()
        self._prepare_new_project()

    def _reload_projects(self, *, select_project_id: str | None = None) -> None:
        projects = self.controller.project_controller.list_projects()
        self.project_list.clear()
        selected_row = -1
        for row, project in enumerate(projects):
            item = QListWidgetItem(project.name)
            item.setData(Qt.ItemDataRole.UserRole, project.id)
            item.setToolTip(project.root_path)
            self.project_list.addItem(item)
            if project.id == select_project_id:
                selected_row = row
        if selected_row >= 0:
            self.project_list.setCurrentRow(selected_row)

    def _reload_personality_options(self, *, selected_id: str | None = None) -> None:
        self.default_personality_combo.clear()
        self.default_personality_combo.addItem("None", None)
        selected_index = 0
        for index, personality in enumerate(
            self.controller.personality_controller.list_personalities(),
            start=1,
        ):
            self.default_personality_combo.addItem(personality.name, personality.id)
            if personality.id == selected_id:
                selected_index = index
        self.default_personality_combo.setCurrentIndex(selected_index)

    def _prepare_new_project(self) -> None:
        self.current_project_id = None
        self.name_edit.clear()
        self.description_edit.clear()
        self.root_path_edit.clear()
        self._reload_personality_options()
        self.project_list.blockSignals(True)
        self.project_list.setCurrentItem(None)
        self.project_list.clearSelection()
        self.project_list.blockSignals(False)

    def _load_selected_project(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,  # noqa: ARG002
    ) -> None:
        if current is None:
            return
        project_id = current.data(Qt.ItemDataRole.UserRole)
        project = self.controller.project_controller.repository.get(project_id)
        if project is None:
            return
        self.current_project_id = project.id
        self.name_edit.setText(project.name)
        self.description_edit.setPlainText(project.description)
        self.root_path_edit.setText(project.root_path)
        self._reload_personality_options(selected_id=project.default_personality_id)

    def _browse_root_path(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Project Root",
            self.root_path_edit.text() or str(Path.home()),
        )
        if selected:
            self.root_path_edit.setText(selected)

    def _save_project(self) -> None:
        try:
            if self.current_project_id is None:
                project = self.controller.project_controller.create_project(
                    name=self.name_edit.text(),
                    description=self.description_edit.toPlainText(),
                    root_path=self.root_path_edit.text(),
                    default_personality_id=self.default_personality_combo.currentData(),
                )
            else:
                existing = self.controller.project_controller.repository.get(self.current_project_id)
                if existing is None:
                    raise ValueError("Selected project no longer exists.")
                existing.name = self.name_edit.text().strip()
                existing.description = self.description_edit.toPlainText()
                existing.root_path = self.root_path_edit.text().strip()
                existing.default_personality_id = self.default_personality_combo.currentData()
                project = self.controller.project_controller.update_project(existing)
        except Exception as exc:
            QMessageBox.warning(self, "Project Error", str(exc))
            return

        self.current_project_id = project.id
        self.controller.status_messages.publish_success(
            f"Saved project {project.name}.",
            source="projects",
        )
        self._reload_projects(select_project_id=project.id)

    def _delete_project(self) -> None:
        if self.current_project_id is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Project Reference",
            "Remove this project from the GUI? The actual project folder will not be deleted.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.controller.project_controller.delete_project(self.current_project_id)
        except Exception as exc:
            QMessageBox.warning(self, "Project Error", str(exc))
            return

        self.controller.status_messages.publish_warning(
            "Project reference deleted.",
            source="projects",
        )
        self._reload_projects()
        self._prepare_new_project()
