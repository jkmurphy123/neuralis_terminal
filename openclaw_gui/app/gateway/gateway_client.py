"""Placeholder gateway client for Milestone 1."""

from __future__ import annotations

from openclaw_gui.app.gateway.gateway_adapter import GatewayAdapter
from openclaw_gui.app.gateway.gateway_models import GatewayStatus


class GatewayClient(GatewayAdapter):
    """Stub gateway client preserving the later integration seam."""

    def __init__(self, gateway_url: str, gateway_token: str = "") -> None:
        self.gateway_url = gateway_url
        self.gateway_token = gateway_token

    def ping(self) -> bool:
        return False

    def get_status(self) -> GatewayStatus:
        return GatewayStatus(
            connected=False,
            endpoint=self.gateway_url,
            detail="Gateway integration is not implemented in Milestone 1.",
        )
