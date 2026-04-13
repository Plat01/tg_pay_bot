"""Referral service for business logic."""

import logging
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.infrastructure.database.repositories import ReferralEarningRepository, UserRepository
from src.models.payment import Payment
from src.models.referral import ReferralEarning, ReferralEarningStatus
from src.models.user import User

logger = logging.getLogger(__name__)


class ReferralService:
    """Service for referral-related business logic."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize referral service with session."""
        self.repository = ReferralEarningRepository(session)
        self.user_repository = UserRepository(session)

    async def process_referral_earning(self, payment: Payment) -> ReferralEarning | None:
        """Process referral earning for a completed payment."""
        # Get the user who made the payment
        user = await self.user_repository.get_by_id(payment.user_id)
        if not user or not user.referred_by_id:
            return None

        # Calculate earning amount
        earning_amount = payment.amount * settings.referral_bonus_percent / Decimal("100")

        # Create referral earning record
        earning_data = {
            "referrer_id": user.referred_by_id,
            "referral_id": user.id,
            "payment_id": payment.id,
            "amount": earning_amount,
            "percent": settings.referral_bonus_percent,
            "status": ReferralEarningStatus.PENDING,
        }
        earning = await self.repository.create(earning_data)

        # Update referrer's balance
        referrer = await self.user_repository.get_by_id(user.referred_by_id)
        if referrer:
            new_balance = referrer.balance + earning_amount
            await self.user_repository.update(referrer, {"balance": new_balance})

            # Send notification to referrer
            try:
                from src.bot.bot import bot
                from src.bot.texts import Texts

                referral_name = user.first_name or user.username or f"#{user.id}"
                referral_username = user.username or "нет username"
                example_bonus = int(1000 * settings.referral_bonus_percent / 100)

                await bot.send_message(
                    chat_id=referrer.telegram_id,
                    text=Texts.REFERRAL_EARNING_NOTIFICATION.format(
                        referral_name=referral_name,
                        referral_username=referral_username,
                        payment_amount=payment.amount,
                        bonus_percent=settings.referral_bonus_percent,
                        bonus_amount=earning_amount,
                        example_bonus=example_bonus,
                    ),
                    parse_mode="HTML",
                )

                logger.info(
                    f"Referral notification sent",
                    extra={
                        "referrer_id": referrer.id,
                        "referral_id": user.id,
                        "payment_id": payment.id,
                        "bonus_amount": str(earning_amount),
                    },
                )
            except Exception as e:
                logger.error(
                    f"Failed to send referral notification: {e}",
                    extra={
                        "referrer_id": referrer.id,
                        "referral_id": user.id,
                    },
                )

        return earning

    async def get_referrer_earnings(
        self,
        referrer_id: uuid.UUID,
        status: ReferralEarningStatus | None = None,
    ) -> list[ReferralEarning]:
        """Get all earnings for a referrer."""
        return await self.repository.get_referrer_earnings(referrer_id, status)

    async def get_total_pending_earnings(self, referrer_id: uuid.UUID) -> Decimal:
        """Get total pending earnings for a referrer."""
        return await self.repository.get_total_pending_earnings(referrer_id)

    async def get_referral_stats(self, user_id: uuid.UUID) -> dict:
        """Get referral statistics for a user."""
        referrals = await self.user_repository.get_referrals(user_id)
        total_earnings = await self.repository.get_total_pending_earnings(user_id)
        earnings = await self.repository.get_referrer_earnings(user_id)

        return {
            "total_referrals": len(referrals),
            "total_earnings": total_earnings,
            "pending_earnings": sum(
                e.amount for e in earnings if e.status == ReferralEarningStatus.PENDING
            ),
            "paid_earnings": sum(
                e.amount for e in earnings if e.status == ReferralEarningStatus.PAID
            ),
        }
