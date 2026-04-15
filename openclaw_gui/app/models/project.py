"""Project model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Project:
    """Represents a tracked local code project."""

    id: str
    name: str
    root_path: str
    description: str = ""
    default_personality_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
