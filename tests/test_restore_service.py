from __future__ import annotations

from openclaw_gui.app.services.restore_service import RestoreService


def test_restore_service_round_trip(file_store) -> None:
    service = RestoreService(file_store)

    service.save_startup_state(
        project_id="project-1",
        personality_id="persona-1",
        session_id="session-1",
        composer_draft="hello",
    )
    state = service.load_startup_state()

    assert state.project_id == "project-1"
    assert state.personality_id == "persona-1"
    assert state.session_id == "session-1"
    assert state.composer_draft == "hello"
