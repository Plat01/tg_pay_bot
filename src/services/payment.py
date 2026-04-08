"""Payment service for business logic.

This service orchestrates payment operations, integrating with
external payment providers and managing the payment lifecycle.
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.infrastructure.database.repositories import PaymentRepository, UserRepository
from src.infrastructure.payments import (
    PaymentProvider,
    PaymentProviderFactory,
    CreatePaymentResult,
    PlategaPaymentMethod,
)
from src.models.payment import Payment, PaymentStatus
from src.services.referral import ReferralService

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for payment-related business logic.

    This service handles the complete payment lifecycle:
    - Creating payments via external providers
    - Storing payment records in the database
    - Checking and updating payment status
    - Processing referral earnings on completion

    Example:
        >>> async with async_session_maker() as session:
        ...     service = PaymentService(session)
        ...     payment, result = await service.create_external_payment(
        ...         user_id=123,
        ...         amount=Decimal("1000"),
        ...         payment_method=PlategaPaymentMethod.SBP_QR,
        ...     )
        ...     print(result.payment_url)  # URL for user to pay
    """

    def __init__(
        self,
        session: AsyncSession,
        provider_name: str | None = None,
    ) -> None:
        """Initialize payment service.

        Args:
            session: Database session for repository operations.
            provider_name: Payment provider name (default from settings).
        """
        self.repository = PaymentRepository(session)
        self.user_repository = UserRepository(session)
        self.referral_service = ReferralService(session)
        self.provider_name = provider_name or settings.default_payment_provider
        self._provider: PaymentProvider | None = None
        self._closed: bool = False

    async def _get_user_id_by_telegram_id(self, telegram_id: str) -> uuid.UUID:
        """Resolve Telegram ID to user UUID.

        Args:
            telegram_id: Telegram user ID as string.

        Returns:
            User UUID from database.

        Raises:
            ValueError: If user not found.
        """
        user = await self.user_repository.get_by_telegram_id(telegram_id)
        if user is None:
            raise ValueError(f"User with telegram_id {telegram_id} not found")
        return user.id

    @property
    def provider(self) -> PaymentProvider:
        """Get or create payment provider instance.

        Lazy initialization of the provider, using factory
        to create based on configured provider name.

        Raises:
            RuntimeError: If service has been closed.

        Returns:
            PaymentProvider instance.
        """
        if self._closed:
            raise RuntimeError(
                "PaymentService has been closed. Create a new instance to use payment operations."
            )
        if self._provider is None:
            self._provider = PaymentProviderFactory.create(self.provider_name)
        return self._provider

    async def create_payment(
        self,
        telegram_id: str,
        amount: Decimal,
        currency: str = "RUB",
        description: str | None = None,
        payment_provider: str | None = None,
        external_id: str | None = None,
        payment_metadata: dict[str, Any] | None = None,
    ) -> Payment:
        """Create a new payment record in database.

        This method only creates the database record, not the
        external payment. Use create_external_payment for full flow.

        Args:
            telegram_id: Telegram user ID as string.
            amount: Payment amount.
            currency: Currency code (default: 'RUB').
            description: Payment description.
            payment_provider: Provider name (default: configured).
            external_id: ID from external system (if already created).
            payment_metadata: Additional metadata from provider.

        Returns:
            Created Payment model instance.
        """
        user_id = await self._get_user_id_by_telegram_id(telegram_id)

        payment_data = {
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "description": description,
            "payment_provider": payment_provider or self.provider_name,
            "external_id": external_id,
            "payment_metadata": payment_metadata,
            "status": PaymentStatus.PENDING,
        }

        logger.info(
            f"Creating payment record",
            extra={
                "user_id": user_id,
                "telegram_id": telegram_id,
                "amount": str(amount),
                "currency": currency,
                "provider": payment_provider or self.provider_name,
            },
        )

        return await self.repository.create(payment_data)

    async def create_external_payment(
        self,
        telegram_id: str,
        amount: Decimal,
        currency: str = "RUB",
        description: str | None = None,
        payment_method: PlategaPaymentMethod = PlategaPaymentMethod.SBP_QR,
        return_url: str | None = None,
        failed_url: str | None = None,
        **kwargs: Any,
    ) -> tuple[Payment, CreatePaymentResult]:
        """Create payment via provider and save to database.

        This is the main method for initiating a payment:
        1. Creates payment in external provider system
        2. Saves payment record to database with external_id
        3. Returns both database record and provider result

        Args:
            telegram_id: Telegram user ID as string.
            amount: Payment amount.
            currency: Currency code (default: 'RUB').
            description: Payment description.
            payment_method: Payment method (default: SBP_QR).
            return_url: Redirect URL after success.
            failed_url: Redirect URL after failure.
            **kwargs: Additional provider-specific options.

        Returns:
            Tuple of (Payment record, CreatePaymentResult from provider).

        Raises:
            PaymentCreationError: If provider fails to create payment.
            PaymentProviderUnavailable: If provider is unreachable.
        """
        user_id = await self._get_user_id_by_telegram_id(telegram_id)

        logger.info(
            f"Creating external payment",
            extra={
                "telegram_id": telegram_id,
                "user_id": user_id,
                "amount": str(amount),
                "currency": currency,
                "method": payment_method.name,
                "provider": self.provider_name,
            },
        )

        # Create payment in external system
        external_result = await self.provider.create_payment(
            amount=amount,
            currency=currency,
            description=description or f"Пополнение баланса пользователя {telegram_id}",
            metadata={"telegram_id": telegram_id, "user_id": str(user_id)},
            payment_method=payment_method,
            return_url=return_url,
            failed_url=failed_url,
            **kwargs,
        )

        # Save to database
        payment = await self.create_payment(
            telegram_id=telegram_id,
            amount=amount,
            currency=currency,
            description=description,
            payment_provider=self.provider_name,
            external_id=external_result.external_id,
            payment_metadata=external_result.metadata,
        )

        logger.info(
            f"External payment created successfully",
            extra={
                "payment_id": payment.id,
                "external_id": external_result.external_id,
                "telegram_id": telegram_id,
                "user_id": user_id,
            },
        )

        return payment, external_result

    async def get_payment_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        """Get payment by ID.

        Args:
            payment_id: Internal payment ID.

        Returns:
            Payment instance or None if not found.
        """
        return await self.repository.get_by_id(payment_id)

    async def get_payment_by_external_id(self, external_id: str) -> Payment | None:
        """Get payment by external provider ID.

        Args:
            external_id: ID from external payment system.

        Returns:
            Payment instance or None if not found.
        """
        return await self.repository.get_by_external_id(external_id)

    async def get_user_payments(
        self,
        telegram_id: str,
        status: PaymentStatus | None = None,
    ) -> list[Payment]:
        """Get all payments for a user.

        Args:
            telegram_id: Telegram user ID as string.
            status: Filter by status (optional).

        Returns:
            List of Payment instances.
        """
        user_id = await self._get_user_id_by_telegram_id(telegram_id)
        return await self.repository.get_user_payments(user_id, status)

    async def check_and_update_status(
        self,
        payment: Payment,
    ) -> Payment:
        """Check payment status from provider and update database.

        This method queries the external provider for the current
        status and updates the database record accordingly.

        Args:
            payment: Payment instance to check.

        Returns:
            Updated Payment instance.

        Raises:
            ValueError: If payment has no external_id.
            PaymentStatusError: If status check fails.
        """
        if not payment.external_id:
            raise ValueError(
                f"Payment {payment.id} has no external_id, cannot check status with provider"
            )

        logger.info(
            f"Checking payment status",
            extra={
                "payment_id": payment.id,
                "external_id": payment.external_id,
                "current_status": payment.status.value,
            },
        )

        # Get status from provider
        status_result = await self.provider.get_payment_status(payment.external_id)
        new_status = self.provider.map_status(status_result.status)

        logger.info(
            f"Payment status from provider",
            extra={
                "payment_id": payment.id,
                "external_status": status_result.status,
                "mapped_status": new_status.value,
            },
        )

        # Update if status changed
        if new_status != payment.status:
            if new_status == PaymentStatus.COMPLETED:
                payment = await self.complete_payment(payment)
            elif new_status == PaymentStatus.FAILED:
                payment = await self.fail_payment(payment)
            elif new_status == PaymentStatus.CANCELLED:
                payment = await self.cancel_payment(payment)
            else:
                # Just update status without special processing
                payment = await self.repository.update_status(payment, new_status)

            logger.info(
                f"Payment status updated",
                extra={
                    "payment_id": payment.id,
                    "old_status": payment.status.value,
                    "new_status": new_status.value,
                },
            )

        return payment

    async def complete_payment(self, payment: Payment) -> Payment:
        """Mark payment as completed and process referral earnings.

        This method:
        1. Updates payment status to COMPLETED
        2. Sets completion timestamp
        3. Processes referral earnings for the referrer

        Args:
            payment: Payment instance to complete.

        Returns:
            Updated Payment instance.
        """
        logger.info(
            f"Completing payment",
            extra={
                "payment_id": payment.id,
                "user_id": payment.user_id,
                "amount": str(payment.amount),
            },
        )

        # Update payment status
        payment = await self.repository.update_status(
            payment,
            PaymentStatus.COMPLETED,
            datetime.now(timezone.utc),
        )

        # Process referral earnings
        try:
            await self.referral_service.process_referral_earning(payment)
            logger.info(
                f"Referral earnings processed",
                extra={"payment_id": payment.id},
            )
        except Exception as e:
            # Log error but don't fail the payment completion
            logger.error(
                f"Failed to process referral earnings: {e}",
                extra={"payment_id": payment.id},
            )

        return payment

    async def fail_payment(self, payment: Payment) -> Payment:
        """Mark payment as failed.

        Args:
            payment: Payment instance to fail.

        Returns:
            Updated Payment instance.
        """
        logger.info(
            f"Failing payment",
            extra={"payment_id": payment.id},
        )
        return await self.repository.update_status(payment, PaymentStatus.FAILED)

    async def cancel_payment(self, payment: Payment) -> Payment:
        """Mark payment as cancelled.

        Args:
            payment: Payment instance to cancel.

        Returns:
            Updated Payment instance.
        """
        logger.info(
            f"Cancelling payment",
            extra={"payment_id": payment.id},
        )
        return await self.repository.update_status(payment, PaymentStatus.CANCELLED)

    async def close_provider(self) -> None:
        """Close payment provider resources.

        Should be called when shutting down or switching providers.
        After calling this method, the service instance cannot be reused.
        """
        if self._closed:
            logger.debug("Payment provider already closed")
            return

        self._closed = True

        if self._provider:
            await self._provider.close()
            self._provider = None
            logger.debug("Payment provider closed")

    async def __aenter__(self) -> "PaymentService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures provider is closed."""
        await self.close_provider()
