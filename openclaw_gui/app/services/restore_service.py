"""Startup restore and UI-state persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass

from openclaw_gui.app.persistence.file_store import FileStore


@dataclass(slots=True)
class StartupState:
    """Persisted lightweight restore state for the main window."""

    project_id: str | None = None
    personality_id: str | None = None
    session_id: str | None = None
    composer_draft: str = ""


class RestoreService:
    """Persist and recover last active UI/session context."""

    def __init__(self, file_store: FileStore) -> None:
        self.file_store = file_store

    def load_startup_state(self) -> StartupState:
        state = self.file_store.read_ui_state()
        return StartupState(
            project_id=self._optional_string(state.get("project_id")),
            personality_id=self._optional_string(state.get("personality_id")),
            session_id=self._optional_string(state.get("session_id")),
            composer_draft=str(state.get("composer_draft", "")),
        )

    def save_startup_state(
        self,
        *,
        project_id: str | None,
        personality_id: str | None,
        session_id: str | None,
        composer_draft: str = "",
    ) -> None:
        self.file_store.write_ui_state(
            {
                "project_id": project_id,
                "personality_id": personality_id,
                "session_id": session_id,
                "composer_draft": composer_draft,
            }
        )

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
