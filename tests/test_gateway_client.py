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


class FakeRpcClient:
    def __init__(self) -> None:
        self.ensure_connected_calls = 0
        self.ensure_session_calls: list[str] = []
        self.send_chat_calls: list[tuple[str, str]] = []
        self.closed = False
        self.send_chat_result: dict[str, object] = {
            "sessionKey": "ignored",
            "runId": "run-1",
            "state": "final",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "hello from gateway"}],
            },
        }

    def close(self) -> None:
        self.closed = True

    def ensure_connected(self) -> dict[str, object]:
        self.ensure_connected_calls += 1
        return {"ok": True}

    def ensure_session(self, session_key: str) -> dict[str, object]:
        self.ensure_session_calls.append(session_key)
        self.ensure_connected()
        return {"messages": []}

    def send_chat(self, session_key: str, text: str) -> dict[str, object]:
        self.send_chat_calls.append((session_key, text))
        self.ensure_connected()
        payload = dict(self.send_chat_result)
        payload.setdefault("sessionKey", session_key)
        return payload


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
    assert status.capabilities.adapter_can_send_message is True
    assert status.capabilities.adapter_can_start_session is True
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
    assert capabilities.adapter_can_send_message is False
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


def test_gateway_start_session_uses_rpc_client() -> None:
    rpc_client = FakeRpcClient()
    client = GatewayClient(
        "http://gateway.test",
        transport=make_transport(lambda request: httpx.Response(200, json={"ok": True})),
        rpc_client=rpc_client,
    )

    handle = client.start_session(
        {"id": "project-1", "name": "Project 1"},
        {"id": "persona-1", "name": "Helpful Persona"},
    )

    assert handle.gateway_session_ref == handle.session_key
    assert handle.session_key.startswith("project-1-helpful-persona-")
    assert rpc_client.ensure_session_calls == [handle.session_key]


def test_gateway_send_message_uses_rpc_client_and_returns_payload() -> None:
    rpc_client = FakeRpcClient()
    rpc_client.send_chat_result["sessionKey"] = "agent:main:session-1"
    client = GatewayClient(
        "http://gateway.test",
        transport=make_transport(lambda request: httpx.Response(200, json={"ok": True})),
        rpc_client=rpc_client,
    )

    result = client.send_message(GatewaySessionHandle(session_key="session-1"), "hello")

    assert rpc_client.send_chat_calls == [("session-1", "hello")]
    assert result.session_key == "agent:main:session-1"
    assert result.run_id == "run-1"
    assert result.raw_payload["state"] == "final"


def test_gateway_restore_session_prefers_saved_gateway_session_key() -> None:
    rpc_client = FakeRpcClient()
    client = GatewayClient(
        "http://gateway.test",
        transport=make_transport(lambda request: httpx.Response(200, json={"ok": True})),
        rpc_client=rpc_client,
    )

    handle = client.restore_session(
        {
            "session_id": "local-session-1",
            "metadata": {"gateway": {"session_key": "remote-session-7"}},
        }
    )

    assert handle.session_key == "remote-session-7"
    assert rpc_client.ensure_session_calls == ["remote-session-7"]


def test_gateway_restore_session_rejects_missing_session_key() -> None:
    client = GatewayClient(
        "http://gateway.test",
        transport=make_transport(lambda request: httpx.Response(200, json={"ok": True})),
        rpc_client=FakeRpcClient(),
    )

    with pytest.raises(GatewayMalformedResponseError):
        client.restore_session({})


def test_gateway_end_session_closes_rpc_client() -> None:
    rpc_client = FakeRpcClient()
    client = GatewayClient(
        "http://gateway.test",
        transport=make_transport(lambda request: httpx.Response(200, json={"ok": True})),
        rpc_client=rpc_client,
    )

    client.end_session(GatewaySessionHandle(session_key="session-1"))

    assert rpc_client.closed is True


def test_gateway_client_builds_from_settings() -> None:
    settings = AppSettings(
        gateway_url="http://localhost:9999",
        gateway_token="token-123",
        gateway_timeout_seconds=9.5,
    )

    rpc_client = FakeRpcClient()
    client = GatewayClient.from_settings(settings, rpc_client=rpc_client)

    assert client.gateway_url == "http://localhost:9999"
    assert client.gateway_token == "token-123"
    assert client.timeout_seconds == 9.5
