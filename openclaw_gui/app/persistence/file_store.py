"""Filesystem-backed storage for personalities, transcripts, and exports."""

from __future__ import annotations

import json
from pathlib import Path

from openclaw_gui.app.models.event import SessionEvent


class FileStore:
    """Manage the app data directory layout described by the design docs."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root

    @property
    def database_path(self) -> Path:
        return self.data_root / "app.db"

    @property
    def settings_path(self) -> Path:
        return self.data_root / "settings.json"

    @property
    def personalities_root(self) -> Path:
        return self.data_root / "personalities"

    @property
    def projects_root(self) -> Path:
        return self.data_root / "projects"

    @property
    def exports_root(self) -> Path:
        return self.data_root / "exports"

    @property
    def logs_root(self) -> Path:
        return self.data_root / "logs"

    @property
    def log_path(self) -> Path:
        return self.logs_root / "app.log"

    @property
    def ui_state_path(self) -> Path:
        return self.data_root / "ui_state.json"

    def initialize(self) -> None:
        """Create the base directory tree."""
        for path in (
            self.data_root,
            self.personalities_root,
            self.projects_root,
            self.exports_root,
            self.logs_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def personality_dir(self, personality_id: str) -> Path:
        """Return the directory used for one personality bundle."""
        return self.personalities_root / personality_id

    def ensure_personality_bundle(
        self,
        personality_id: str,
        *,
        soul_text: str = "",
        agents_text: str = "",
        identity_text: str = "",
        metadata: dict[str, object] | None = None,
    ) -> Path:
        """Create or update a personality folder with its canonical files."""
        directory = self.personality_dir(personality_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SOUL.md").write_text(soul_text, encoding="utf-8")
        (directory / "AGENTS.md").write_text(agents_text, encoding="utf-8")
        (directory / "IDENTITY.md").write_text(identity_text, encoding="utf-8")
        (directory / "personality.json").write_text(
            json.dumps(metadata or {}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return directory

    def read_personality_bundle(self, personality_id: str) -> dict[str, str]:
        """Load the text files for an existing personality bundle."""
        directory = self.personality_dir(personality_id)
        return {
            "SOUL.md": (directory / "SOUL.md").read_text(encoding="utf-8"),
            "AGENTS.md": (directory / "AGENTS.md").read_text(encoding="utf-8"),
            "IDENTITY.md": (directory / "IDENTITY.md").read_text(encoding="utf-8"),
            "personality.json": (directory / "personality.json").read_text(
                encoding="utf-8"
            ),
        }

    def project_dir(self, project_id: str) -> Path:
        """Return the storage directory for one tracked project."""
        return self.projects_root / project_id

    def session_dir(self, project_id: str, session_id: str) -> Path:
        """Return the filesystem directory for one session."""
        return self.project_dir(project_id) / "sessions" / session_id

    def initialize_session_files(self, project_id: str, session_id: str) -> dict[str, Path]:
        """Create the canonical file set for a session transcript."""
        directory = self.session_dir(project_id, session_id)
        directory.mkdir(parents=True, exist_ok=True)
        files = {
            "transcript_md": directory / "transcript.md",
            "transcript_jsonl": directory / "transcript.jsonl",
            "summary_md": directory / "summary.md",
            "metadata_json": directory / "metadata.json",
        }
        files["transcript_md"].touch(exist_ok=True)
        files["transcript_jsonl"].touch(exist_ok=True)
        if not files["metadata_json"].exists():
            files["metadata_json"].write_text("{}", encoding="utf-8")
        return files

    def append_transcript_markdown(
        self,
        project_id: str,
        session_id: str,
        *,
        role: str,
        content: str,
        timestamp: str,
    ) -> Path:
        """Append one transcript entry to the markdown log."""
        files = self.initialize_session_files(project_id, session_id)
        entry = f"## {role} [{timestamp}]\n\n{content}\n\n"
        with files["transcript_md"].open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return files["transcript_md"]

    def append_transcript_event_jsonl(
        self,
        project_id: str,
        session_id: str,
        event: SessionEvent,
    ) -> Path:
        """Append one structured event to the JSONL transcript."""
        files = self.initialize_session_files(project_id, session_id)
        payload = {
            "id": event.id,
            "session_id": event.session_id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value,
            "content": event.content,
            "metadata_json": event.metadata_json,
        }
        with files["transcript_jsonl"].open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return files["transcript_jsonl"]

    def write_session_metadata(
        self,
        project_id: str,
        session_id: str,
        metadata: dict[str, object],
    ) -> Path:
        """Persist session-specific metadata to JSON."""
        files = self.initialize_session_files(project_id, session_id)
        files["metadata_json"].write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return files["metadata_json"]

    def read_session_metadata(self, project_id: str, session_id: str) -> dict[str, object]:
        """Load session metadata from disk."""
        files = self.initialize_session_files(project_id, session_id)
        return json.loads(files["metadata_json"].read_text(encoding="utf-8"))

    def write_summary(self, project_id: str, session_id: str, summary_text: str) -> Path:
        """Persist the session summary markdown file."""
        files = self.initialize_session_files(project_id, session_id)
        files["summary_md"].write_text(summary_text, encoding="utf-8")
        return files["summary_md"]

    def export_text(self, filename: str, content: str) -> Path:
        """Write an exported log to the exports directory."""
        self.exports_root.mkdir(parents=True, exist_ok=True)
        path = self.exports_root / filename
        path.write_text(content, encoding="utf-8")
        return path

    def write_ui_state(self, state: dict[str, object]) -> Path:
        """Persist lightweight window/session restore state."""
        self.initialize()
        self.ui_state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return self.ui_state_path

    def read_ui_state(self) -> dict[str, object]:
        """Load persisted window/session restore state."""
        if not self.ui_state_path.exists():
            return {}
        try:
            loaded = json.loads(self.ui_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
