from __future__ import annotations

from pathlib import Path

from openclaw_gui.app.models.settings import AppSettings, SettingsStore
from openclaw_gui.app.persistence.file_store import FileStore


def test_settings_load_save_round_trip(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    store = SettingsStore(settings_path)
    settings = AppSettings(
        gateway_url="http://localhost:9999",
        gateway_token="token-123",
        gateway_timeout_seconds=12.0,
        data_root=str(tmp_path / "app-data"),
        default_personality_id="persona-1",
        autosave_seconds=45,
    )

    store.save(settings)
    loaded = store.load()

    assert loaded == settings


def test_file_store_initializes_data_root_layout(tmp_path: Path) -> None:
    root = tmp_path / "data-root"
    store = FileStore(root)

    store.initialize()

    assert root.exists()
    assert store.personalities_root.exists()
    assert store.projects_root.exists()
    assert store.exports_root.exists()
