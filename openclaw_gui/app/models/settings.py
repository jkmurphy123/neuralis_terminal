"""Application settings model and JSON store."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


def default_data_root() -> str:
    """Return the default Linux app data directory."""
    return str(Path.home() / ".local" / "share" / "neuralis-terminal")


@dataclass(slots=True)
class AppSettings:
    """Persistent application settings."""

    gateway_url: str = "http://127.0.0.1:18789"
    gateway_token: str = ""
    gateway_timeout_seconds: float = 5.0
    data_root: str = default_data_root()
    default_personality_id: str | None = None
    autosave_seconds: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AppSettings":
        """Construct settings from a plain mapping."""
        defaults = cls()
        return cls(
            gateway_url=str(data.get("gateway_url", defaults.gateway_url)),
            gateway_token=str(data.get("gateway_token", defaults.gateway_token)),
            gateway_timeout_seconds=float(
                data.get("gateway_timeout_seconds", defaults.gateway_timeout_seconds)
            ),
            data_root=str(data.get("data_root", default_data_root())),
            default_personality_id=(
                str(data["default_personality_id"])
                if data.get("default_personality_id") is not None
                else None
            ),
            autosave_seconds=int(data.get("autosave_seconds", defaults.autosave_seconds)),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize settings to a plain mapping."""
        return asdict(self)


class SettingsStore:
    """Load and save application settings as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppSettings:
        """Load settings from disk or return defaults when absent."""
        if not self.path.exists():
            return AppSettings()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return AppSettings.from_dict(data)

    def save(self, settings: AppSettings) -> None:
        """Persist settings to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(settings.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
