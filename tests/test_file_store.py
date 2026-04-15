from __future__ import annotations

import json

from openclaw_gui.app.models.event import EventType, SessionEvent


def test_file_store_writes_transcript_files(file_store) -> None:
    event = SessionEvent(
        id="event-1",
        session_id="session-1",
        event_type=EventType.USER,
        content="Test message",
    )

    markdown_path = file_store.append_transcript_markdown(
        "project-1",
        "session-1",
        role="user",
        content="Test message",
        timestamp=event.timestamp.isoformat(),
    )
    jsonl_path = file_store.append_transcript_event_jsonl("project-1", "session-1", event)

    markdown = markdown_path.read_text(encoding="utf-8")
    jsonl_line = jsonl_path.read_text(encoding="utf-8").strip()

    assert "Test message" in markdown
    payload = json.loads(jsonl_line)
    assert payload["event_type"] == "user"
    assert payload["content"] == "Test message"


def test_file_store_writes_and_reads_session_metadata(file_store) -> None:
    metadata = {"status": "active", "messages": 1}

    path = file_store.write_session_metadata("project-1", "session-1", metadata)
    loaded = file_store.read_session_metadata("project-1", "session-1")

    assert path.exists()
    assert loaded == metadata
