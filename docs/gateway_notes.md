# Gateway Notes

Date: April 15, 2026

These findings were observed against the local OpenClaw gateway running at `http://127.0.0.1:18789`.

## Proven HTTP endpoints

- `GET /health`
  - Returns JSON like `{"ok": true, "status": "live"}`.
- `GET /`
  - Returns the OpenClaw Control dashboard HTML.
- `GET /assets/index-*.js`
  - Serves the dashboard client bundle used for protocol discovery.
- `GET /avatar/<agent>?meta=1`
  - Returns lightweight JSON metadata such as `{"avatarUrl": null}`.

## HTTP endpoints not found

- `POST /rpc` returned `404 Not Found`
- `POST /api/rpc` returned `404 Not Found`
- `GET /api/health` returned `404 Not Found`

## Discovered operator protocol from the served dashboard bundle

The dashboard bundle uses a WebSocket RPC client, not a plain HTTP JSON API, for richer gateway operations.

Observed RPC method names include:

- `connect`
- `health`
- `status`
- `last-heartbeat`
- `chat.history`
- `chat.send`
- `chat.abort`
- `sessions.list`
- `sessions.patch`
- `sessions.reset`
- `sessions.delete`
- `sessions.compact`
- `sessions.usage`
- `sessions.usage.logs`
- `sessions.usage.timeseries`
- `models.list`
- `agent.identity.get`
- `channels.status`

Observed handshake characteristics from the dashboard bundle:

- WebSocket transport is used for RPC requests.
- The connect handshake may begin with a `connect.challenge` event containing a nonce.
- The `connect` request includes protocol version fields, a client identity block, role/scopes, optional device data, and auth fields.
- Auth fields observed in the bundle:
  - token
  - password
  - device token
- Chat/session calls are keyed by `sessionKey`.

## What Milestone 2 implements

- A real `httpx`-based gateway client for:
  - health checks
  - connection/status normalization
  - capability discovery by inspecting the served dashboard bundle
- Settings-driven gateway URL/token/timeout configuration
- Normalized gateway error types

## What Milestone 2 does not implement

- WebSocket operator protocol transport
- Native remote session start
- Chat send/history over the gateway
- Gateway-backed session restore/end flows

Those features are explicitly marked unsupported in the adapter for now because they were only observed on the WebSocket RPC transport, and no plain HTTP RPC endpoint was discovered.
