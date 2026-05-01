"""Payment service for business logic.

This module provides business logic for payment operations:
- Creating payments (external via Platega, internal balance top-ups)
- Checking payment status via Platega API
- Completing payments and delivering subscriptions (balance or VPN subscriptions)
- Managing payment records in database
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.tariff import TariffService
from src.services.referral import ReferralService
from src.services.vpn_subscription import VpnSubscriptionService, TARIFF_DURATION
from src.config import settings
from src.infrastructure.database.repositories import (
    PaymentRepository,
    UserRepository,
)
from src.infrastructure.payments import (
    PaymentProvider,
    PaymentProviderFactory,
    CreatePaymentResult,
    PlategaPaymentMethod,
)
from src.infrastructure.vpn_subscription.exceptions import VpnSubscriptionError
from src.models.payment import Payment, PaymentStatus
from src.models.user import User
from src.services.subscription import SubscriptionService

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
        self.session = session
        self.repository = PaymentRepository(session)
        self.user_repository = UserRepository(session)
        self.referral_service = ReferralService(session)
        self.subscription_service = SubscriptionService(session)
        self.vpn_subscription_service: VpnSubscriptionService | None = None
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

        logger.error(
            f"Creating payment record: user_id={user_id}, telegram_id={telegram_id}, "
            f"amount={amount}, currency={currency}, provider={payment_provider or self.provider_name}"
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

        logger.error(
            f"Creating external payment: telegram_id={telegram_id}, user_id={user_id}, "
            f"amount={amount}, currency={currency}, method={payment_method.name}, provider={self.provider_name}"
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

        # Validate external_id before saving
        if not external_result.external_id or external_result.external_id.strip() == "":
            logger.error(
                f"Provider returned empty external_id: "
                f"provider={self.provider_name}, telegram_id={telegram_id}, "
                f"amount={amount}, success={external_result.success}, "
                f"error_message={external_result.error_message}"
            )
            raise ValueError(
                "Платеж не создан: провайдер вернул пустый external_id. "
                "Попробуйте еще раз или выберите другой способ оплаты."
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

        logger.error(
            f"External payment created successfully: payment_id={payment.id}, "
            f"external_id={external_result.external_id}, telegram_id={telegram_id}, user_id={user_id}"
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

        logger.error(
            f"Checking payment status: payment_id={payment.id}, "
            f"external_id={payment.external_id}, current_status={payment.status.value}"
        )

        # Get status from provider
        status_result = await self.provider.get_payment_status(payment.external_id)
        new_status = status_result.status

        logger.error(
            f"Payment status from provider: payment_id={payment.id}, "
            f"external_status={status_result.external_status}, mapped_status={new_status.value}"
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

            logger.error(
                f"Payment status updated: payment_id={payment.id}, "
                f"old_status={payment.status.value}, new_status={new_status.value}"
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
        logger.error(
            f"Completing payment: payment_id={payment.id}, "
            f"user_id={payment.user_id}, amount={payment.amount}"
        )

        # Update payment status
        payment = await self.repository.update_status(
            payment,
            PaymentStatus.COMPLETED,
            datetime.now(timezone.utc),
        )

        # Process referral earnings only for external payments (not balance)
        if payment.payment_provider != "balance":
            try:
                await self.referral_service.process_referral_earning(payment)
                logger.error(
                    f"Referral earnings processed: payment_id={payment.id}"
                )
            except Exception as e:
                # Log error but don't fail the payment completion
                logger.error(
                    f"Failed to process referral earnings: {e} (payment_id={payment.id})"
                )
        else:
            logger.error(
                f"Skipping referral earnings for balance payment: payment_id={payment.id}"
            )

        return payment

    async def fail_payment(self, payment: Payment) -> Payment:
        """Mark payment as failed.

        Args:
            payment: Payment instance to fail.

        Returns:
            Updated Payment instance.
        """
        logger.error(f"Failing payment: payment_id={payment.id}")
        return await self.repository.update_status(payment, PaymentStatus.FAILED)

    async def cancel_payment(self, payment: Payment) -> Payment:
        """Mark payment as cancelled.

        Args:
            payment: Payment instance to cancel.

        Returns:
            Updated Payment instance.
        """
        logger.error(f"Cancelling payment: payment_id={payment.id}")
        return await self.repository.update_status(payment, PaymentStatus.CANCELLED)

    async def complete_payment_and_deliver(
        self,
        payment: Payment,
        telegram_id: str,
    ) -> dict[str, Any]:
        """Complete payment and deliver appropriate product.

        Handles both subscription and balance deposit payments.

        Args:
            payment: Payment to complete
            telegram_id: User Telegram ID for notifications

        Returns:
            Dict with delivery details (subscription_id, vpn_link, etc.)

        Raises:
            ValueError: If payment type unknown or product not found
        """
        logger.error(
            f"Completing payment and delivering product: payment_id={payment.id}, "
            f"amount={payment.amount}, description={payment.description}"
        )

        if payment.description and payment.description.startswith("Подписка:"):
            result = await self._deliver_subscription(payment)
            logger.error(
                f"Subscription delivered: payment_id={payment.id}, "
                f"subscription_id={result['subscription_id']}"
            )
            return result
        elif payment.description and payment.description.startswith("Пополнение"):
            result = await self._deliver_balance_topup(payment)
            logger.error(
                f"Balance topup delivered: payment_id={payment.id}, "
                f"new_balance={result['new_balance']}"
            )
            return result
        else:
            raise ValueError(f"Unknown payment type: {payment.description}")

    async def _deliver_subscription(self, payment: Payment) -> dict[str, Any]:
        """Create subscription for successful payment.

        Args:
            payment: Payment instance

        Returns:
            Dict with subscription details

        Raises:
            ValueError: If tariff not found
            VpnSubscriptionError: If VPN subscription creation fails
        """
        tariff_service = TariffService(self.session)
        tariff_type = await tariff_service.get_tariff_by_price(int(payment.amount))

        if not tariff_type:
            raise ValueError(f"Cannot determine tariff for amount {payment.amount}")

        if tariff_type not in TARIFF_DURATION:
            raise ValueError(f"Invalid tariff type: {tariff_type}")

        duration_days = TARIFF_DURATION[tariff_type]["days"]

        subscription = await self.subscription_service.create_subscription(
            user_id=payment.user_id,
            subscription_type=tariff_type,
            duration_days=duration_days,
        )

        vpn_link = None
        try:
            self.vpn_subscription_service = VpnSubscriptionService(self.session)
            encrypted_sub = await self.vpn_subscription_service.create_subscription_for_tariff(
                tariff_type=tariff_type,
                subscription_id=subscription.id,
            )
            vpn_link = encrypted_sub.encrypted_link

            encrypted_sub.subscription_id = subscription.id
            self.session.add(encrypted_sub)
            await self.session.commit()
        except VpnSubscriptionError as e:
            logger.error(
                f"Failed to create VPN subscription: {e}",
                extra={
                    "payment_id": str(payment.id),
                    "subscription_id": str(subscription.id),
                    "tariff_type": tariff_type,
                },
            )

        return {
            "type": "subscription",
            "subscription_id": subscription.id,
            "vpn_link": vpn_link or "VPN link pending - try again later",
            "duration_days": duration_days,
        }

    async def _deliver_balance_topup(self, payment: Payment) -> dict[str, Any]:
        """Update user balance for successful deposit.

        Args:
            payment: Payment instance

        Returns:
            Dict with balance details

        Raises:
            ValueError: If user not found
        """
        user = await self.user_repository.get_by_id(payment.user_id)

        if not user:
            raise ValueError(f"User not found: {payment.user_id}")

        new_balance = user.balance + payment.amount
        user = await self.user_repository.update(user, {"balance": new_balance})

        return {
            "type": "balance",
            "amount": payment.amount,
            "new_balance": user.balance,
        }

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
