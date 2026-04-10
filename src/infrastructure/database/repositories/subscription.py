"""Subscription repository for database operations."""

from datetime import datetime, timezone
import uuid
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.infrastructure.database.repositories.base import BaseRepository
from src.models.subscription import Subscription


class SubscriptionRepository(BaseRepository[Subscription]):
    """Repository for Subscription model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize subscription repository."""
        super().__init__(Subscription, session)

    async def get_active_subscription(self, user_id: uuid.UUID) -> Subscription | None:
        """Get active subscription for user by user ID (UUID)."""
        statement = (
            select(Subscription)
            .options(selectinload(Subscription.product))
            .where(Subscription.user_id == user_id)
            .where(Subscription.is_active == True)
            .where(Subscription.end_date > datetime.now(timezone.utc))
            .order_by(desc(Subscription.end_date))
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
            .where(Subscription.is_active == True)  # Only include active subscriptions
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
