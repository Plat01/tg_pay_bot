"""Payment repository for database operations."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.repositories.base import BaseRepository
from src.models.payment import Payment, PaymentStatus


class PaymentRepository(BaseRepository[Payment]):
    """Repository for Payment model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize payment repository."""
        super().__init__(Payment, session)

    async def get_by_external_id(self, external_id: str) -> Payment | None:
        """Get payment by external ID."""
        statement = select(Payment).where(Payment.external_id == external_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user_payments(
        self,
        user_id: uuid.UUID,
        status: PaymentStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Payment]:
        """Get all payments for a user."""
        statement = select(Payment).where(Payment.user_id == user_id)
        if status:
            statement = statement.where(Payment.status == status)
        statement = statement.offset(skip).limit(limit).order_by(Payment.created_at.desc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update_status(
        self,
        payment: Payment,
        status: PaymentStatus,
        completed_at: datetime | None = None,
    ) -> Payment:
        """Update payment status."""
        payment.status = status
        if completed_at:
            payment.completed_at = completed_at
        payment.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_active_pending_payments(
        self,
        newer_than: datetime,
        limit: int = 100,
    ) -> list[Payment]:
        """Get PENDING payments newer than specified datetime (active payments).

        Payments created AFTER this datetime are considered active
        and should be checked with provider.

        Args:
            newer_than: Datetime threshold (payments created after this)
            limit: Maximum number of payments to return

        Returns:
            List of active PENDING Payment instances.
        """
        statement = (
            select(Payment)
            .where(Payment.status == PaymentStatus.PENDING)
            .where(Payment.created_at > newer_than)
            .where(Payment.external_id.isnot(None))
            .order_by(Payment.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_expired_pending_payments(
        self,
        older_than: datetime,
        limit: int = 100,
    ) -> list[Payment]:
        """Get PENDING payments older than specified datetime (expired payments).

        Payments created BEFORE this datetime are considered expired
        and should be marked as EXPIRED without checking provider.

        Args:
            older_than: Datetime threshold (payments created before this)
            limit: Maximum number of payments to return

        Returns:
            List of expired PENDING Payment instances.
        """
        statement = (
            select(Payment)
            .where(Payment.status == PaymentStatus.PENDING)
            .where(Payment.created_at < older_than)
            .where(Payment.external_id.isnot(None))
            .order_by(Payment.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
