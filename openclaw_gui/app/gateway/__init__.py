"""Gateway abstraction package."""

from .gateway_client import GatewayClient
from .gateway_errors import (
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayError,
    GatewayMalformedResponseError,
    GatewayServerError,
    GatewayTimeoutError,
    GatewayUnsupportedOperationError,
)
from .gateway_models import (
    GatewayCapabilities,
    GatewayDiscovery,
    GatewayMessageResult,
    GatewaySessionHandle,
    GatewayStatus,
)

__all__ = [
    "GatewayAuthenticationError",
    "GatewayCapabilities",
    "GatewayClient",
    "GatewayConnectionError",
    "GatewayDiscovery",
    "GatewayError",
    "GatewayMalformedResponseError",
    "GatewayMessageResult",
    "GatewayServerError",
    "GatewaySessionHandle",
    "GatewayStatus",
    "GatewayTimeoutError",
    "GatewayUnsupportedOperationError",
]
