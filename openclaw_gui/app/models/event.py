"""Session event models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .project import utc_now


class EventType(StrEnum):
    """Supported session event kinds."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    STATUS = "status"
    ERROR = "error"
    PERSONALITY_CHANGE = "personality_change"


@dataclass(slots=True)
class SessionEvent:
    """Represents one persisted event in a transcript."""

    id: str
    session_id: str
    event_type: EventType
    content: str
    timestamp: datetime = field(default_factory=utc_now)
    metadata_json: str | None = None
