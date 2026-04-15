"""Session models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .project import utc_now


class SessionStatus(StrEnum):
    """Known lifecycle states for a session record."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    FAILED = "failed"


@dataclass(slots=True)
class SessionRecord:
    """Represents persisted metadata for one project-scoped session."""

    id: str
    project_id: str
    personality_id: str
    transcript_path: str
    status: SessionStatus = SessionStatus.ACTIVE
    gateway_session_ref: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    last_activity_at: datetime = field(default_factory=utc_now)
    summary_path: str | None = None
    metadata_json: str | None = None
