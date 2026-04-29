"""WebSocket RPC client for the OpenClaw gateway."""

from __future__ import annotations

import base64
import hashlib
import json
import locale
import os
import socket
import ssl
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from urllib.parse import urlparse

from openclaw_gui.app.gateway.gateway_errors import (
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayMalformedResponseError,
    GatewayServerError,
    GatewayTimeoutError,
)

_CONNECT_SCOPES = (
    "operator.admin",
    "operator.approvals",
    "operator.pairing",
)
_CLOSE_NORMAL = 1000


@dataclass(slots=True)
class _BufferedEvent:
    event: str
    payload: dict[str, object]


class _RawWebSocket:
    """Minimal RFC 6455 text-frame client for synchronous RPC use."""

    def __init__(self, url: str, *, timeout_seconds: float, origin: str) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.origin = origin
        self._socket: socket.socket | ssl.SSLSocket | None = None
        self._recv_buffer = bytearray()
        self._fragment_opcode: int | None = None
        self._fragment_data = bytearray()

    @property
    def connected(self) -> bool:
        return self._socket is not None

    def connect(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme not in {"ws", "wss"}:
            raise GatewayConnectionError(
                f"Unsupported WebSocket scheme: {parsed.scheme or 'missing'}",
                operation="ws connect",
                endpoint=self.url,
            )

        host = parsed.hostname
        if not host:
            raise GatewayConnectionError(
                "Gateway WebSocket URL is missing a hostname.",
                operation="ws connect",
                endpoint=self.url,
            )

        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        try:
            raw_socket = socket.create_connection((host, port), timeout=self.timeout_seconds)
            raw_socket.settimeout(self.timeout_seconds)
            if parsed.scheme == "wss":
                context = ssl.create_default_context()
                sock = context.wrap_socket(raw_socket, server_hostname=host)
            else:
                sock = raw_socket
        except socket.timeout as exc:
            raise GatewayTimeoutError(
                "Timed out while opening the gateway WebSocket.",
                operation="ws connect",
                endpoint=self.url,
            ) from exc
        except OSError as exc:
            raise GatewayConnectionError(
                "Could not open the gateway WebSocket.",
                operation="ws connect",
                endpoint=self.url,
            ) from exc

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host_header = host if parsed.port is None else f"{host}:{parsed.port}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Origin: {self.origin}\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")

        try:
            sock.sendall(request)
            response = self._read_http_headers(sock)
        except socket.timeout as exc:
            sock.close()
            raise GatewayTimeoutError(
                "Timed out during the gateway WebSocket handshake.",
                operation="ws connect",
                endpoint=self.url,
            ) from exc
        except OSError as exc:
            sock.close()
            raise GatewayConnectionError(
                "Gateway WebSocket handshake failed.",
                operation="ws connect",
                endpoint=self.url,
            ) from exc

        head, _, remainder = response.partition(b"\r\n\r\n")
        status_line, headers = self._parse_http_response(head)
        if " 101 " not in status_line:
            sock.close()
            raise GatewayConnectionError(
                f"Gateway WebSocket upgrade failed: {status_line}",
                operation="ws connect",
                endpoint=self.url,
            )

        expected_accept = base64.b64encode(
            hashlib.sha1(f"{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".encode("ascii")).digest()
        ).decode("ascii")
        actual_accept = headers.get("sec-websocket-accept")
        if actual_accept != expected_accept:
            sock.close()
            raise GatewayMalformedResponseError(
                "Gateway WebSocket handshake returned an invalid accept key.",
                operation="ws connect",
                endpoint=self.url,
            )

        self._socket = sock
        self._recv_buffer = bytearray(remainder)
        self._fragment_opcode = None
        self._fragment_data.clear()

    def close(self) -> None:
        if self._socket is None:
            return
        try:
            self._send_frame(0x8, _CLOSE_NORMAL.to_bytes(2, "big"))
        except Exception:
            pass
        try:
            self._socket.close()
        finally:
            self._socket = None
            self._recv_buffer.clear()
            self._fragment_opcode = None
            self._fragment_data.clear()

    def send_text(self, payload: str) -> None:
        self._send_frame(0x1, payload.encode("utf-8"))

    def recv_text(self) -> str:
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x1:
                return payload.decode("utf-8")
            if opcode == 0x2:
                raise GatewayMalformedResponseError(
                    "Gateway sent an unexpected binary WebSocket frame.",
                    operation="ws receive",
                    endpoint=self.url,
                )

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self._socket is None:
            raise GatewayConnectionError(
                "Gateway WebSocket is not connected.",
                operation="ws send",
                endpoint=self.url,
            )

        header = bytearray()
        header.append(0x80 | (opcode & 0x0F))
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header.extend(length.to_bytes(2, "big"))
        else:
            header.append(0x80 | 127)
            header.extend(length.to_bytes(8, "big"))

        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        try:
            self._socket.sendall(header + masked)
        except socket.timeout as exc:
            raise GatewayTimeoutError(
                "Timed out while sending a WebSocket frame to the gateway.",
                operation="ws send",
                endpoint=self.url,
            ) from exc
        except OSError as exc:
            self.close()
            raise GatewayConnectionError(
                "Gateway WebSocket send failed.",
                operation="ws send",
                endpoint=self.url,
            ) from exc

    def _recv_frame(self) -> tuple[int, bytes]:
        while True:
            header = self._read_exact(2)
            first, second = header[0], header[1]
            fin = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = int.from_bytes(self._read_exact(2), "big")
            elif length == 127:
                length = int.from_bytes(self._read_exact(8), "big")

            mask = self._read_exact(4) if masked else b""
            payload = bytearray(self._read_exact(length))
            if masked:
                for index in range(length):
                    payload[index] ^= mask[index % 4]

            if opcode == 0x8:
                self.close()
                raise GatewayConnectionError(
                    "Gateway WebSocket closed unexpectedly.",
                    operation="ws receive",
                    endpoint=self.url,
                )
            if opcode == 0x9:
                self._send_frame(0xA, bytes(payload))
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x0:
                if self._fragment_opcode is None:
                    raise GatewayMalformedResponseError(
                        "Gateway sent an unexpected continuation frame.",
                        operation="ws receive",
                        endpoint=self.url,
                    )
                self._fragment_data.extend(payload)
                if fin:
                    complete_opcode = self._fragment_opcode
                    complete_payload = bytes(self._fragment_data)
                    self._fragment_opcode = None
                    self._fragment_data.clear()
                    return complete_opcode, complete_payload
                continue
            if fin:
                return opcode, bytes(payload)
            self._fragment_opcode = opcode
            self._fragment_data = bytearray(payload)

    def _read_exact(self, size: int) -> bytes:
        while len(self._recv_buffer) < size:
            if self._socket is None:
                raise GatewayConnectionError(
                    "Gateway WebSocket is not connected.",
                    operation="ws receive",
                    endpoint=self.url,
                )
            try:
                chunk = self._socket.recv(4096)
            except socket.timeout as exc:
                raise GatewayTimeoutError(
                    "Timed out while waiting for a WebSocket frame from the gateway.",
                    operation="ws receive",
                    endpoint=self.url,
                ) from exc
            except OSError as exc:
                self.close()
                raise GatewayConnectionError(
                    "Gateway WebSocket receive failed.",
                    operation="ws receive",
                    endpoint=self.url,
                ) from exc
            if not chunk:
                self.close()
                raise GatewayConnectionError(
                    "Gateway WebSocket closed the connection.",
                    operation="ws receive",
                    endpoint=self.url,
                )
            self._recv_buffer.extend(chunk)

        data = bytes(self._recv_buffer[:size])
        del self._recv_buffer[:size]
        return data

    def _read_http_headers(self, sock: socket.socket | ssl.SSLSocket) -> bytes:
        data = bytearray()
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def _parse_http_response(response: bytes) -> tuple[str, dict[str, str]]:
        try:
            head = response.decode("iso-8859-1")
        except UnicodeDecodeError as exc:
            raise GatewayMalformedResponseError(
                "Gateway WebSocket handshake returned invalid HTTP headers.",
                operation="ws connect",
                endpoint="handshake",
            ) from exc
        lines = [line for line in head.split("\r\n") if line]
        if not lines:
            raise GatewayMalformedResponseError(
                "Gateway WebSocket handshake returned an empty HTTP response.",
                operation="ws connect",
                endpoint="handshake",
            )
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
        return lines[0], headers


class OpenClawRpcClient:
    """Persistent JSON-RPC client over the OpenClaw WebSocket operator channel."""

    def __init__(
        self,
        gateway_url: str,
        gateway_token: str = "",
        *,
        timeout_seconds: float = 5.0,
        client_name: str = "openclaw-control-ui",
        client_version: str = "control-ui",
        platform: str = "python",
        mode: str = "webchat",
        user_agent: str = "openclaw-control-ui",
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.gateway_token = gateway_token
        self.timeout_seconds = timeout_seconds
        self.client_name = client_name
        self.client_version = client_version
        self.platform = platform
        self.mode = mode
        self.user_agent = user_agent
        default_locale = locale.getlocale()[0] or locale.getdefaultlocale()[0]
        self.locale = default_locale or "en_US"
        self._lock = threading.RLock()
        self._ws = _RawWebSocket(
            self._ws_url_from_gateway_url(self.gateway_url),
            timeout_seconds=self.timeout_seconds,
            origin=self._origin_from_gateway_url(self.gateway_url),
        )
        self._connected = False
        self._hello_payload: dict[str, object] | None = None
        self._event_buffer: deque[_BufferedEvent] = deque()

    def close(self) -> None:
        with self._lock:
            self._connected = False
            self._hello_payload = None
            self._event_buffer.clear()
            self._ws.close()

    def ensure_connected(self) -> dict[str, object]:
        with self._lock:
            if self._connected and self._hello_payload is not None:
                return dict(self._hello_payload)
            self._ws.close()
            self._ws.connect()
            self._event_buffer.clear()
            self._hello_payload = self._perform_connect_handshake()
            self._connected = True
            return dict(self._hello_payload)

    def ensure_session(self, session_key: str) -> dict[str, object]:
        return self.request("chat.history", {"sessionKey": session_key, "limit": 1})

    def send_chat(self, session_key: str, text: str) -> dict[str, object]:
        run_id = str(uuid.uuid4())
        ack_payload = self.request(
            "chat.send",
            {
                "sessionKey": session_key,
                "message": text,
                "deliver": False,
                "idempotencyKey": run_id,
                "attachments": [],
            },
        )
        try:
            return self.wait_for_chat_completion(session_key, run_id, expected_user_text=text)
        except GatewayTimeoutError:
            return self._chat_history_fallback(session_key, run_id, text, ack_payload)

    def request(self, method: str, params: dict[str, object]) -> dict[str, object]:
        with self._lock:
            self.ensure_connected()
            request_id = str(uuid.uuid4())
            envelope = {
                "type": "req",
                "id": request_id,
                "method": method,
                "params": params,
            }
            self._send_json(envelope)
            while True:
                message = self._recv_json()
                msg_type = message.get("type")
                if msg_type == "event":
                    self._buffer_event(message)
                    continue
                if msg_type != "res":
                    raise GatewayMalformedResponseError(
                        f"Gateway returned an unexpected RPC envelope type for {method}.",
                        operation=method,
                        endpoint=self.gateway_url,
                    )
                if str(message.get("id")) != request_id:
                    raise GatewayMalformedResponseError(
                        f"Gateway returned a mismatched RPC response id for {method}.",
                        operation=method,
                        endpoint=self.gateway_url,
                    )
                if message.get("ok") is True:
                    payload = message.get("payload")
                    if payload is None:
                        return {}
                    if isinstance(payload, dict):
                        return dict(payload)
                    raise GatewayMalformedResponseError(
                        f"Gateway returned a non-object RPC payload for {method}.",
                        operation=method,
                        endpoint=self.gateway_url,
                    )
                self._raise_rpc_error(method, message.get("error"))

    def wait_for_chat_completion(
        self,
        session_key: str,
        run_id: str,
        *,
        expected_user_text: str | None = None,
    ) -> dict[str, object]:
        with self._lock:
            deadline = time.monotonic() + max(self.timeout_seconds, 30.0)
            effective_session_key = session_key
            assistant_text: str | None = None
            while True:
                if time.monotonic() >= deadline:
                    raise GatewayTimeoutError(
                        "Timed out waiting for a final gateway chat event.",
                        operation="chat.send",
                        endpoint=self.gateway_url,
                    )
                event = self._next_event(lambda item: item.event in {"chat", "agent"})
                payload = event.payload
                payload_run_id = payload.get("runId")
                if payload_run_id not in {None, run_id}:
                    continue
                payload_session_key = payload.get("sessionKey")
                if isinstance(payload_session_key, str) and payload_session_key.strip():
                    effective_session_key = payload_session_key.strip()

                if event.event == "agent":
                    assistant_text = self._assistant_text_from_agent_payload(payload) or assistant_text
                    if self._agent_run_finished(payload):
                        history_message = self._latest_assistant_message(
                            effective_session_key,
                            run_id=run_id,
                            after_user_text=expected_user_text,
                        )
                        if history_message is not None:
                            return {
                                "sessionKey": effective_session_key,
                                "runId": run_id,
                                "state": "agent-history-final",
                                "message": history_message,
                            }
                        if assistant_text:
                            return {
                                "sessionKey": effective_session_key,
                                "runId": run_id,
                                "state": "agent-stream-final",
                                "message": {
                                    "role": "assistant",
                                    "content": [{"type": "text", "text": assistant_text}],
                                },
                            }
                    continue

                state = str(payload.get("state", "")).lower()
                if state == "delta":
                    assistant_text = self._assistant_text_from_chat_payload(payload) or assistant_text
                    continue
                if state == "error":
                    message = str(payload.get("errorMessage") or "Gateway chat failed.")
                    raise GatewayServerError(
                        message,
                        operation="chat.send",
                        endpoint=self.gateway_url,
                    )
                if state in {"final", "aborted"}:
                    final_text = self._assistant_text_from_chat_payload(payload) or assistant_text
                    if final_text:
                        result = dict(payload)
                        result["sessionKey"] = effective_session_key
                        if not self._is_assistant_message(result.get("message")):
                            result["message"] = {
                                "role": "assistant",
                                "content": [{"type": "text", "text": final_text}],
                            }
                        return result
                    history_message = self._latest_assistant_message(
                        effective_session_key,
                        run_id=run_id,
                        after_user_text=expected_user_text,
                    )
                    if history_message is not None:
                        return {
                            "sessionKey": effective_session_key,
                            "runId": run_id,
                            "state": "final-history-fallback",
                            "message": history_message,
                        }
                    raise GatewayMalformedResponseError(
                        "Gateway finished the chat turn without an assistant reply.",
                        operation="chat.send",
                        endpoint=self.gateway_url,
                    )

    def _chat_history_fallback(
        self,
        session_key: str,
        run_id: str,
        user_text: str,
        ack_payload: dict[str, object],
    ) -> dict[str, object]:
        for candidate_session_key in self._fallback_session_keys(session_key):
            history = self.request("chat.history", {"sessionKey": candidate_session_key, "limit": 20})
            history_message = self._latest_assistant_message_from_history(
                history,
                run_id=run_id,
                after_user_text=user_text,
            )
            if history_message is not None:
                return {
                    "sessionKey": candidate_session_key,
                    "runId": run_id,
                    "state": "history-fallback",
                    "message": history_message,
                    "history": history,
                    "send_ack": ack_payload,
                }
        raise GatewayTimeoutError(
            "Timed out waiting for a final gateway chat event.",
            operation="chat.send",
            endpoint=self.gateway_url,
        )

    def _latest_assistant_message(
        self,
        session_key: str,
        *,
        run_id: str | None = None,
        after_user_text: str | None = None,
    ) -> dict[str, object] | None:
        history = self.request("chat.history", {"sessionKey": session_key, "limit": 20})
        return self._latest_assistant_message_from_history(
            history,
            run_id=run_id,
            after_user_text=after_user_text,
        )

    def _perform_connect_handshake(self) -> dict[str, object]:
        request_id = str(uuid.uuid4())
        self._send_json(
            {
                "type": "req",
                "id": request_id,
                "method": "connect",
                "params": self._connect_params(None),
            }
        )
        while True:
            message = self._recv_json()
            msg_type = message.get("type")
            if msg_type == "event":
                self._buffer_event(message)
                continue
            if msg_type != "res" or str(message.get("id")) != request_id:
                raise GatewayMalformedResponseError(
                    "Gateway returned an unexpected connect handshake response.",
                    operation="connect",
                    endpoint=self.gateway_url,
                )
            if message.get("ok") is True:
                payload = message.get("payload")
                if payload is None:
                    return {}
                if isinstance(payload, dict):
                    return dict(payload)
                raise GatewayMalformedResponseError(
                    "Gateway connect handshake returned a non-object payload.",
                    operation="connect",
                    endpoint=self.gateway_url,
                )
            self._raise_rpc_error("connect", message.get("error"))

    def _next_event(self, predicate) -> _BufferedEvent:
        buffered = self._pop_buffered_event(predicate)
        if buffered is not None:
            return buffered

        while True:
            message = self._recv_json()
            if message.get("type") != "event":
                raise GatewayMalformedResponseError(
                    "Gateway returned a non-event while waiting for chat completion.",
                    operation="chat.send",
                    endpoint=self.gateway_url,
                )
            self._buffer_event(message)
            buffered = self._pop_buffered_event(predicate)
            if buffered is not None:
                return buffered

    def _pop_buffered_event(self, predicate) -> _BufferedEvent | None:
        for index, event in enumerate(self._event_buffer):
            if predicate(event):
                selected = event
                del self._event_buffer[index]
                return selected
        return None

    def _buffer_event(self, message: dict[str, object]) -> None:
        event_name = message.get("event")
        payload = message.get("payload")
        if not isinstance(event_name, str) or not isinstance(payload, dict):
            return
        self._event_buffer.append(_BufferedEvent(event=event_name, payload=dict(payload)))

    def _send_json(self, payload: dict[str, object]) -> None:
        self._ws.send_text(json.dumps(payload))

    def _recv_json(self) -> dict[str, object]:
        message = self._ws.recv_text()
        try:
            decoded = json.loads(message)
        except json.JSONDecodeError as exc:
            raise GatewayMalformedResponseError(
                "Gateway WebSocket returned invalid JSON.",
                operation="ws receive",
                endpoint=self.gateway_url,
            ) from exc
        if not isinstance(decoded, dict):
            raise GatewayMalformedResponseError(
                "Gateway WebSocket returned a non-object JSON envelope.",
                operation="ws receive",
                endpoint=self.gateway_url,
            )
        return decoded

    def _connect_params(self, nonce: str | None) -> dict[str, object]:
        auth: dict[str, object] | None = None
        token = self.gateway_token.strip()
        if token:
            auth = {"token": token}
        params: dict[str, object] = {
            "minProtocol": 3,
            "maxProtocol": 3,
            "client": {
                "id": self.client_name,
                "version": self.client_version,
                "platform": self.platform,
                "mode": self.mode,
            },
            "role": "operator",
            "scopes": list(_CONNECT_SCOPES),
            "caps": ["tool-events"],
            "userAgent": self.user_agent,
            "locale": self.locale.replace("_", "-"),
        }
        if auth is not None:
            params["auth"] = auth
        return params

    def _raise_rpc_error(self, operation: str, error_payload: object) -> None:
        details: dict[str, object] = {}
        if isinstance(error_payload, dict):
            details = error_payload
        code = str(details.get("code") or "").upper()
        message = str(details.get("message") or "Gateway request failed.")
        if any(token in code for token in ("AUTH", "PAIR", "UNAUTHORIZED")):
            raise GatewayAuthenticationError(
                message,
                operation=operation,
                endpoint=self.gateway_url,
            )
        raise GatewayServerError(
            message,
            operation=operation,
            endpoint=self.gateway_url,
        )

    @staticmethod
    def _is_assistant_message(message: object) -> bool:
        if not isinstance(message, dict):
            return False
        role = message.get("role")
        return isinstance(role, str) and role.lower() == "assistant"

    @staticmethod
    def _assistant_text_from_chat_payload(payload: dict[str, object]) -> str | None:
        message = payload.get("message")
        if not isinstance(message, dict):
            return None
        return OpenClawRpcClient._extract_message_text(message)

    @staticmethod
    def _assistant_text_from_agent_payload(payload: dict[str, object]) -> str | None:
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        text = data.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        delta = data.get("delta")
        if isinstance(delta, str) and delta.strip():
            return delta.strip()
        return None

    @staticmethod
    def _agent_run_finished(payload: dict[str, object]) -> bool:
        data = payload.get("data")
        if not isinstance(data, dict):
            return False
        stream = payload.get("stream")
        phase = data.get("phase")
        return stream == "lifecycle" and phase == "end"

    @staticmethod
    def _extract_message_text(message: dict[str, object]) -> str | None:
        content = message.get("content")
        if not isinstance(content, list):
            return None
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        if parts:
            return "\n".join(parts)
        return None

    @staticmethod
    def _fallback_session_keys(session_key: str) -> tuple[str, ...]:
        derived = f"agent:main:{session_key}"
        if derived == session_key:
            return (session_key,)
        return (session_key, derived)

    @classmethod
    def _latest_assistant_message_from_history(
        cls,
        history: dict[str, object],
        *,
        run_id: str | None = None,
        after_user_text: str | None = None,
    ) -> dict[str, object] | None:
        messages = [message for message in history.get("messages", []) if isinstance(message, dict)]
        if run_id:
            for message in reversed(messages):
                if cls._is_assistant_message(message) and cls._message_run_id(message) == run_id:
                    return dict(message)

        normalized_user_text = after_user_text.strip() if after_user_text else ""
        if normalized_user_text:
            for index in range(len(messages) - 1, -1, -1):
                message = messages[index]
                if not cls._is_user_message(message):
                    continue
                if cls._extract_message_text(message) != normalized_user_text:
                    continue
                for candidate in messages[index + 1 :]:
                    if cls._is_user_message(candidate):
                        return None
                    if cls._is_assistant_message(candidate):
                        return dict(candidate)
                return None
        return None

    @staticmethod
    def _is_user_message(message: object) -> bool:
        if not isinstance(message, dict):
            return False
        role = message.get("role")
        return isinstance(role, str) and role.lower() == "user"

    @classmethod
    def _message_run_id(cls, message: dict[str, object]) -> str | None:
        for value in cls._candidate_run_id_values(message):
            if value:
                return value
        return None

    @classmethod
    def _candidate_run_id_values(cls, value: object) -> list[str]:
        if isinstance(value, dict):
            found: list[str] = []
            direct = value.get("runId")
            if isinstance(direct, str) and direct.strip():
                found.append(direct.strip())
            for key in ("metadata", "meta", "message", "data"):
                nested = value.get(key)
                if isinstance(nested, dict):
                    found.extend(cls._candidate_run_id_values(nested))
            return found
        return []

    @staticmethod
    def _ws_url_from_gateway_url(gateway_url: str) -> str:
        parsed = urlparse(gateway_url)
        if parsed.scheme in {"ws", "wss"}:
            return gateway_url
        if parsed.scheme == "https":
            return parsed._replace(scheme="wss").geturl()
        if parsed.scheme in {"http", ""}:
            return parsed._replace(scheme="ws").geturl()
        raise GatewayConnectionError(
            f"Unsupported gateway URL scheme: {parsed.scheme or 'missing'}",
            operation="ws url",
            endpoint=gateway_url,
        )

    @staticmethod
    def _origin_from_gateway_url(gateway_url: str) -> str:
        parsed = urlparse(gateway_url)
        scheme = "https" if parsed.scheme in {"https", "wss"} else "http"
        host = parsed.hostname or "localhost"
        port = parsed.port
        if port is None:
            return f"{scheme}://{host}"
        return f"{scheme}://{host}:{port}"
