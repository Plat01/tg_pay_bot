"""Abstract base class for payment providers.

This module defines the interface that all payment providers must implement,
ensuring consistent behavior across different payment systems.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.models.payment import PaymentStatus


# Re-export PaymentStatus for convenience
__all__ = [
    "PaymentProviderName",
    "CreatePaymentResult",
    "PaymentStatusResult",
    "WebhookData",
    "PaymentProvider",
    "PaymentStatus",
]


class PaymentProviderName(str, Enum):
    """Supported payment providers."""

    PLATEGA = "platega"
    # Future providers:
    # YOOKASSA = "yookassa"
    # STRIPE = "stripe"


class CreatePaymentResult(BaseModel):
    """Result of creating a payment in external system.

    This model standardizes the response from different payment providers,
    abstracting away provider-specific details.

    Attributes:
        success: Whether the payment was created successfully.
        payment_id: Internal payment ID (same as external_id for most cases).
        external_id: Unique identifier in the provider's system.
        payment_url: URL for the user to complete payment (if applicable).
        amount: Payment amount.
        currency: Currency code.
        status: Initial status from the provider.
        expires_at: When the payment expires (optional).
        error_message: Error message if creation failed.
        metadata: Provider-specific additional data.
        raw_response: Full response data for debugging/logging.
    """

    success: bool = Field(default=True, description="Whether creation was successful")
    payment_id: str = Field(default="", description="Internal payment ID")
    external_id: str = Field(default="", description="ID in provider's system")
    payment_url: str | None = Field(None, description="URL for payment completion")
    amount: Decimal = Field(default=Decimal("0"), description="Payment amount")
    currency: str = Field(default="RUB", description="Currency code")
    status: str = Field(default="PENDING", description="Initial payment status")
    expires_at: str | None = Field(None, description="Expiration datetime string")
    error_message: str | None = Field(None, description="Error message if failed")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific metadata",
    )
    raw_response: dict[str, Any] = Field(
        default_factory=dict,
        description="Full provider response",
    )


class PaymentStatusResult(BaseModel):
    """Result of checking payment status.

    This model standardizes status check responses from different providers.

    Attributes:
        success: Whether the status check was successful.
        payment_id: Payment ID that was checked.
        status: Current status from the provider (mapped to PaymentStatus).
        amount: Payment amount.
        currency: Currency code.
        error_message: Error message if check failed.
        raw_response: Full response data for debugging/logging.
    """

    success: bool = Field(default=True, description="Whether status check was successful")
    payment_id: str = Field(default="", description="Payment ID checked")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, description="Current payment status")
    amount: Decimal = Field(default=Decimal("0"), description="Payment amount")
    currency: str = Field(default="RUB", description="Currency code")
    error_message: str | None = Field(None, description="Error message if failed")
    raw_response: dict[str, Any] = Field(
        default_factory=dict,
        description="Full provider response",
    )


class WebhookData(BaseModel):
    """Parsed webhook data from payment provider.

    This model standardizes webhook payloads from different providers.

    Attributes:
        payment_id: ID in provider's system.
        order_id: Our internal order/payment ID.
        status: Payment status from webhook.
        amount: Payment amount.
        currency: Currency code.
        signature: Signature for verification.
        raw_data: Full webhook payload.
    """

    payment_id: str = Field(..., description="ID in provider's system")
    order_id: str = Field(default="", description="Internal order ID")
    status: PaymentStatus = Field(..., description="Payment status")
    amount: Decimal = Field(..., description="Payment amount")
    currency: str = Field(default="RUB", description="Currency code")
    signature: str = Field(default="", description="Webhook signature")
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Full webhook payload",
    )


class PaymentProvider(ABC):
    """Abstract base class for payment providers.

    All payment providers must implement this interface to ensure
    consistent behavior across the application. This allows for
    easy switching between providers without changing business logic.

    Example:
        >>> class MyProvider(PaymentProvider):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_provider"
        ...
        ...     async def create_payment(self, amount, currency, **kwargs):
        ...         # Implementation specific to MyProvider
        ...         pass
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get provider name for identification.

        This name is used in logs, database records, and factory
        registration.

        Returns:
            Provider identifier string (e.g., 'platega', 'yookassa').
        """
        pass

    @abstractmethod
    async def create_payment(
        self,
        amount: Decimal,
        currency: str,
        description: str,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CreatePaymentResult:
        """Create a payment in the external system.

        This method should send a request to the provider's API
        to create a new payment and return standardized result.

        Args:
            amount: Payment amount.
            currency: Currency code (e.g., 'RUB', 'USD').
            description: Payment description for user.
            metadata: Custom data to track/associate with payment.
            **kwargs: Provider-specific options (e.g., payment_method).

        Returns:
            Standardized creation result with external_id and payment_url.

        Raises:
            PaymentCreationError: If creation fails.
            PaymentProviderUnavailable: If provider is unreachable.
        """
        pass

    @abstractmethod
    async def get_payment_status(
        self,
        external_id: str,
    ) -> PaymentStatusResult:
        """Get current payment status from provider.

        This method queries the provider's API for the current
        status of a previously created payment.

        Args:
            external_id: ID of payment in provider's system.

        Returns:
            Standardized status result with current status.

        Raises:
            PaymentStatusError: If status check fails.
            PaymentProviderUnavailable: If provider is unreachable.
        """
        pass

    @abstractmethod
    def map_status(self, external_status: str) -> PaymentStatus:
        """Map provider status to internal PaymentStatus.

        Each provider has its own status naming. This method
        translates provider-specific statuses to our internal
        PaymentStatus enum.

        Args:
            external_status: Status string from provider.

        Returns:
            Corresponding internal PaymentStatus value.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close provider resources.

        This method should clean up any resources used by the
        provider, such as HTTP sessions or connections.

        Called when shutting down the application or switching
        providers.
        """
        pass