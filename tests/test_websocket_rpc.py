from __future__ import annotations

import pytest

from openclaw_gui.app.gateway.gateway_errors import GatewayTimeoutError
from openclaw_gui.app.gateway.websocket_rpc import OpenClawRpcClient, _BufferedEvent


def test_send_chat_falls_back_to_chat_history_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenClawRpcClient("http://gateway.test", gateway_token="token-123")
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_request(method: str, params: dict[str, object]) -> dict[str, object]:
        calls.append((method, dict(params)))
        if method == "chat.send":
            return {"accepted": True}
        if method == "chat.history":
            return {
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": "hello"}]},
                    {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "reply from history"}],
                    },
                ]
            }
        raise AssertionError(f"Unexpected RPC method: {method}")

    def fake_wait_for_chat_completion(session_key: str, run_id: str) -> dict[str, object]:
        raise GatewayTimeoutError(
            "timed out",
            operation="chat.send",
            endpoint="http://gateway.test",
        )

    monkeypatch.setattr(client, "request", fake_request)
    monkeypatch.setattr(client, "wait_for_chat_completion", fake_wait_for_chat_completion)

    result = client.send_chat("session-1", "hello")

    assert [method for method, _ in calls] == ["chat.send", "chat.history"]
    assert result["state"] == "history-fallback"
    assert result["message"]["role"] == "assistant"
    assert result["message"]["content"][0]["text"] == "reply from history"


def test_send_chat_raises_timeout_when_history_has_no_assistant_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenClawRpcClient("http://gateway.test", gateway_token="token-123")

    def fake_request(method: str, params: dict[str, object]) -> dict[str, object]:
        if method == "chat.send":
            return {"accepted": True}
        if method == "chat.history":
            return {"messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]}
        raise AssertionError(f"Unexpected RPC method: {method}")

    def fake_wait_for_chat_completion(session_key: str, run_id: str) -> dict[str, object]:
        raise GatewayTimeoutError(
            "timed out",
            operation="chat.send",
            endpoint="http://gateway.test",
        )

    monkeypatch.setattr(client, "request", fake_request)
    monkeypatch.setattr(client, "wait_for_chat_completion", fake_wait_for_chat_completion)

    with pytest.raises(GatewayTimeoutError):
        client.send_chat("session-1", "hello")


def test_wait_for_chat_completion_accepts_gateway_derived_session_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenClawRpcClient("http://gateway.test", gateway_token="token-123")
    events = iter(
        [
            _BufferedEvent(
                event="agent",
                payload={
                    "runId": "run-1",
                    "stream": "lifecycle",
                    "data": {"phase": "start"},
                    "sessionKey": "agent:main:session-1",
                },
            ),
            _BufferedEvent(
                event="chat",
                payload={
                    "runId": "run-1",
                    "sessionKey": "agent:main:session-1",
                    "state": "delta",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "pong"}],
                    },
                },
            ),
            _BufferedEvent(
                event="chat",
                payload={
                    "runId": "run-1",
                    "sessionKey": "agent:main:session-1",
                    "state": "final",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "pong"}],
                    },
                },
            ),
        ]
    )

    monkeypatch.setattr(client, "_next_event", lambda predicate: next(events))

    result = client.wait_for_chat_completion("session-1", "run-1")

    assert result["state"] == "final"
    assert result["sessionKey"] == "agent:main:session-1"


def test_wait_for_chat_completion_uses_agent_lifecycle_end_history_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenClawRpcClient("http://gateway.test", gateway_token="token-123")
    events = iter(
        [
            _BufferedEvent(
                event="agent",
                payload={
                    "runId": "run-1",
                    "stream": "assistant",
                    "data": {"text": "pong"},
                    "sessionKey": "agent:main:session-1",
                },
            ),
            _BufferedEvent(
                event="agent",
                payload={
                    "runId": "run-1",
                    "stream": "lifecycle",
                    "data": {"phase": "end"},
                    "sessionKey": "agent:main:session-1",
                },
            ),
        ]
    )

    monkeypatch.setattr(client, "_next_event", lambda predicate: next(events))
    monkeypatch.setattr(
        client,
        "_latest_assistant_message",
        lambda session_key: {
            "role": "assistant",
            "content": [{"type": "text", "text": "pong"}],
        },
    )

    result = client.wait_for_chat_completion("session-1", "run-1")

    assert result["state"] == "agent-history-final"
    assert result["sessionKey"] == "agent:main:session-1"
