"""Exceptions for VPN Subscription API."""

from typing import Any


class VpnSubscriptionError(Exception):
    """Base exception for VPN Subscription API errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize exception with message and optional details."""
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class VpnSubscriptionConnectionError(VpnSubscriptionError):
    """Error when cannot connect to VPN Subscription API."""

    pass


class VpnSubscriptionAuthError(VpnSubscriptionError):
    """Error when authentication fails."""

    pass


class VpnSubscriptionApiError(VpnSubscriptionError):
    """Error when API returns error response."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        """Initialize with status code and response body."""
        super().__init__(message, {"status_code": status_code, "response_body": response_body})
        self.status_code = status_code
        self.response_body = response_body


class VpnSubscriptionValidationError(VpnSubscriptionError):
    """Error when request validation fails."""

    pass


class VpnSubscriptionNotFoundError(VpnSubscriptionError):
    """Error when subscription or VPN source not found."""

    pass