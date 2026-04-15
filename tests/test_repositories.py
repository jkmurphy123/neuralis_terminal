from __future__ import annotations

import json
from pathlib import Path

from openclaw_gui.app.models.event import EventType, SessionEvent
from openclaw_gui.app.models.personality import Personality
from openclaw_gui.app.models.project import Project
from openclaw_gui.app.models.session import SessionRecord, SessionStatus
from openclaw_gui.app.persistence.file_store import FileStore
from openclaw_gui.app.persistence.repositories import (
    PersonalityRepository,
    ProjectRepository,
    SessionEventRepository,
    SessionRepository,
)


def test_project_repository_create_read_update_delete(database, tmp_path: Path) -> None:
    repository = ProjectRepository(database)
    project = Project(id="project-1", name="Alpha", root_path=str(tmp_path))

    repository.create(project)
    loaded = repository.get("project-1")

    assert loaded is not None
    assert loaded.name == "Alpha"
    assert repository.list_all()[0].id == "project-1"

    loaded.description = "Updated project"
    updated = repository.update(loaded)

    assert updated.description == "Updated project"
    assert repository.get("project-1").description == "Updated project"

    repository.delete("project-1")
    assert repository.get("project-1") is None


def test_personality_repository_create_and_read(database, file_store: FileStore) -> None:
    repository = PersonalityRepository(database)
    bundle_path = file_store.ensure_personality_bundle(
        "persona-1",
        soul_text="Soul",
        agents_text="Agents",
        identity_text="Identity",
        metadata={"name": "Default"},
    )
    personality = Personality(
        id="persona-1",
        name="Default",
        description="Base personality",
        storage_path=str(bundle_path),
    )

    repository.create(personality)
    loaded = repository.get("persona-1")

    assert loaded is not None
    assert loaded.storage_path == str(bundle_path)
    assert repository.list_all()[0].name == "Default"


def test_session_repository_round_trip(database, file_store: FileStore) -> None:
    project_repo = ProjectRepository(database)
    personality_repo = PersonalityRepository(database)
    session_repo = SessionRepository(database)

    project_repo.create(Project(id="project-1", name="Alpha", root_path=str(file_store.data_root)))
    personality_repo.create(
        Personality(
            id="persona-1",
            name="Default",
            storage_path=str(file_store.ensure_personality_bundle("persona-1")),
        )
    )
    files = file_store.initialize_session_files("project-1", "session-1")
    session = SessionRecord(
        id="session-1",
        project_id="project-1",
        personality_id="persona-1",
        transcript_path=str(files["transcript_md"]),
        summary_path=str(files["summary_md"]),
        metadata_json=json.dumps({"state": "new"}),
        status=SessionStatus.ACTIVE,
    )

    session_repo.create(session)
    loaded = session_repo.get("session-1")

    assert loaded is not None
    assert loaded.project_id == "project-1"
    assert loaded.status == SessionStatus.ACTIVE
    assert session_repo.list_by_project("project-1")[0].id == "session-1"


def test_session_event_repository_round_trip(database, file_store: FileStore) -> None:
    project_repo = ProjectRepository(database)
    personality_repo = PersonalityRepository(database)
    session_repo = SessionRepository(database)
    event_repo = SessionEventRepository(database)

    project_repo.create(Project(id="project-1", name="Alpha", root_path=str(file_store.data_root)))
    personality_repo.create(
        Personality(
            id="persona-1",
            name="Default",
            storage_path=str(file_store.ensure_personality_bundle("persona-1")),
        )
    )
    files = file_store.initialize_session_files("project-1", "session-1")
    session_repo.create(
        SessionRecord(
            id="session-1",
            project_id="project-1",
            personality_id="persona-1",
            transcript_path=str(files["transcript_md"]),
        )
    )
    event = SessionEvent(
        id="event-1",
        session_id="session-1",
        event_type=EventType.USER,
        content="Hello",
    )

    event_repo.create(event)
    loaded = event_repo.list_by_session("session-1")

    assert len(loaded) == 1
    assert loaded[0].content == "Hello"
    assert loaded[0].event_type == EventType.USER
