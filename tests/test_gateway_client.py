from __future__ import annotations

import httpx
import pytest

from openclaw_gui.app.gateway.gateway_client import GatewayClient
from openclaw_gui.app.gateway.gateway_errors import (
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayMalformedResponseError,
    GatewayServerError,
    GatewayTimeoutError,
    GatewayUnsupportedOperationError,
)
from openclaw_gui.app.gateway.gateway_models import GatewaySessionHandle
from openclaw_gui.app.models.settings import AppSettings


def make_transport(handler):
    return httpx.MockTransport(handler)


def dashboard_html(script_path: str = "./assets/index-test.js") -> str:
    return (
        "<!doctype html><html><head>"
        f'<script type="module" crossorigin src="{script_path}"></script>'
        "</head><body><openclaw-app></openclaw-app></body></html>"
    )


def rpc_bundle(*methods: str) -> str:
    calls = "\n".join(f"client.request(`{method}`, {{}});" for method in methods)
    return (
        "connect.challenge\n"
        "authToken authPassword authDeviceToken sessionKey\n"
        "new WebSocket(this.opts.url)\n"
        f"{calls}\n"
    )


def test_gateway_ping_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"ok": True, "status": "live"})

    client = GatewayClient("http://gateway.test", transport=make_transport(handler))
    assert client.ping() is True


def test_gateway_ping_failure_on_connect_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = GatewayClient("http://gateway.test", transport=make_transport(handler))
    assert client.ping() is False


def test_gateway_get_status_happy_path_with_discovery() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True, "status": "live"})
        if request.url.path == "/":
            return httpx.Response(200, text=dashboard_html())
        if request.url.path == "/assets/index-test.js":
            return httpx.Response(
                200,
                text=rpc_bundle("connect", "status", "health", "chat.history", "chat.send", "sessions.reset"),
            )
        raise AssertionError(f"Unexpected request path: {request.url.path}")

    client = GatewayClient("http://gateway.test", gateway_token="secret", transport=make_transport(handler))
    status = client.get_status()

    assert status.connected is True
    assert status.auth_configured is True
    assert status.capabilities.health_endpoint is True
    assert status.capabilities.websocket_rpc is True
    assert status.capabilities.message_send_rpc is True
    assert status.capabilities.adapter_can_send_message is False
    assert "chat.send" in status.capabilities.discovered_methods


def test_gateway_status_auth_failure_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = GatewayClient("http://gateway.test", transport=make_transport(handler))
    with pytest.raises(GatewayAuthenticationError):
        client.get_status()


def test_gateway_status_malformed_health_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    client = GatewayClient("http://gateway.test", transport=make_transport(handler))
    with pytest.raises(GatewayMalformedResponseError):
        client.get_status()


def test_gateway_list_capabilities_falls_back_when_dashboard_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True, "status": "live"})
        if request.url.path == "/":
            return httpx.Response(404, text="Not Found")
        raise AssertionError(f"Unexpected request path: {request.url.path}")

    client = GatewayClient("http://gateway.test", transport=make_transport(handler))
    capabilities = client.list_capabilities()

    assert capabilities.health_endpoint is True
    assert capabilities.dashboard_bundle is False
    assert capabilities.websocket_rpc is False
    assert capabilities.discovered_methods == ()


def test_gateway_timeout_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = GatewayClient("http://gateway.test", transport=make_transport(handler))
    with pytest.raises(GatewayTimeoutError):
        client.get_status()


def test_gateway_server_error_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "busy"})

    client = GatewayClient("http://gateway.test", transport=make_transport(handler))
    with pytest.raises(GatewayServerError):
        client.get_status()


def test_gateway_connection_error_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = GatewayClient("http://gateway.test", transport=make_transport(handler))
    with pytest.raises(GatewayConnectionError):
        client.get_status()


def test_gateway_session_and_message_operations_are_explicitly_unsupported() -> None:
    client = GatewayClient("http://gateway.test", transport=make_transport(lambda request: httpx.Response(200, json={"ok": True})))

    with pytest.raises(GatewayUnsupportedOperationError):
        client.start_session({"project_id": "p1"}, {"personality_id": "x"})

    with pytest.raises(GatewayUnsupportedOperationError):
        client.send_message(GatewaySessionHandle(session_key="s1"), "hello")

    with pytest.raises(GatewayUnsupportedOperationError):
        client.restore_session({"session_key": "s1"})

    with pytest.raises(GatewayUnsupportedOperationError):
        client.end_session(GatewaySessionHandle(session_key="s1"))


def test_gateway_client_builds_from_settings() -> None:
    settings = AppSettings(
        gateway_url="http://localhost:9999",
        gateway_token="token-123",
        gateway_timeout_seconds=9.5,
    )

    client = GatewayClient.from_settings(settings)

    assert client.gateway_url == "http://localhost:9999"
    assert client.gateway_token == "token-123"
    assert client.timeout_seconds == 9.5
