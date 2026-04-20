"""Platega payment provider implementation.

Documentation: https://docs.platega.io/

Platega API endpoints:
- POST /transaction/process - Create transaction
- GET /transaction/{id} - Get transaction status
"""

import hashlib
import hmac
import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import aiohttp
from pydantic import Field

from src.config import settings
from src.models.payment import PaymentStatus
from src.infrastructure.payments.base import (
    CreatePaymentResult,
    PaymentProvider,
    PaymentProviderName,
    PaymentStatusResult,
    WebhookData,
)
from src.infrastructure.payments.exceptions import (
    PaymentCreationError,
    PaymentProviderUnavailable,
    PaymentSignatureError,
    PaymentStatusError,
    PaymentValidationError,
)
from src.infrastructure.payments.schemas import (
    PlategaCreateRequest,
    PlategaCreateResponse,
    PlategaPaymentDetails,
    PlategaPaymentMethod,
    PlategaStatus,
    PlategaStatusResponse,
)
from src.infrastructure.payments.retry import DEFAULT_RETRY_CONFIG

logger = logging.getLogger(__name__)


class PlategaCreatePaymentResult(CreatePaymentResult):
    """Extended result for Platega payments.

    Attributes:
        transaction_id: Platega transaction UUID.
        qr_code: QR code data for SBP payments.
        expires_in: Time until expiration (HH:MM:SS format).
    """

    transaction_id: str | None = Field(None, description="Platega transaction UUID")
    qr_code: str | None = Field(None, description="QR code data for SBP payments")
    expires_in: str | None = Field(None, description="Time until expiration")


class PlategaProvider(PaymentProvider):
    """Platega.io payment provider implementation.

    This provider supports multiple payment methods:
    - SBP QR (Russian fast payment system)
    - ERIP (Belarusian payment system)
    - Card acquiring (Russian cards)
    - International card payments
    - Cryptocurrency payments

    Example:
        >>> provider = PlategaProvider()
        >>> result = await provider.create_payment(
        ...     amount=Decimal("1000"),
        ...     currency="RUB",
        ...     description="Account top-up",
        ...     payment_method=PlategaPaymentMethod.SBP_QR,
        ... )
        >>> print(result.payment_url)  # URL for user to pay
    """

    def __init__(
        self,
        api_key: str | None = None,
        merchant_id: str | None = None,
        webhook_secret: str | None = None,
        api_url: str | None = None,
        default_payment_method: PlategaPaymentMethod = PlategaPaymentMethod.SBP_QR,
    ) -> None:
        """Initialize Platega provider.

        Args:
            api_key: Platega API key / secret (X-Secret header).
            merchant_id: Platega merchant ID (X-MerchantId header).
            webhook_secret: Secret for webhook signature verification.
            api_url: Platega API URL (defaults to settings).
            default_payment_method: Default payment method for transactions.
        """
        self._api_key = api_key or settings.platega_secret
        self._merchant_id = merchant_id or settings.platega_merchant_id
        self._webhook_secret = webhook_secret or settings.platega_webhook_secret
        self._api_url = (api_url or settings.platega_api_url).rstrip("/")
        self._default_payment_method = default_payment_method
        self._session: aiohttp.ClientSession | None = None

        # Log configuration for debugging
        logger.info(
            "Platega provider initialized",
            extra={
                "merchant_id": self._merchant_id[:8] + "..." if self._merchant_id else "EMPTY",
                "api_key": self._api_key[:8] + "..." if self._api_key else "EMPTY",
                "api_url": self._api_url,
            },
        )

    @property
    def name(self) -> PaymentProviderName:
        """Get provider name."""
        return PaymentProviderName.PLATEGA

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with Platega authentication headers."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_RETRY_CONFIG.timeout or 10.0)
            self._session = aiohttp.ClientSession(
                headers={
                    "X-MerchantId": self._merchant_id,
                    "X-Secret": self._api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=timeout,
            )
        return self._session

    async def create_payment(
        self,
        amount: Decimal,
        currency: str = "RUB",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        payment_method: PlategaPaymentMethod | None = None,
        return_url: str | None = None,
        failed_url: str | None = None,
        **kwargs: Any,
    ) -> PlategaCreatePaymentResult:
        """Create a new payment transaction in Platega.

        Args:
            amount: Payment amount.
            currency: Currency code (default: 'RUB').
            description: Payment description.
            metadata: Additional metadata (stored in payload).
            payment_method: Payment method (defaults to SBP_QR).
            return_url: Redirect URL after success.
            failed_url: Redirect URL after failure.
            **kwargs: Additional provider-specific options.

        Returns:
            PlategaCreatePaymentResult with payment details.

        Raises:
            PaymentCreationError: If payment creation fails.
            PaymentProviderUnavailable: If provider is unreachable.
        """
        url = f"{self._api_url}/transaction/process"

        # Use provided payment method or default
        method = payment_method or self._default_payment_method

        # Build payload string from metadata
        # Convert Decimal to str for JSON serialization
        if metadata:
            serialized_metadata = {
                k: str(v) if isinstance(v, Decimal) else v for k, v in metadata.items()
            }
            payload_str = json.dumps(serialized_metadata)
        else:
            payload_str = None

        # Create request body using Pydantic schema
        request_data = PlategaCreateRequest(
            paymentMethod=method,
            paymentDetails=PlategaPaymentDetails(amount=amount, currency=currency),
            description=description or f"Payment {amount} {currency}",
            return_url=return_url,
            failedUrl=failed_url,
            payload=payload_str,
        )

        logger.info(
            "Creating Platega payment",
            extra={
                "amount": str(amount),
                "currency": currency,
                "method": method.name,
            },
        )

        try:
            session = await self._get_session()
            async with session.post(url, json=request_data.model_dump(by_alias=True)) as response:
                response_data = await response.json()

                logger.debug(
                    "Platega API response",
                    extra={
                        "status": response.status,
                        "response_data": response_data,
                    },
                )

                if response.status not in (200, 201):
                    error_msg = response_data.get("message", "Unknown error")
                    logger.error(f"Platega create payment failed: {response.status} - {error_msg}")

                    transaction_id_raw = response_data.get("transactionId")
                    if transaction_id_raw:
                        transaction_id = str(transaction_id_raw)
                        logger.warning(
                            f"Transaction created but with error: {transaction_id}",
                            extra={"error": error_msg, "transaction_id": transaction_id},
                        )
                        return PlategaCreatePaymentResult(
                            success=False,
                            payment_id=transaction_id,
                            external_id=transaction_id,
                            payment_url=response_data.get("redirect", ""),
                            amount=amount,
                            currency=currency,
                            error_message=error_msg,
                            transaction_id=transaction_id,
                            metadata={"transaction_id": transaction_id},
                            raw_response=response_data,
                        )

                    return PlategaCreatePaymentResult(
                        success=False,
                        payment_id="",
                        external_id="",
                        payment_url="",
                        amount=amount,
                        currency=currency,
                        error_message=error_msg,
                        raw_response=response_data,
                    )

                # Parse response using Pydantic schema
                platega_response = PlategaCreateResponse(**response_data)

                # Extract transaction ID and payment URL
                transaction_id = str(platega_response.transactionId)
                payment_url = platega_response.redirect or ""

                # Calculate expiration time
                expires_at = platega_response.get_expires_at()
                expires_at_str = expires_at.isoformat() if expires_at else None

                logger.info(
                    "Platega payment created successfully",
                    extra={
                        "transaction_id": transaction_id,
                        "payment_url": payment_url,
                        "expires_at": expires_at_str,
                    },
                )

                return PlategaCreatePaymentResult(
                    success=True,
                    payment_id=transaction_id,
                    external_id=transaction_id,
                    payment_url=payment_url,
                    amount=amount,
                    currency=currency,
                    expires_at=expires_at_str,
                    transaction_id=transaction_id,
                    qr_code=platega_response.qr if hasattr(platega_response, "qr") else None,
                    expires_in=platega_response.expiresIn,
                    metadata={"transaction_id": transaction_id},
                    raw_response=response_data,
                )

        except aiohttp.ClientError as e:
            logger.error(f"Platega API connection error: {e}")
            raise PaymentProviderUnavailable(f"Platega API unavailable: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating Platega payment: {e}")
            raise PaymentCreationError(f"Failed to create payment: {e}") from e

    async def get_payment_status(self, payment_id: str) -> PaymentStatusResult:
        """Get payment status from Platega.

        Args:
            payment_id: Platega transaction ID (UUID format).

        Returns:
            PaymentStatusResult with current status.

        Raises:
            PaymentStatusError: If status check fails.
            PaymentProviderUnavailable: If provider is unreachable.
        """
        url = f"{self._api_url}/transaction/{payment_id}"

        logger.info(
            "Checking Platega payment status",
            extra={"payment_id": payment_id},
        )

        try:
            session = await self._get_session()
            async with session.get(url) as response:
                response_data = await response.json()

                if response.status != 200:
                    error_msg = response_data.get("message", "Unknown error")
                    logger.error(
                        f"Platega get payment status failed: {response.status} - {error_msg}"
                    )
                    return PaymentStatusResult(
                        success=False,
                        payment_id=payment_id,
                        status=PaymentStatus.PENDING,
                        amount=Decimal("0"),
                        currency="",
                        error_message=error_msg,
                        raw_response=response_data,
                    )

                # Parse response using Pydantic schema
                status_response = PlategaStatusResponse(**response_data)

                # Map Platega status to internal status
                status = self._map_platega_status(status_response.status)

                # Get amount and currency
                amount = status_response.paymentDetails.amount
                currency = status_response.paymentDetails.currency

                logger.info(
                    "Platega payment status retrieved",
                    extra={
                        "payment_id": payment_id,
                        "status": status.value,
                        "amount": str(amount),
                    },
                )

                return PaymentStatusResult(
                    success=True,
                    payment_id=payment_id,
                    status=status,
                    external_status=status_response.status.value,
                    amount=amount,
                    currency=currency,
                    raw_response=response_data,
                )

        except aiohttp.ClientError as e:
            logger.error(f"Platega API connection error: {e}")
            raise PaymentProviderUnavailable(f"Platega API unavailable: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting Platega payment status: {e}")
            raise PaymentStatusError(f"Failed to get payment status: {e}") from e

    def parse_webhook(
        self,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookData:
        """Parse and validate Platega webhook data.

        Note: Platega webhooks may vary in format. This implementation
        handles common webhook structures.

        Args:
            raw_body: Raw request body.
            headers: Request headers.

        Returns:
            Parsed WebhookData.

        Raises:
            PaymentSignatureError: If signature validation fails.
            PaymentValidationError: If data validation fails.
        """
        # Verify signature if configured
        signature = headers.get("X-Signature", "") or headers.get("x-signature", "")

        if not self._verify_signature(raw_body, signature):
            logger.warning("Platega webhook signature verification failed")
            raise PaymentSignatureError("Invalid webhook signature")

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse webhook JSON: {e}")
            raise PaymentValidationError(f"Invalid JSON: {e}") from e

        # Parse webhook data
        try:
            # Platega webhook format may vary
            payment_id = data.get("transactionId") or data.get("id", "")
            order_id = data.get("payload") or data.get("order_id", "")
            status_str = data.get("status", "PENDING")

            # Parse amount from paymentDetails or direct fields
            if "paymentDetails" in data:
                pd = data["paymentDetails"]
                if isinstance(pd, dict):
                    amount = Decimal(str(pd.get("amount", "0")))
                    currency = pd.get("currency", "RUB")
                else:
                    # Parse "100 RUB" format
                    parts = str(pd).split()
                    amount = Decimal(parts[0]) if parts else Decimal("0")
                    currency = parts[1] if len(parts) > 1 else "RUB"
            else:
                amount = Decimal(str(data.get("amount", "0")))
                currency = data.get("currency", "RUB")

            if not payment_id:
                raise PaymentValidationError("Missing required field: transactionId")

            status = self._map_platega_status_str(status_str)

            logger.info(
                "Platega webhook parsed",
                extra={
                    "payment_id": payment_id,
                    "status": status.value,
                    "amount": str(amount),
                },
            )

            return WebhookData(
                payment_id=str(payment_id),
                order_id=order_id,
                status=status,
                amount=amount,
                currency=currency,
                signature=signature,
                raw_data=data,
            )

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse webhook data: {e}")
            raise PaymentValidationError(f"Invalid webhook data: {e}") from e

    def _verify_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify webhook signature using HMAC-SHA256.

        Args:
            raw_body: Raw request body.
            signature: Signature from X-Signature header.

        Returns:
            True if signature is valid, False otherwise.

        Raises:
            PaymentSignatureError: In production mode when secret not configured.
        """
        if not self._webhook_secret:
            # In debug mode, allow skipping signature verification with warning
            if settings.debug:
                logger.warning(
                    "No webhook secret configured, skipping signature verification (DEBUG mode only)"
                )
                return True
            # In production, require webhook secret for security
            logger.error("Webhook secret not configured in production mode")
            raise PaymentSignatureError("Webhook secret not configured")

        if not signature:
            return False

        expected_signature = hmac.new(
            self._webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature.lower(), expected_signature.lower())

    @staticmethod
    def _map_platega_status(status: PlategaStatus) -> PaymentStatus:
        """Map Platega status enum to internal PaymentStatus.

        Args:
            status: PlategaStatus enum value.

        Returns:
            PaymentStatus enum value.
        """
        status_map = {
            PlategaStatus.PENDING: PaymentStatus.PENDING,
            PlategaStatus.CONFIRMED: PaymentStatus.COMPLETED,
            PlategaStatus.CANCELED: PaymentStatus.CANCELLED,
            PlategaStatus.CHARGEBACKED: PaymentStatus.FAILED,
        }
        return status_map.get(status, PaymentStatus.PENDING)

    @staticmethod
    def _map_platega_status_str(status: str) -> PaymentStatus:
        """Map Platega status string to internal PaymentStatus.

        Args:
            status: Platega status string.

        Returns:
            PaymentStatus enum value.
        """
        status_map = {
            "PENDING": PaymentStatus.PENDING,
            "pending": PaymentStatus.PENDING,
            "CONFIRMED": PaymentStatus.COMPLETED,
            "confirmed": PaymentStatus.COMPLETED,
            "CANCELED": PaymentStatus.CANCELLED,
            "canceled": PaymentStatus.CANCELLED,
            "CHARGEBACKED": PaymentStatus.FAILED,
            "chargebacked": PaymentStatus.FAILED,
        }
        return status_map.get(status, PaymentStatus.PENDING)

    @staticmethod
    def map_status(status: str) -> PaymentStatus:
        """Map provider status string to internal PaymentStatus.

        This is a public method used by PaymentService.

        Args:
            status: Provider status string.

        Returns:
            PaymentStatus enum value.
        """
        return PlategaProvider._map_platega_status_str(status)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("Platega HTTP session closed")
