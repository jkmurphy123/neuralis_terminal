"""Abstract gateway adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from openclaw_gui.app.gateway.gateway_models import (
    GatewayCapabilities,
    GatewayMessageResult,
    GatewaySessionHandle,
    GatewayStatus,
)


class GatewayAdapter(ABC):
    """Interface that isolates the application from concrete gateway APIs."""

    @abstractmethod
    def ping(self) -> bool:
        """Return whether the gateway is reachable."""

    @abstractmethod
    def get_status(self) -> GatewayStatus:
        """Return a normalized status payload."""

    @abstractmethod
    def list_capabilities(self) -> GatewayCapabilities:
        """Return discovered capability flags for the gateway."""

    @abstractmethod
    def start_session(
        self,
        project_context: dict[str, object],
        personality_context: dict[str, object],
    ) -> GatewaySessionHandle:
        """Start or provision a session handle."""

    @abstractmethod
    def send_message(self, session_handle: GatewaySessionHandle, text: str) -> GatewayMessageResult:
        """Send one message through the gateway."""

    @abstractmethod
    def restore_session(self, saved_state: dict[str, object]) -> GatewaySessionHandle:
        """Restore a previously saved session if the gateway supports it."""

    @abstractmethod
    def end_session(self, session_handle: GatewaySessionHandle) -> None:
        """End a gateway-backed session if supported."""
