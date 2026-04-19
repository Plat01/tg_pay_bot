"""Subscription repository for database operations."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.infrastructure.database.repositories.base import BaseRepository
from src.models.subscription import Subscription


class SubscriptionRepository(BaseRepository[Subscription]):
    """Repository for Subscription model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize subscription repository."""
        super().__init__(Subscription, session)

    async def get_active_subscriptions(self, user_id: uuid.UUID) -> list[Subscription]:
        """Get all active subscriptions for user by user ID (UUID)."""
        statement = (
            select(Subscription)
            .options(selectinload(Subscription.product))
            .where(Subscription.user_id == user_id)
            .where(Subscription.is_active)
            .where(Subscription.end_date > datetime.now(UTC))
            .order_by(desc(Subscription.end_date))
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_subscription_by_id(self, subscription_id: uuid.UUID) -> Subscription | None:
        """Get subscription by ID (UUID)."""
        statement = (
            select(Subscription)
            .options(selectinload(Subscription.product))
            .where(Subscription.id == subscription_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_active_subscription_by_id(
        self, subscription_id: uuid.UUID
    ) -> Subscription | None:
        """Get active subscription by ID (UUID).

        Returns subscription only if it's active AND not expired.
        """
        statement = (
            select(Subscription)
            .options(selectinload(Subscription.product))
            .where(Subscription.id == subscription_id)
            .where(Subscription.is_active)
            .where(Subscription.end_date > datetime.now(UTC))
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user_subscriptions(
        self, user_id: uuid.UUID, limit: int = 10
    ) -> list[Subscription]:
        """Get all subscriptions for user by user ID (UUID)."""
        statement = (
            select(Subscription)
            .options(selectinload(Subscription.product))
            .where(Subscription.user_id == user_id)
            .where(Subscription.is_active)  # Only include active subscriptions
            .order_by(desc(Subscription.created_at))
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create_subscription(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        end_date: datetime,
        start_date: datetime,
    ) -> Subscription:
        """Create a new subscription."""
        subscription_data = {
            "user_id": user_id,
            "product_id": product_id,
            "end_date": end_date,
            "start_date": start_date,
        }
        return await self.create(subscription_data)

    async def deactivate_subscription(self, subscription: Subscription) -> Subscription:
        """Deactivate a subscription."""
        return await self.update(subscription, {"is_active": False})

    async def get_expiring_subscriptions(
        self, hours_before: int = 24, check_interval_hours: int = 1, limit: int = 100
    ) -> list[Subscription]:
        """Get active subscriptions expiring within a specific window.

        Selects subscriptions that will expire in the window:
        [hours_before - check_interval_hours, hours_before]

        This prevents duplicate notifications when checking periodically.

        Args:
            hours_before: Upper bound of the window (hours before expiry).
            check_interval_hours: Width of the window (check frequency).
            limit: Maximum number of subscriptions to return.

        Returns:
            List of active subscriptions expiring within the specified window.
        """
        now = datetime.now(UTC)
        window_start = now + timedelta(hours=hours_before - check_interval_hours)
        window_end = now + timedelta(hours=hours_before)

        statement = (
            select(Subscription)
            .options(selectinload(Subscription.product), selectinload(Subscription.user))
            .where(Subscription.is_active)
            .where(Subscription.end_date > window_start)
            .where(Subscription.end_date <= window_end)
            .order_by(Subscription.end_date)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_all_active_subscriptions_with_details(self) -> list[Subscription]:
        """Get all active subscriptions with user and product details.

        Returns:
            List of active subscriptions with loaded user and product relationships,
            ordered by end_date ascending.
        """
        statement = (
            select(Subscription)
            .options(selectinload(Subscription.product), selectinload(Subscription.user))
            .where(Subscription.is_active)
            .where(Subscription.end_date > datetime.now(UTC))
            .order_by(Subscription.end_date)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
