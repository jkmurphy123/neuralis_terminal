"""Personality manager dialog with bundle editing."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from openclaw_gui.app.controllers.app_controller import AppController


class PersonalityManagerDialog(QDialog):
    """Manage personality metadata and the three markdown bundle files."""

    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.current_personality_id: str | None = None
        self.setWindowTitle("Personalities")
        self.resize(1040, 620)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.personality_list = QListWidget()
        self.personality_list.currentItemChanged.connect(self._load_selected_personality)
        splitter.addWidget(self.personality_list)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        form.addRow("Name", self.name_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setFixedHeight(90)
        form.addRow("Description", self.description_edit)

        editor_layout.addLayout(form)

        self.bundle_tabs = QTabWidget()
        self.soul_edit = QTextEdit()
        self.agents_edit = QTextEdit()
        self.identity_edit = QTextEdit()
        self.bundle_tabs.addTab(self.soul_edit, "SOUL.md")
        self.bundle_tabs.addTab(self.agents_edit, "AGENTS.md")
        self.bundle_tabs.addTab(self.identity_edit, "IDENTITY.md")
        editor_layout.addWidget(self.bundle_tabs, stretch=1)
        editor_layout.addWidget(
            QLabel("Each personality stores editable SOUL.md, AGENTS.md, and IDENTITY.md content.")
        )

        button_row = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._prepare_new_personality)
        button_row.addWidget(self.new_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_personality)
        button_row.addWidget(self.save_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_personality)
        button_row.addWidget(self.delete_button)

        button_row.addStretch(1)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.close_button)
        editor_layout.addLayout(button_row)

        splitter.addWidget(editor)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self._reload_personalities()
        self._prepare_new_personality()

    def _reload_personalities(self, *, select_personality_id: str | None = None) -> None:
        personalities = self.controller.personality_controller.list_personalities()
        self.personality_list.clear()
        selected_row = -1
        for row, personality in enumerate(personalities):
            item = QListWidgetItem(personality.name)
            item.setData(Qt.ItemDataRole.UserRole, personality.id)
            item.setToolTip(personality.storage_path)
            self.personality_list.addItem(item)
            if personality.id == select_personality_id:
                selected_row = row
        if selected_row >= 0:
            self.personality_list.setCurrentRow(selected_row)

    def _prepare_new_personality(self) -> None:
        self.current_personality_id = None
        self.name_edit.clear()
        self.description_edit.clear()
        self.soul_edit.clear()
        self.agents_edit.clear()
        self.identity_edit.clear()
        self.personality_list.blockSignals(True)
        self.personality_list.setCurrentItem(None)
        self.personality_list.clearSelection()
        self.personality_list.blockSignals(False)

    def _load_selected_personality(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,  # noqa: ARG002
    ) -> None:
        if current is None:
            return
        personality_id = current.data(Qt.ItemDataRole.UserRole)
        personality = self.controller.personality_controller.repository.get(personality_id)
        if personality is None:
            return
        bundle = self.controller.personality_controller.load_bundle(personality.id)
        self.current_personality_id = personality.id
        self.name_edit.setText(personality.name)
        self.description_edit.setPlainText(personality.description)
        self.soul_edit.setPlainText(bundle["SOUL.md"])
        self.agents_edit.setPlainText(bundle["AGENTS.md"])
        self.identity_edit.setPlainText(bundle["IDENTITY.md"])

    def _save_personality(self) -> None:
        try:
            if self.current_personality_id is None:
                personality = self.controller.personality_controller.create_personality(
                    name=self.name_edit.text(),
                    description=self.description_edit.toPlainText(),
                    soul_text=self.soul_edit.toPlainText(),
                    agents_text=self.agents_edit.toPlainText(),
                    identity_text=self.identity_edit.toPlainText(),
                )
            else:
                personality = self.controller.personality_controller.repository.get(
                    self.current_personality_id
                )
                if personality is None:
                    raise ValueError("Selected personality no longer exists.")
                personality.name = self.name_edit.text().strip()
                personality.description = self.description_edit.toPlainText()
                personality = self.controller.personality_controller.update_personality(
                    personality,
                    soul_text=self.soul_edit.toPlainText(),
                    agents_text=self.agents_edit.toPlainText(),
                    identity_text=self.identity_edit.toPlainText(),
                )
        except Exception as exc:
            QMessageBox.warning(self, "Personality Error", str(exc))
            return

        self.current_personality_id = personality.id
        self.controller.status_messages.publish_success(
            f"Saved personality {personality.name}.",
            source="personalities",
        )
        self._reload_personalities(select_personality_id=personality.id)

    def _delete_personality(self) -> None:
        if self.current_personality_id is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Personality",
            "Remove this personality from the GUI? Existing session history will be preserved.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.controller.personality_controller.delete_personality(self.current_personality_id)
        except Exception as exc:
            QMessageBox.warning(self, "Personality Error", str(exc))
            return

        self.controller.status_messages.publish_warning(
            "Personality deleted.",
            source="personalities",
        )
        self._reload_personalities()
        self._prepare_new_personality()
