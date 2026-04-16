"""Top-level controller composition for Milestone 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openclaw_gui.app.controllers.personality_controller import PersonalityController
from openclaw_gui.app.controllers.project_controller import ProjectController
from openclaw_gui.app.controllers.session_controller import SessionController
from openclaw_gui.app.gateway.gateway_client import GatewayClient
from openclaw_gui.app.gateway.gateway_models import GatewayStatus
from openclaw_gui.app.models.settings import AppSettings, SettingsStore
from openclaw_gui.app.persistence.db import Database
from openclaw_gui.app.persistence.file_store import FileStore
from openclaw_gui.app.persistence.repositories import (
    PersonalityRepository,
    ProjectRepository,
    SessionEventRepository,
    SessionRepository,
)
from openclaw_gui.app.services.status_message_bus import StatusMessageBus


@dataclass(slots=True)
class AppController:
    """Own the application-scoped services and controllers."""

    bootstrap_settings_store: SettingsStore
    settings_store: SettingsStore
    settings: AppSettings
    file_store: FileStore
    database: Database
    gateway_client: GatewayClient
    gateway_status: GatewayStatus | None
    status_messages: StatusMessageBus
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
        project_repository = ProjectRepository(database)
        personality_repository = PersonalityRepository(database)
        session_repository = SessionRepository(database)
        event_repository = SessionEventRepository(database)
        gateway_client = GatewayClient.from_settings(settings)
        return cls(
            bootstrap_settings_store=bootstrap_store,
            settings_store=settings_store,
            settings=settings,
            file_store=file_store,
            database=database,
            gateway_client=gateway_client,
            gateway_status=None,
            status_messages=StatusMessageBus(),
            project_controller=ProjectController(project_repository),
            personality_controller=PersonalityController(
                personality_repository,
                file_store,
            ),
            session_controller=SessionController(
                session_repository,
                event_repository,
                file_store,
                gateway_client,
                project_repository,
                personality_repository,
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
        self.gateway_client.close()
        self.settings = settings
        self.bootstrap_settings_store.save(settings)
        self.settings_store.save(settings)
        self.gateway_client = GatewayClient.from_settings(settings)
        self.session_controller.gateway = self.gateway_client
        self.gateway_status = None

    def test_gateway_connection(self) -> GatewayStatus:
        """Probe the configured gateway and cache the normalized status."""
        self.gateway_status = self.gateway_client.get_status()
        return self.gateway_status

    def gateway_status_summary(self) -> str:
        """Return a short human-readable gateway status string."""
        if self.gateway_status is None:
            return f"Configured: {self.settings.gateway_url}"
        return self.gateway_status.detail
