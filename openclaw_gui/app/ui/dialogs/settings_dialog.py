"""Settings dialog for gateway and app storage configuration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.models.settings import AppSettings


class SettingsDialog(QDialog):
    """Edit persisted application settings."""

    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Settings")
        self.resize(640, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.gateway_url_edit = QLineEdit(controller.settings.gateway_url)
        form.addRow("Gateway URL", self.gateway_url_edit)

        self.gateway_token_edit = QLineEdit(controller.settings.gateway_token)
        self.gateway_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Gateway Token", self.gateway_token_edit)

        self.gateway_timeout_spin = QSpinBox()
        self.gateway_timeout_spin.setRange(1, 120)
        self.gateway_timeout_spin.setValue(int(controller.settings.gateway_timeout_seconds))
        form.addRow("Gateway Timeout (s)", self.gateway_timeout_spin)

        data_root_row = QHBoxLayout()
        self.data_root_edit = QLineEdit(controller.settings.data_root)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_data_root)
        data_root_row.addWidget(self.data_root_edit, stretch=1)
        data_root_row.addWidget(browse_button)
        data_root_widget = QWidget()
        data_root_widget.setLayout(data_root_row)
        form.addRow("App Data Root", data_root_widget)

        self.default_personality_combo = QComboBox()
        self.default_personality_combo.addItem("None", None)
        selected_personality_id = controller.settings.default_personality_id
        selected_index = 0
        for index, personality in enumerate(
            controller.personality_controller.list_personalities(),
            start=1,
        ):
            self.default_personality_combo.addItem(personality.name, personality.id)
            if personality.id == selected_personality_id:
                selected_index = index
        self.default_personality_combo.setCurrentIndex(selected_index)
        form.addRow("Default Personality", self.default_personality_combo)

        self.autosave_spin = QSpinBox()
        self.autosave_spin.setRange(5, 3600)
        self.autosave_spin.setSingleStep(5)
        self.autosave_spin.setValue(controller.settings.autosave_seconds)
        form.addRow("Autosave Seconds", self.autosave_spin)

        layout.addLayout(form)
        layout.addWidget(
            QLabel(
                "Use the top bar Test Connection action to verify the configured gateway "
                "without leaving the main window."
            )
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def build_settings(self) -> AppSettings:
        return AppSettings(
            gateway_url=self.gateway_url_edit.text().strip(),
            gateway_token=self.gateway_token_edit.text(),
            gateway_timeout_seconds=float(self.gateway_timeout_spin.value()),
            data_root=self.data_root_edit.text().strip(),
            default_personality_id=self.default_personality_combo.currentData(),
            autosave_seconds=self.autosave_spin.value(),
        )

    def _browse_data_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select App Data Root",
            self.data_root_edit.text() or str(Path.home()),
        )
        if selected:
            self.data_root_edit.setText(selected)

    def _handle_accept(self) -> None:
        settings = self.build_settings()
        if not settings.gateway_url:
            QMessageBox.warning(self, "Invalid Settings", "Gateway URL must not be empty.")
            return
        if not settings.data_root:
            QMessageBox.warning(self, "Invalid Settings", "App data root must not be empty.")
            return
        self.controller.save_settings(settings)
        self.controller.status_messages.publish_success(
            "Settings saved.",
            source="settings",
        )
        self.accept()
