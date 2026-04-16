"""Reusable application status message models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .project import utc_now


class StatusMessageLevel(StrEnum):
    """Supported alert levels for the shared status panel."""

    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    DEBUG = "debug"


@dataclass(slots=True)
class StatusMessage:
    """One application status entry shown in the bottom message panel."""

    level: StatusMessageLevel
    text: str
    source: str = "app"
    timestamp: datetime = field(default_factory=utc_now)
