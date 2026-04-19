"""Payment providers module.

This module provides an abstract interface for payment providers
with implementations for various payment systems (Platega, etc).
"""

from src.models.payment import PaymentStatus
from src.infrastructure.payments.base import (
    PaymentProvider,
    PaymentProviderName,
    CreatePaymentResult,
    PaymentStatusResult,
    WebhookData,
)
from src.infrastructure.payments.factory import PaymentProviderFactory
from src.infrastructure.payments.platega import PlategaProvider
from src.infrastructure.payments.exceptions import (
    PaymentProviderError,
    PaymentCreationError,
    PaymentStatusError,
    PaymentProviderUnavailable,
    PaymentValidationError,
    PaymentSignatureError,
    PaymentTimeoutError,
)
from src.infrastructure.payments.schemas import (
    PlategaPaymentMethod,
    PlategaStatus,
    PlategaPaymentDetails,
    PlategaCreateRequest,
    PlategaCreateResponse,
    PlategaStatusResponse,
)
from src.infrastructure.payments.retry import with_retry, RetryConfig, DEFAULT_RETRY_CONFIG

# Convenience function for async cache clearing
async def async_clear_cache() -> None:
    """Clear all cached payment provider instances with proper cleanup."""
    await PaymentProviderFactory.async_clear_cache()

__all__ = [
    # Base classes
    "PaymentProvider",
    "PaymentProviderName",
    "PaymentStatus",
    "CreatePaymentResult",
    "PaymentStatusResult",
    "WebhookData",
    # Factory
    "PaymentProviderFactory",
    # Providers
    "PlategaProvider",
    # Exceptions
    "PaymentProviderError",
    "PaymentCreationError",
    "PaymentStatusError",
    "PaymentProviderUnavailable",
    "PaymentValidationError",
    "PaymentSignatureError",
    "PaymentTimeoutError",
    # Schemas
    "PlategaPaymentMethod",
    "PlategaStatus",
    "PlategaPaymentDetails",
    "PlategaCreateRequest",
    "PlategaCreateResponse",
    "PlategaStatusResponse",
    # Retry
    "with_retry",
    "RetryConfig",
    "DEFAULT_RETRY_CONFIG",
    # Factory async methods
    "async_clear_cache",
]