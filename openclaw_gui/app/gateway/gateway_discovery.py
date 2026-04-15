"""Gateway discovery helpers."""

from __future__ import annotations

import re

from openclaw_gui.app.gateway.gateway_models import GatewayCapabilities, GatewayDiscovery

_DASHBOARD_SCRIPT_RE = re.compile(
    r"""<script[^>]+type=["']module["'][^>]+src=["'](?P<src>[^"']+)["']""",
    re.IGNORECASE,
)
_RPC_METHOD_RE = re.compile(r"request\(`([^`]+)`")


def extract_dashboard_script_path(html: str) -> str | None:
    """Return the first module script path from the dashboard HTML."""
    match = _DASHBOARD_SCRIPT_RE.search(html)
    return match.group("src") if match else None


def analyze_bundle(bundle_text: str, gateway_url: str, script_path: str | None) -> GatewayDiscovery:
    """Build a discovery report from the served dashboard bundle."""
    methods = tuple(sorted(set(_RPC_METHOD_RE.findall(bundle_text))))
    auth_modes: list[str] = []
    if "authToken" in bundle_text:
        auth_modes.append("token")
    if "authPassword" in bundle_text:
        auth_modes.append("password")
    if "authDeviceToken" in bundle_text:
        auth_modes.append("device_token")

    notes = [
        "Dashboard bundle uses WebSocket RPC requests rather than plain HTTP JSON endpoints."
    ]
    if "connect.challenge" in bundle_text:
        notes.append("WebSocket handshake includes an optional connect.challenge nonce flow.")
    if "sessionKey" in bundle_text:
        notes.append("Session-oriented RPC calls are keyed by sessionKey values.")

    return GatewayDiscovery(
        gateway_url=gateway_url,
        dashboard_present=True,
        dashboard_script_path=script_path,
        websocket_rpc_detected="connect" in methods,
        auth_modes=tuple(auth_modes),
        rpc_methods=methods,
        notes=tuple(notes),
    )


def empty_discovery(gateway_url: str, note: str) -> GatewayDiscovery:
    """Create a discovery report when the dashboard bundle is unavailable."""
    return GatewayDiscovery(
        gateway_url=gateway_url,
        notes=(note,),
    )


def capabilities_from_discovery(
    *,
    health_endpoint_available: bool,
    discovery: GatewayDiscovery,
) -> GatewayCapabilities:
    """Infer a stable capability summary from a discovery report."""
    methods = set(discovery.rpc_methods)
    return GatewayCapabilities(
        health_endpoint=health_endpoint_available,
        dashboard_bundle=discovery.dashboard_present,
        websocket_rpc=discovery.websocket_rpc_detected,
        status_rpc="status" in methods,
        chat_history_rpc="chat.history" in methods,
        message_send_rpc="chat.send" in methods,
        session_management_rpc=bool(
            {"sessions.list", "sessions.patch", "sessions.reset"} & methods
        ),
        restore_session_rpc="sessions.restore" in methods,
        discovered_methods=tuple(sorted(methods)),
    )
