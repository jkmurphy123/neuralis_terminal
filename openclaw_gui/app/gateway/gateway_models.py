"""Structured models for gateway configuration, discovery, and status."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GatewayCapabilities:
    """Summarize what the gateway exposes and what this adapter implements."""

    health_endpoint: bool = False
    dashboard_bundle: bool = False
    websocket_rpc: bool = False
    status_rpc: bool = False
    chat_history_rpc: bool = False
    message_send_rpc: bool = False
    session_management_rpc: bool = False
    restore_session_rpc: bool = False
    adapter_can_ping: bool = True
    adapter_can_get_status: bool = True
    adapter_can_list_capabilities: bool = True
    adapter_can_start_session: bool = False
    adapter_can_send_message: bool = False
    adapter_can_restore_session: bool = False
    adapter_can_end_session: bool = False
    discovered_methods: tuple[str, ...] = ()


@dataclass(slots=True)
class GatewayDiscovery:
    """Observed HTTP and RPC shape of an OpenClaw gateway instance."""

    gateway_url: str
    health_endpoint: str = "/health"
    dashboard_path: str = "/"
    dashboard_present: bool = False
    dashboard_script_path: str | None = None
    websocket_rpc_detected: bool = False
    auth_modes: tuple[str, ...] = ()
    rpc_methods: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(slots=True)
class GatewayStatus:
    """Normalized gateway status payload used by the rest of the app."""

    connected: bool
    endpoint: str
    detail: str = ""
    auth_configured: bool = False
    health_payload: dict[str, object] = field(default_factory=dict)
    capabilities: GatewayCapabilities = field(default_factory=GatewayCapabilities)
    discovery: GatewayDiscovery | None = None


@dataclass(slots=True)
class GatewaySessionHandle:
    """Placeholder session handle retained for later milestones."""

    session_key: str
    gateway_session_ref: str | None = None


@dataclass(slots=True)
class GatewayMessageResult:
    """Placeholder message result retained for later milestones."""

    session_key: str
    raw_payload: dict[str, object] = field(default_factory=dict)
