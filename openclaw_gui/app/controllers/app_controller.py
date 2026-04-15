"""Top-level controller composition for Milestone 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openclaw_gui.app.controllers.personality_controller import PersonalityController
from openclaw_gui.app.controllers.project_controller import ProjectController
from openclaw_gui.app.controllers.session_controller import SessionController
from openclaw_gui.app.models.settings import AppSettings, SettingsStore
from openclaw_gui.app.persistence.db import Database
from openclaw_gui.app.persistence.file_store import FileStore
from openclaw_gui.app.persistence.repositories import (
    PersonalityRepository,
    ProjectRepository,
    SessionEventRepository,
    SessionRepository,
)


@dataclass(slots=True)
class AppController:
    """Own the application-scoped services and controllers."""

    bootstrap_settings_store: SettingsStore
    settings_store: SettingsStore
    settings: AppSettings
    file_store: FileStore
    database: Database
    project_controller: ProjectController
    personality_controller: PersonalityController
    session_controller: SessionController

    @classmethod
    def create_default(cls) -> "AppController":
        """Build the default application graph from persisted settings."""
        bootstrap_store = SettingsStore(Path(AppSettings().data_root) / "settings.json")
        settings = bootstrap_store.load()
        file_store = FileStore(Path(settings.data_root))
        settings_store = SettingsStore(file_store.settings_path)
        if settings_store.path.exists():
            settings = settings_store.load()
            file_store = FileStore(Path(settings.data_root))
            settings_store = SettingsStore(file_store.settings_path)
        database = Database(file_store.database_path)
        return cls(
            bootstrap_settings_store=bootstrap_store,
            settings_store=settings_store,
            settings=settings,
            file_store=file_store,
            database=database,
            project_controller=ProjectController(ProjectRepository(database)),
            personality_controller=PersonalityController(
                PersonalityRepository(database),
                file_store,
            ),
            session_controller=SessionController(
                SessionRepository(database),
                SessionEventRepository(database),
                file_store,
            ),
        )

    def initialize(self) -> None:
        """Initialize local storage and persist settings if absent."""
        self.file_store.initialize()
        self.database.initialize()
        self.bootstrap_settings_store.save(self.settings)
        if not self.settings_store.path.exists():
            self.settings_store.save(self.settings)

    def save_settings(self, settings: AppSettings) -> None:
        """Persist updated settings and refresh in-memory state."""
        self.settings = settings
        self.bootstrap_settings_store.save(settings)
        self.settings_store.save(settings)
