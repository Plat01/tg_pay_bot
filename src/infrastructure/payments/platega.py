"""Platega payment provider implementation.

Documentation: https://docs.platega.io/

Platega API endpoints:
- POST /transaction/process - Create transaction
- GET /transaction/{id} - Get transaction status
"""

import asyncio
import hashlib
import hmac
import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import aiohttp
from pydantic import Field

from src.config import settings
from src.models.payment import PaymentStatus
from src.infrastructure.payments.base import (
    CreatePaymentResult,
    PaymentMethodInfo,
    PaymentMethodKind,
    PaymentProvider,
    PaymentProviderName,
    PaymentStatusResult,
    WebhookData,
)
from src.infrastructure.payments.exceptions import (
    PaymentCreationError,
    PaymentProviderError,
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

# Способы оплаты Platega -> общий для всех провайдеров тип способа.
# Названия и эмодзи кнопок берутся из типа (PAYMENT_METHOD_KIND_VIEW),
# поэтому кнопка выглядит одинаково независимо от провайдера.
PLATEGA_METHODS: dict[PlategaPaymentMethod, PaymentMethodKind] = {
    PlategaPaymentMethod.SBP_QR: PaymentMethodKind.SBP,
    PlategaPaymentMethod.CARD_ACQUIRING: PaymentMethodKind.CARD_RU,
    PlategaPaymentMethod.INTERNATIONAL: PaymentMethodKind.CARD_INTL,
    PlategaPaymentMethod.ERIP: PaymentMethodKind.ERIP,
    PlategaPaymentMethod.CRYPTO: PaymentMethodKind.CRYPTO,
}


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

    def is_configured(self) -> bool:
        """Check that merchant ID and secret are set in the settings.

        Returns:
            True if credentials are present, False otherwise.
        """
        return bool(self._merchant_id and self._api_key)

    def _get_enabled_methods(self) -> list[PlategaPaymentMethod]:
        """Parse enabled payment method codes from the settings.

        Unknown or malformed codes are skipped with a warning, so a typo in
        the .env file cannot break the whole keyboard.

        Returns:
            List of enabled PlategaPaymentMethod values.
        """
        enabled: list[PlategaPaymentMethod] = []

        for raw_code in settings.platega_enabled_methods.split(","):
            code = raw_code.strip()
            if not code:
                continue
            try:
                method = PlategaPaymentMethod(int(code))
            except ValueError:
                logger.warning(f"Unknown Platega payment method in settings: {code!r}")
                continue
            if method not in enabled:
                enabled.append(method)

        return enabled

    def get_payment_methods(self) -> list[PaymentMethodInfo]:
        """Get payment methods enabled for this installation.

        Returns:
            List of PaymentMethodInfo sorted by button order.
        """
        methods: list[PaymentMethodInfo] = []

        for method in self._get_enabled_methods():
            methods.append(
                PaymentMethodInfo(
                    provider=self.name.value,
                    code=str(method.value),
                    kind=PLATEGA_METHODS[method],
                )
            )

        methods.sort(key=lambda item: item.order)
        return methods

    async def check_method_availability(self, method: PaymentMethodInfo) -> bool:
        """Check that a payment method is enabled for this merchant.

        Platega does not report which methods a merchant has, so the only
        way to find out is to try to create a transaction: a method that is
        switched off makes the API answer with an error.

        The probe transaction is never saved to the database and is left
        unpaid, so it expires on the Platega side by itself.

        Args:
            method: Method to check.

        Returns:
            True if Platega accepted a transaction with this method.
        """
        try:
            result = await self.create_payment(
                amount=settings.payment_method_probe_amount,
                currency="RUB",
                description="Проверка доступности способа оплаты",
                payment_method=method.code,
            )
        except PaymentProviderError as e:
            logger.error(
                f"Platega payment method probe failed: method={method.code} "
                f"({method.label}), error={e}"
            )
            return False

        if not result.success:
            logger.error(
                f"Platega payment method is not available: method={method.code} "
                f"({method.label}), error={result.error_message}"
            )
            return False

        logger.error(
            f"Platega payment method is available: method={method.code} ({method.label})"
        )
        return True

    async def check_availability(self) -> bool:
        """Check that the Platega API is reachable and credentials are valid.

        Requests a random transaction: an answer with any status except
        401/403 (bad credentials) and 5xx (provider problems) means the API
        works and accepts our headers.

        Returns:
            True if the provider can be used right now, False otherwise.
        """
        if not self.is_configured():
            logger.warning("Platega provider is not configured: merchant_id or secret is empty")
            return False

        url = f"{self._api_url}/transaction/{uuid4()}"
        timeout = aiohttp.ClientTimeout(total=settings.payment_provider_check_timeout)

        try:
            session = await self._get_session()
            async with session.get(url, timeout=timeout) as response:
                if response.status in (401, 403):
                    logger.error(
                        f"Platega credentials rejected during availability check: "
                        f"status={response.status}"
                    )
                    return False
                if response.status >= 500:
                    logger.error(
                        f"Platega API returned server error during availability check: "
                        f"status={response.status}"
                    )
                    return False

                logger.info(f"Platega provider is available (status={response.status})")
                return True

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Platega availability check failed: {e}")
            return False

    @staticmethod
    def _coerce_payment_method(
        payment_method: "PlategaPaymentMethod | int | str | None",
    ) -> PlategaPaymentMethod | None:
        """Convert a payment method code to PlategaPaymentMethod.

        Handlers pass the method code as a string (it comes from callback
        data), older code passes the enum itself.

        Args:
            payment_method: Enum value, numeric code or None.

        Returns:
            PlategaPaymentMethod or None if nothing was passed.

        Raises:
            PaymentValidationError: If the code is unknown.
        """
        if payment_method is None:
            return None
        if isinstance(payment_method, PlategaPaymentMethod):
            return payment_method

        try:
            return PlategaPaymentMethod(int(payment_method))
        except (TypeError, ValueError) as e:
            raise PaymentValidationError(
                f"Unknown Platega payment method: {payment_method!r}"
            ) from e

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
        payment_method: PlategaPaymentMethod | int | str | None = None,
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
            payment_method: Payment method (enum or numeric code,
                defaults to the provider default).
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

        # Use provided payment method (enum or code) or the default one
        method = self._coerce_payment_method(payment_method) or self._default_payment_method

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

        logger.error(
            f"Creating Platega payment: amount={amount}, currency={currency}, method={method.name}"
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

                logger.error(
                    f"Platega payment created successfully: transaction_id={transaction_id}, "
                    f"payment_url={payment_url}, expires_at={expires_at_str}"
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

        logger.error(f"Checking Platega payment status: payment_id={payment_id}")

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

                logger.error(
                    f"Platega payment status retrieved: payment_id={payment_id}, "
                    f"status={status.value}, amount={amount}"
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

            logger.error(
                f"Platega webhook parsed: payment_id={payment_id}, "
                f"status={status.value}, amount={amount}"
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
