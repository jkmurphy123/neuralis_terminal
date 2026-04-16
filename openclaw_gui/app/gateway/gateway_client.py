"""Gateway adapter for OpenClaw HTTP discovery and WebSocket RPC messaging."""

from __future__ import annotations

import re
import uuid
from typing import Any, Protocol
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
)
from openclaw_gui.app.gateway.gateway_models import (
    GatewayCapabilities,
    GatewayDiscovery,
    GatewayMessageResult,
    GatewaySessionHandle,
    GatewayStatus,
)
from openclaw_gui.app.gateway.websocket_rpc import OpenClawRpcClient
from openclaw_gui.app.models.settings import AppSettings


class RpcClientProtocol(Protocol):
    """Protocol used to inject a fake RPC client in tests."""

    def close(self) -> None: ...

    def ensure_connected(self) -> dict[str, object]: ...

    def ensure_session(self, session_key: str) -> dict[str, object]: ...

    def send_chat(self, session_key: str, text: str) -> dict[str, object]: ...


class GatewayClient(GatewayAdapter):
    """Centralized adapter for the OpenClaw gateway HTTP and WebSocket surfaces."""

    def __init__(
        self,
        gateway_url: str,
        gateway_token: str = "",
        *,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
        rpc_client: RpcClientProtocol | None = None,
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
        self._rpc_client = rpc_client

    @classmethod
    def from_settings(
        cls,
        settings: AppSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        rpc_client: RpcClientProtocol | None = None,
    ) -> "GatewayClient":
        """Build a gateway client from persisted app settings."""
        return cls(
            settings.gateway_url,
            settings.gateway_token,
            timeout_seconds=settings.gateway_timeout_seconds,
            transport=transport,
            rpc_client=rpc_client,
        )

    def close(self) -> None:
        """Dispose of the underlying HTTP and RPC clients."""
        if self._rpc_client is not None:
            self._rpc_client.close()
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
        capabilities = self._with_adapter_capabilities(capabilities)
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
        capabilities = capabilities_from_discovery(
            health_endpoint_available=self.ping(),
            discovery=discovery,
        )
        return self._with_adapter_capabilities(capabilities)

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
        session_key = self._build_session_key(project_context, personality_context)
        self._get_rpc_client().ensure_session(session_key)
        return GatewaySessionHandle(
            session_key=session_key,
            gateway_session_ref=session_key,
        )

    def send_message(self, session_handle: GatewaySessionHandle, text: str) -> GatewayMessageResult:
        payload = self._get_rpc_client().send_chat(session_handle.session_key, text)
        run_id = payload.get("runId")
        effective_session_key = payload.get("sessionKey")
        return GatewayMessageResult(
            session_key=(
                str(effective_session_key)
                if isinstance(effective_session_key, str) and effective_session_key.strip()
                else session_handle.session_key
            ),
            run_id=str(run_id) if run_id is not None else None,
            raw_payload=payload,
        )

    def restore_session(self, saved_state: dict[str, object]) -> GatewaySessionHandle:
        session_key = self._session_key_from_saved_state(saved_state)
        self._get_rpc_client().ensure_session(session_key)
        return GatewaySessionHandle(
            session_key=session_key,
            gateway_session_ref=session_key,
        )

    def end_session(self, session_handle: GatewaySessionHandle) -> None:
        # The gateway session is keyed by `sessionKey`, so ending a local live session
        # means detaching this client connection rather than resetting remote context.
        self._get_rpc_client().close()

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
                "WebSocket RPC methods for chat/session features, and this adapter "
                "can use them for session start, restore, and message send flows."
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

    def _get_rpc_client(self) -> RpcClientProtocol:
        if self._rpc_client is None:
            self._rpc_client = OpenClawRpcClient(
                self.gateway_url,
                self.gateway_token,
                timeout_seconds=self.timeout_seconds,
            )
        return self._rpc_client

    def _with_adapter_capabilities(self, capabilities: GatewayCapabilities) -> GatewayCapabilities:
        capabilities.adapter_can_start_session = capabilities.websocket_rpc
        capabilities.adapter_can_send_message = capabilities.websocket_rpc
        capabilities.adapter_can_restore_session = capabilities.websocket_rpc
        capabilities.adapter_can_end_session = capabilities.websocket_rpc
        return capabilities

    def _build_session_key(
        self,
        project_context: dict[str, object],
        personality_context: dict[str, object],
    ) -> str:
        project = self._slug_component(project_context.get("name") or project_context.get("id"))
        personality = self._slug_component(
            personality_context.get("name") or personality_context.get("id")
        )
        return f"{project}-{personality}-{uuid.uuid4().hex[:8]}"

    def _session_key_from_saved_state(self, saved_state: dict[str, object]) -> str:
        direct = saved_state.get("session_key")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        metadata = saved_state.get("metadata")
        if isinstance(metadata, dict):
            gateway = metadata.get("gateway")
            if isinstance(gateway, dict):
                session_key = gateway.get("session_key")
                if isinstance(session_key, str) and session_key.strip():
                    return session_key.strip()
        session_id = saved_state.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            return session_id.strip()
        raise GatewayMalformedResponseError(
            "Saved session state does not include a usable session key.",
            operation="restore_session",
            endpoint=self.gateway_url,
        )

    @staticmethod
    def _slug_component(value: object) -> str:
        text = str(value or "session").strip().lower()
        text = re.sub(r"[^a-z0-9_-]+", "-", text).strip("-")
        return text or "session"

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
