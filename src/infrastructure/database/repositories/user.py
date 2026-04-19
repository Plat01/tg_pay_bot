"""User repository for database operations."""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.repositories.base import BaseRepository
from src.models.user import User


class UserRepository(BaseRepository[User]):
    """Repository for User model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize user repository."""
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: str) -> User | None:
        """Get user by Telegram ID."""
        statement = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        statement = select(User).where(User.username == username)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, referral_code: str) -> User | None:
        """Get user by referral code."""
        statement = select(User).where(User.referral_code == referral_code)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_referrals(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[User]:
        """Get all users referred by this user."""
        statement = select(User).where(User.referred_by_id == user_id).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_all_users(self, skip: int = 0, limit: int = 100000) -> list[User]:
        """Get all users with pagination."""
        statement = select(User).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_users_with_active_subscription(self) -> list[User]:
        """Get all users with active paid subscription."""
        from sqlalchemy.distinct import distinct
        from src.models.subscription import Subscription
        from datetime import datetime, timezone

        statement = (
            select(User)
            .join(Subscription, User.id == Subscription.user_id)
            .where(Subscription.is_active == True)
            .where(Subscription.end_date > datetime.now(timezone.utc))
            .distinct()
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
