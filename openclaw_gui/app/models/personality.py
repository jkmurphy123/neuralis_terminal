"""Personality model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .project import utc_now


@dataclass(slots=True)
class Personality:
    """Represents a reusable personality bundle on disk."""

    id: str
    name: str
    storage_path: str
    description: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
