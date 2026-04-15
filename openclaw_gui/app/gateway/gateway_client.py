"""httpx-backed gateway adapter for OpenClaw discovery and health checks."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from openclaw_gui.app.gateway.gateway_adapter import GatewayAdapter
from openclaw_gui.app.gateway.gateway_discovery import (
    analyze_bundle,
    capabilities_from_discovery,
    empty_discovery,
    extract_dashboard_script_path,
)
from openclaw_gui.app.gateway.gateway_errors import (
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayError,
    GatewayMalformedResponseError,
    GatewayServerError,
    GatewayTimeoutError,
    GatewayUnsupportedOperationError,
)
from openclaw_gui.app.gateway.gateway_models import (
    GatewayCapabilities,
    GatewayDiscovery,
    GatewayMessageResult,
    GatewaySessionHandle,
    GatewayStatus,
)
from openclaw_gui.app.models.settings import AppSettings


class GatewayClient(GatewayAdapter):
    """Centralized adapter for the OpenClaw gateway HTTP surface."""

    def __init__(
        self,
        gateway_url: str,
        gateway_token: str = "",
        *,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.gateway_token = gateway_token
        self.timeout_seconds = timeout_seconds
        headers = {
            "Accept": "application/json, text/html;q=0.9, */*;q=0.1",
        }
        token = gateway_token.strip()
        if token:
            # The dashboard bundle suggests token-based auth, but the exact HTTP header
            # contract is not documented. Send both common forms for future compatibility.
            headers["Authorization"] = f"Bearer {token}"
            headers["X-OpenClaw-Token"] = token
        self._client = httpx.Client(
            base_url=self.gateway_url,
            timeout=self.timeout_seconds,
            headers=headers,
            follow_redirects=True,
            transport=transport,
        )

    @classmethod
    def from_settings(
        cls,
        settings: AppSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> "GatewayClient":
        """Build a gateway client from persisted app settings."""
        return cls(
            settings.gateway_url,
            settings.gateway_token,
            timeout_seconds=settings.gateway_timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        """Dispose of the underlying HTTP client."""
        self._client.close()

    def ping(self) -> bool:
        try:
            payload = self._fetch_health_payload()
        except GatewayError:
            return False
        return self._health_is_live(payload)

    def get_status(self) -> GatewayStatus:
        """Return normalized health and capability information."""
        payload = self._fetch_health_payload()
        discovery = self.discover()
        capabilities = capabilities_from_discovery(
            health_endpoint_available=True,
            discovery=discovery,
        )
        detail = self._build_status_detail(payload, capabilities)
        return GatewayStatus(
            connected=self._health_is_live(payload),
            endpoint=self.gateway_url,
            detail=detail,
            auth_configured=bool(self.gateway_token.strip()),
            health_payload=payload,
            capabilities=capabilities,
            discovery=discovery,
        )

    def list_capabilities(self) -> GatewayCapabilities:
        """Discover gateway capabilities by inspecting the served dashboard bundle."""
        discovery = self.discover()
        return capabilities_from_discovery(
            health_endpoint_available=self.ping(),
            discovery=discovery,
        )

    def discover(self) -> GatewayDiscovery:
        """Inspect the dashboard HTML and client bundle for RPC method hints."""
        try:
            response = self._request("GET", "/")
        except GatewayError as exc:
            return empty_discovery(
                self.gateway_url,
                f"Dashboard discovery unavailable: {exc}",
            )

        html = response.text
        script_path = extract_dashboard_script_path(html)
        if not script_path:
            return empty_discovery(
                self.gateway_url,
                "Dashboard HTML did not expose a module script for further discovery.",
            )

        script_url = urljoin(f"{self.gateway_url}/", script_path)
        try:
            bundle_response = self._request("GET", script_url)
        except GatewayError as exc:
            return empty_discovery(
                self.gateway_url,
                f"Dashboard bundle could not be fetched: {exc}",
            )
        return analyze_bundle(bundle_response.text, self.gateway_url, script_path)

    def start_session(
        self,
        project_context: dict[str, object],
        personality_context: dict[str, object],
    ) -> GatewaySessionHandle:
        self._unsupported(
            "start_session",
            "No plain HTTP start-session endpoint was discovered. "
            "Observed session/chat behavior is exposed through WebSocket RPC methods "
            "keyed by sessionKey values.",
        )

    def send_message(self, session_handle: GatewaySessionHandle, text: str) -> GatewayMessageResult:
        self._unsupported(
            "send_message",
            "The gateway exposes `chat.send` in the dashboard bundle, but only over the "
            "WebSocket operator protocol. This Milestone 2 adapter intentionally stays "
            "on the proven httpx-backed HTTP surface.",
        )

    def restore_session(self, saved_state: dict[str, object]) -> GatewaySessionHandle:
        self._unsupported(
            "restore_session",
            "No restore-session operation was discovered on the proven HTTP surface, and "
            "no `sessions.restore` RPC method was observed in the dashboard bundle.",
        )

    def end_session(self, session_handle: GatewaySessionHandle) -> None:
        self._unsupported(
            "end_session",
            "No plain HTTP end-session endpoint was discovered. Session control appears "
            "to happen via WebSocket RPC methods such as `sessions.reset` and `sessions.patch`.",
        )

    def _fetch_health_payload(self) -> dict[str, object]:
        response = self._request("GET", "/health")
        data = self._parse_json_object(response, operation="health")
        return data

    def _build_status_detail(
        self,
        health_payload: dict[str, object],
        capabilities: GatewayCapabilities,
    ) -> str:
        status = str(health_payload.get("status", "unknown"))
        if capabilities.websocket_rpc:
            return (
                f"HTTP health endpoint is {status}. The dashboard also advertises "
                "WebSocket RPC methods for chat/session features, which are not yet "
                "implemented by this adapter."
            )
        return f"HTTP health endpoint is {status}."

    @staticmethod
    def _health_is_live(payload: dict[str, object]) -> bool:
        if payload.get("ok") is True:
            return True
        return str(payload.get("status", "")).lower() in {"live", "ok", "healthy"}

    def _request(self, method: str, url_or_path: str) -> httpx.Response:
        operation = f"{method} {url_or_path}"
        try:
            if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
                response = self._client.request(method, url_or_path)
            else:
                response = self._client.request(method, url_or_path)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError(
                "Gateway request timed out.",
                operation=operation,
                endpoint=self.gateway_url,
            ) from exc
        except httpx.ConnectError as exc:
            raise GatewayConnectionError(
                "Could not connect to the gateway.",
                operation=operation,
                endpoint=self.gateway_url,
            ) from exc
        except httpx.HTTPError as exc:
            raise GatewayConnectionError(
                "Gateway request failed before a response was received.",
                operation=operation,
                endpoint=self.gateway_url,
            ) from exc

        if response.status_code in {401, 403}:
            raise GatewayAuthenticationError(
                "Gateway authentication failed.",
                operation=operation,
                endpoint=self.gateway_url,
                status_code=response.status_code,
            )
        if response.status_code >= 500:
            raise GatewayServerError(
                f"Gateway returned server error {response.status_code}.",
                operation=operation,
                endpoint=self.gateway_url,
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise GatewayConnectionError(
                f"Gateway returned HTTP {response.status_code}.",
                operation=operation,
                endpoint=self.gateway_url,
                status_code=response.status_code,
            )
        return response

    def _parse_json_object(
        self,
        response: httpx.Response,
        *,
        operation: str,
    ) -> dict[str, object]:
        try:
            data: Any = response.json()
        except ValueError as exc:
            raise GatewayMalformedResponseError(
                "Gateway returned invalid JSON.",
                operation=operation,
                endpoint=self.gateway_url,
                status_code=response.status_code,
            ) from exc
        if not isinstance(data, dict):
            raise GatewayMalformedResponseError(
                "Gateway returned JSON that was not an object.",
                operation=operation,
                endpoint=self.gateway_url,
                status_code=response.status_code,
            )
        return data

    def _unsupported(self, operation: str, detail: str) -> None:
        raise GatewayUnsupportedOperationError(
            detail,
            operation=operation,
            endpoint=self.gateway_url,
        )
