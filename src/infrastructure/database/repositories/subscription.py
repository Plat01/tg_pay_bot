"""Subscription repository for database operations."""

from datetime import datetime
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
            .where(Subscription.user_id == user_id)
            .where(Subscription.is_active == True)
            .where(Subscription.end_date > datetime.utcnow())
            .order_by(Subscription.end_date.desc())
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user_subscriptions(self, user_id: uuid.UUID, limit: int = 10) -> list[Subscription]:
        """Get all subscriptions for user by user ID (UUID)."""
        statement = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create_subscription(
        self,
        user_id: uuid.UUID,
        subscription_type: str,
        end_date: datetime,
        device_limit: int = 1,
    ) -> Subscription:
        """Create a new subscription."""
        subscription_data = {
            "user_id": user_id,
            "subscription_type": subscription_type,
            "end_date": end_date,
            "device_limit": device_limit,
        }
        return await self.create(subscription_data)

    async def deactivate_subscription(self, subscription: Subscription) -> Subscription:
        """Deactivate a subscription."""
        return await self.update(subscription, {"is_active": False})
