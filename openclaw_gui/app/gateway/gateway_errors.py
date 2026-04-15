"""App-friendly normalized gateway errors."""

from __future__ import annotations


class GatewayError(Exception):
    """Base class for normalized gateway failures."""

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        endpoint: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.endpoint = endpoint
        self.status_code = status_code


class GatewayConnectionError(GatewayError):
    """Raised when the gateway cannot be reached."""


class GatewayTimeoutError(GatewayError):
    """Raised when a gateway request times out."""


class GatewayAuthenticationError(GatewayError):
    """Raised when gateway authentication fails."""


class GatewayUnsupportedOperationError(GatewayError):
    """Raised when the gateway or adapter does not support an operation."""


class GatewayMalformedResponseError(GatewayError):
    """Raised when the gateway responds with malformed or unexpected data."""


class GatewayServerError(GatewayError):
    """Raised when the gateway returns a server-side error."""
