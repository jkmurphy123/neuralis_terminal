"""Abstract gateway adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from openclaw_gui.app.gateway.gateway_models import GatewayStatus


class GatewayAdapter(ABC):
    """Interface that isolates the application from concrete gateway APIs."""

    @abstractmethod
    def ping(self) -> bool:
        """Return whether the gateway is reachable."""

    @abstractmethod
    def get_status(self) -> GatewayStatus:
        """Return a normalized status payload."""
