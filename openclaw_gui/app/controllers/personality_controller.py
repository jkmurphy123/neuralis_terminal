"""Personality controller for metadata and bundle files."""

from __future__ import annotations

import uuid

from openclaw_gui.app.models.personality import Personality
from openclaw_gui.app.persistence.file_store import FileStore
from openclaw_gui.app.persistence.repositories import PersonalityRepository


class PersonalityController:
    """Manage persisted personality metadata and markdown bundle files."""

    def __init__(self, repository: PersonalityRepository, file_store: FileStore) -> None:
        self.repository = repository
        self.file_store = file_store

    def list_personalities(self) -> list[Personality]:
        return self.repository.list_all()

    def create_personality(
        self,
        *,
        name: str,
        description: str = "",
        soul_text: str = "",
        agents_text: str = "",
        identity_text: str = "",
    ) -> Personality:
        if not name.strip():
            raise ValueError("Personality name must not be empty.")
        personality_id = str(uuid.uuid4())
        storage_path = self.file_store.ensure_personality_bundle(
            personality_id,
            soul_text=soul_text,
            agents_text=agents_text,
            identity_text=identity_text,
            metadata={"name": name.strip(), "description": description},
        )
        personality = Personality(
            id=personality_id,
            name=name.strip(),
            description=description,
            storage_path=str(storage_path),
        )
        return self.repository.create(personality)

    def update_personality(
        self,
        personality: Personality,
        *,
        soul_text: str,
        agents_text: str,
        identity_text: str,
    ) -> Personality:
        self.file_store.ensure_personality_bundle(
            personality.id,
            soul_text=soul_text,
            agents_text=agents_text,
            identity_text=identity_text,
            metadata={
                "name": personality.name,
                "description": personality.description,
            },
        )
        return self.repository.update(personality)

    def load_bundle(self, personality_id: str) -> dict[str, str]:
        return self.file_store.read_personality_bundle(personality_id)

    def delete_personality(self, personality_id: str) -> None:
        self.repository.delete(personality_id)
