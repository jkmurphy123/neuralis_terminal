"""Gateway model stubs for future API integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GatewayStatus:
    """Minimal status payload used by the placeholder UI."""

    connected: bool
    endpoint: str
    detail: str = ""
