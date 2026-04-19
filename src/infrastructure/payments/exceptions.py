"""Payment provider exceptions."""


class PaymentProviderError(Exception):
    """Base exception for payment provider errors."""

    pass


class PaymentCreationError(PaymentProviderError):
    """Error when creating a payment."""

    pass


class PaymentStatusError(PaymentProviderError):
    """Error when getting payment status."""

    pass


class PaymentProviderUnavailable(PaymentProviderError):
    """Error when payment provider is unavailable."""

    def __init__(
        self,
        message: str = "Payment provider unavailable",
        retry_count: int = 0,
        details: dict | None = None,
    ) -> None:
        """Initialize with message and retry information.

        Args:
            message: Error message.
            retry_count: Number of retries attempted.
            details: Additional error details.
        """
        super().__init__(message)
        self.retry_count = retry_count
        self.details = details or {}


class PaymentValidationError(PaymentProviderError):
    """Error when validating payment data."""

    pass


class PaymentSignatureError(PaymentProviderError):
    """Error when validating webhook signature."""

    pass


class PaymentTimeoutError(PaymentProviderError):
    """Error when payment API request times out."""

    def __init__(
        self,
        message: str = "Payment request timed out",
        timeout_seconds: float | None = None,
    ) -> None:
        """Initialize with message and timeout information.

        Args:
            message: Error message.
            timeout_seconds: Timeout duration in seconds.
        """
        super().__init__(message)
        self.timeout_seconds = timeout_seconds