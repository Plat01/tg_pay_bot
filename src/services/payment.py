"""Payment service for business logic."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.payment import Payment, PaymentStatus
from src.repositories.payment import PaymentRepository
from src.services.referral import ReferralService


class PaymentService:
    """Service for payment-related business logic."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize payment service with session."""
        self.repository = PaymentRepository(session)
        self.referral_service = ReferralService(session)

    async def create_payment(
        self,
        user_id: int,
        amount: Decimal,
        currency: str = "RUB",
        description: str | None = None,
        payment_provider: str | None = None,
    ) -> Payment:
        """Create a new payment."""
        payment_data = {
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "description": description,
            "payment_provider": payment_provider,
            "status": PaymentStatus.PENDING,
        }
        return await self.repository.create(payment_data)

    async def get_payment_by_id(self, payment_id: int) -> Payment | None:
        """Get payment by ID."""
        return await self.repository.get_by_id(payment_id)

    async def get_user_payments(
        self,
        user_id: int,
        status: PaymentStatus | None = None,
    ) -> list[Payment]:
        """Get all payments for a user."""
        return await self.repository.get_user_payments(user_id, status)

    async def complete_payment(self, payment: Payment) -> Payment:
        """Mark payment as completed and process referral earnings."""
        # Update payment status
        payment = await self.repository.update_status(
            payment,
            PaymentStatus.COMPLETED,
            datetime.utcnow(),
        )

        # Process referral earnings
        await self.referral_service.process_referral_earning(payment)

        return payment

    async def fail_payment(self, payment: Payment) -> Payment:
        """Mark payment as failed."""
        return await self.repository.update_status(payment, PaymentStatus.FAILED)

    async def cancel_payment(self, payment: Payment) -> Payment:
        """Mark payment as cancelled."""
        return await self.repository.update_status(payment, PaymentStatus.CANCELLED)