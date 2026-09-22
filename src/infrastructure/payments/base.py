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
    "PaymentMethodKind",
    "PaymentMethodInfo",
    "MethodCheckResult",
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

    IMPORTANT: Providers must return mapped PaymentStatus in 'status' field.
    PaymentService should use 'status' directly, NOT call map_status() again.

    'external_status' contains the raw provider status string for logging.

    Attributes:
        success: Whether the status check was successful.
        payment_id: Payment ID that was checked.
        status: Mapped internal PaymentStatus (READY TO USE).
        external_status: Raw status string from provider (for logging).
        amount: Payment amount.
        currency: Currency code.
        error_message: Error message if check failed.
        raw_response: Full response data for debugging/logging.
    """

    success: bool = Field(default=True, description="Whether status check was successful")
    payment_id: str = Field(default="", description="Payment ID checked")
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING, description="Mapped internal payment status"
    )
    external_status: str = Field(default="", description="Raw provider status for logging")
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


class PaymentMethodKind(str, Enum):
    """Kind of payment method, shared by all providers.

    A button in the bot corresponds to a kind, not to a provider: if several
    providers support SBP, the user still sees one "СБП QR-код" button and
    the provider is chosen by priority.

    Values:
        SBP: СБП QR-код (Russian fast payment system)
        CARD_RU: Russian bank cards
        CARD_INTL: Foreign bank cards
        CRYPTO: Cryptocurrency
        ERIP: ЕРИП (Belarusian payment system)
    """

    SBP = "sbp"
    CARD_RU = "card_ru"
    CARD_INTL = "card_intl"
    CRYPTO = "crypto"
    ERIP = "erip"


# Как тип способа оплаты выглядит в интерфейсе: название, эмодзи и порядок
# кнопки. Одинаково для всех провайдеров, поэтому кнопка не зависит от того,
# через кого в итоге пойдет платеж.
PAYMENT_METHOD_KIND_VIEW: dict[PaymentMethodKind, tuple[str, str, int]] = {
    PaymentMethodKind.SBP: ("СБП QR-код", "💳", 10),
    PaymentMethodKind.CARD_RU: ("Банковская карта РФ", "💳", 20),
    PaymentMethodKind.CARD_INTL: ("Международная карта", "🌍", 30),
    PaymentMethodKind.ERIP: ("ЕРИП", "🏦", 40),
    PaymentMethodKind.CRYPTO: ("Криптовалюта", "🪙", 50),
}


class PaymentMethodInfo(BaseModel):
    """Description of a single payment method exposed by a provider.

    Providers return these objects from ``get_payment_methods()``, the bot
    builds keyboard buttons from them. Because every method carries its
    provider name, methods of different providers can be shown side by side.

    Attributes:
        provider: Provider name the method belongs to (e.g. 'platega').
        code: Provider-specific method identifier in string form (e.g. '2').
        kind: Kind of the method, shared by all providers.
    """

    provider: str = Field(..., description="Provider name")
    code: str = Field(..., description="Provider-specific method code")
    kind: PaymentMethodKind = Field(..., description="Kind of payment method")

    @property
    def key(self) -> str:
        """Unique method key in the 'provider:code' form."""
        return f"{self.provider}:{self.code}"

    @property
    def label(self) -> str:
        """Method name for buttons and messages."""
        return PAYMENT_METHOD_KIND_VIEW[self.kind][0]

    @property
    def emoji(self) -> str:
        """Emoji for the button label."""
        return PAYMENT_METHOD_KIND_VIEW[self.kind][1]

    @property
    def order(self) -> int:
        """Button sort order (ascending)."""
        return PAYMENT_METHOD_KIND_VIEW[self.kind][2]

    @property
    def button_text(self) -> str:
        """Text shown on the inline keyboard button."""
        return f"{self.emoji} {self.label}".strip()


class MethodCheckResult(BaseModel):
    """Result of checking a single payment method.

    A method is hidden only when the provider clearly says it does not work.
    Transport problems (network errors, 5xx) must not hide a method: in that
    case the provider returns ``available=True`` with a filled ``reason``, so
    a temporary failure of the provider API does not leave the bot without
    payment buttons.

    Attributes:
        available: Whether the method should be shown to users.
        reason: Why the method was rejected, or what went wrong during an
            inconclusive check. Empty when everything is fine.
    """

    available: bool = Field(..., description="Whether the method can be used")
    reason: str = Field(default="", description="Rejection reason or check error")


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

    def is_configured(self) -> bool:
        """Check that the provider has everything it needs to work.

        Providers override this to validate their credentials (API keys,
        merchant IDs, etc). A provider that is not configured is hidden from
        the payment method keyboards.

        Returns:
            True if the provider can be used, False otherwise.
        """
        return True

    @abstractmethod
    def get_payment_methods(self) -> list[PaymentMethodInfo]:
        """Get payment methods the provider exposes to users.

        Only the methods enabled for this installation should be returned:
        each of them becomes a button in the bot.

        Returns:
            List of PaymentMethodInfo (may be empty).
        """
        pass

    async def check_availability(self) -> bool:
        """Check that the provider is reachable right now.

        Called on bot start (see PaymentMethodsService). The default
        implementation only checks the configuration; providers should
        override it with a real API request when possible.

        Returns:
            True if the provider is available, False otherwise.
        """
        return self.is_configured()

    async def check_method_availability(self, method: PaymentMethodInfo) -> MethodCheckResult:
        """Check that a single payment method works for this merchant.

        Called on bot start for every method returned by
        ``get_payment_methods()``. Providers whose API does not report the
        enabled methods should override this with a probe request.

        A method must be reported unavailable only when the provider says so:
        on a network error or a provider-side failure the method stays
        available (with a filled reason), otherwise a temporary outage would
        leave the bot without any payment buttons.

        Args:
            method: Method to check.

        Returns:
            MethodCheckResult with the verdict and the reason.
        """
        return MethodCheckResult(available=True)

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
        """Map provider status string to internal PaymentStatus.

        USAGE: Only for webhook parsing and initial status mapping.
        NOT for PaymentStatusResult.status (already mapped by provider).

        Each provider has its own status naming. This method
        translates provider-specific statuses to our internal
        PaymentStatus enum.

        Args:
            external_status: Raw status string from provider (e.g., "CONFIRMED").

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
