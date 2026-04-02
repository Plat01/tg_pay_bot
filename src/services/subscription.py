"""Subscription service for business logic."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.repositories import SubscriptionRepository
from src.models.subscription import Subscription


class SubscriptionService:
    """Service for subscription-related business logic."""

    # Subscription durations
    TRIAL_DAYS = 3
    MONTHLY_DAYS = 30
    QUARTERLY_DAYS = 90
    YEARLY_DAYS = 365

    # Device limits by subscription type
    DEVICE_LIMITS = {
        "trial": 1,
        "monthly": 1,
        "quarterly": 2,
        "yearly": 5,
    }

    def __init__(self, session: AsyncSession) -> None:
        """Initialize subscription service."""
        self.repository = SubscriptionRepository(session)

    async def get_active_subscription(self, user_id: uuid.UUID) -> Subscription | None:
        """Get active subscription for user by user ID (UUID)."""
        return await self.repository.get_active_subscription(user_id)

    async def create_subscription(
        self,
        user_id: uuid.UUID,
        subscription_type: str,
        days: Optional[int] = None,
    ) -> Subscription:
        """Create a new subscription.

        Args:
            user_id: User UUID to create subscription for.
            subscription_type: Type of subscription (trial, monthly, quarterly, yearly).
            days: Optional custom duration in days. If not provided, uses default for type.
        """
        if days is None:
            days = {
                "trial": self.TRIAL_DAYS,
                "monthly": self.MONTHLY_DAYS,
                "quarterly": self.QUARTERLY_DAYS,
                "yearly": self.YEARLY_DAYS,
            }.get(subscription_type, self.MONTHLY_DAYS)

        device_limit = self.DEVICE_LIMITS.get(subscription_type, 1)
        end_date = datetime.utcnow() + timedelta(days=days)

        return await self.repository.create_subscription(
            user_id=user_id,
            subscription_type=subscription_type,
            end_date=end_date,
            device_limit=device_limit,
        )

    async def activate_trial(
        self,
        user_id: uuid.UUID,
    ) -> Subscription:
        """Activate trial subscription for user."""
        return await self.create_subscription(
            user_id=user_id,
            subscription_type="trial",
            days=self.TRIAL_DAYS,
        )

    def get_subscription_info(self, subscription: Subscription) -> dict:
        """Get subscription info for display.

        Args:
            subscription: Subscription instance.

        Returns:
            Dictionary with subscription info.
        """
        now = datetime.utcnow()
        time_left = subscription.end_date - now

        days_left = time_left.days
        hours_left = (time_left.seconds // 3600) % 24

        return {
            "subscription_type": subscription.subscription_type,
            "end_date": subscription.end_date,
            "device_limit": subscription.device_limit,
            "is_active": subscription.is_active and subscription.end_date > now,
            "days_left": days_left,
            "hours_left": hours_left,
        }
