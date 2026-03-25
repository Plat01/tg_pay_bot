"""Referral earning repository for database operations."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.referral import ReferralEarning, ReferralEarningStatus
from src.repositories.base import BaseRepository


class ReferralEarningRepository(BaseRepository[ReferralEarning]):
    """Repository for ReferralEarning model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize referral earning repository."""
        super().__init__(ReferralEarning, session)

    async def get_referrer_earnings(
        self,
        referrer_id: int,
        status: ReferralEarningStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ReferralEarning]:
        """Get all earnings for a referrer."""
        statement = select(ReferralEarning).where(ReferralEarning.referrer_id == referrer_id)
        if status:
            statement = statement.where(ReferralEarning.status == status)
        statement = statement.offset(skip).limit(limit).order_by(ReferralEarning.created_at.desc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_total_pending_earnings(self, referrer_id: int) -> Decimal:
        """Get total pending earnings for a referrer."""
        statement = select(ReferralEarning).where(
            ReferralEarning.referrer_id == referrer_id,
            ReferralEarning.status == ReferralEarningStatus.PENDING,
        )
        result = await self.session.execute(statement)
        earnings = result.scalars().all()
        return sum(e.amount for e in earnings)

    async def mark_as_paid(self, earning: ReferralEarning) -> ReferralEarning:
        """Mark earning as paid."""
        earning.status = ReferralEarningStatus.PAID
        earning.paid_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(earning)
        return earning