"""Repository for EncryptedSubscription model operations."""

import uuid
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.encrypted_subscription import EncryptedSubscription


class EncryptedSubscriptionRepository:
    """Repository for EncryptedSubscription model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, encrypted_id: uuid.UUID) -> EncryptedSubscription | None:
        """Get encrypted subscription by ID."""
        stmt = select(EncryptedSubscription).where(EncryptedSubscription.id == encrypted_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_subscription_id(
        self, subscription_id: uuid.UUID
    ) -> EncryptedSubscription | None:
        """Get encrypted subscription by linked subscription ID.

        Returns the most recent active encrypted subscription for the subscription.
        """
        stmt = (
            select(EncryptedSubscription)
            .where(EncryptedSubscription.subscription_id == subscription_id)
            .where(EncryptedSubscription.expires_at > datetime.now(UTC))
            .order_by(desc(EncryptedSubscription.expires_at))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_public_id(self, public_id: str) -> EncryptedSubscription | None:
        """Get encrypted subscription by public ID."""
        stmt = select(EncryptedSubscription).where(EncryptedSubscription.public_id == public_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_subscription_id(
        self, subscription_id: uuid.UUID, limit: int = 10
    ) -> Sequence[EncryptedSubscription]:
        """Get all encrypted subscriptions for a subscription (history)."""
        stmt = (
            select(EncryptedSubscription)
            .where(EncryptedSubscription.subscription_id == subscription_id)
            .order_by(desc(EncryptedSubscription.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_expired(self, limit: int = 100) -> Sequence[EncryptedSubscription]:
        """Get expired encrypted subscriptions for cleanup."""
        stmt = (
            select(EncryptedSubscription)
            .where(EncryptedSubscription.expires_at <= datetime.now(UTC))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_active_standalone(self, limit: int = 100) -> Sequence[EncryptedSubscription]:
        """Get active encrypted subscriptions without linked subscription (trial, standalone).

        These are subscriptions created directly via API without a Subscription record.
        """
        stmt = (
            select(EncryptedSubscription)
            .where(EncryptedSubscription.subscription_id.is_(None))
            .where(EncryptedSubscription.expires_at > datetime.now(UTC))
            .order_by(desc(EncryptedSubscription.expires_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, data: dict) -> EncryptedSubscription:
        """Create new encrypted subscription."""
        encrypted_sub = EncryptedSubscription(**data)
        self.session.add(encrypted_sub)
        await self.session.commit()
        await self.session.refresh(encrypted_sub)
        return encrypted_sub

    async def update(
        self, encrypted_id: uuid.UUID, data: dict
    ) -> EncryptedSubscription | None:
        """Update encrypted subscription fields."""
        encrypted_sub = await self.get_by_id(encrypted_id)
        if not encrypted_sub:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(encrypted_sub, key, value)

        encrypted_sub.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(encrypted_sub)
        return encrypted_sub

    async def delete(self, encrypted_id: uuid.UUID) -> bool:
        """Delete encrypted subscription by ID."""
        encrypted_sub = await self.get_by_id(encrypted_id)
        if not encrypted_sub:
            return False

        await self.session.delete(encrypted_sub)
        await self.session.commit()
        return True

    async def delete_expired(self, older_than_days: int = 30) -> int:
        """Delete expired encrypted subscriptions older than specified days.

        Returns count of deleted records.
        """
        threshold = datetime.now(UTC) - __import__('datetime').timedelta(days=older_than_days)
        stmt = select(EncryptedSubscription).where(
            and_(
                EncryptedSubscription.expires_at <= threshold,
                EncryptedSubscription.subscription_id.is_(None)  # Only standalone
            )
        )
        result = await self.session.execute(stmt)
        expired = result.scalars().all()

        count = 0
        for enc_sub in expired:
            await self.session.delete(enc_sub)
            count += 1

        await self.session.commit()
        return count

    async def refresh_link(
        self,
        subscription_id: uuid.UUID,
        new_link: str,
        new_expires_at: datetime,
        new_public_id: str | None = None,
    ) -> EncryptedSubscription | None:
        """Refresh encrypted subscription link for existing subscription.

        Updates the link and expiration for an existing encrypted subscription.
        """
        encrypted_sub = await self.get_by_subscription_id(subscription_id)
        if not encrypted_sub:
            return None

        encrypted_sub.encrypted_link = new_link
        encrypted_sub.expires_at = new_expires_at
        if new_public_id:
            encrypted_sub.public_id = new_public_id
        encrypted_sub.updated_at = datetime.now(UTC)

        await self.session.commit()
        await self.session.refresh(encrypted_sub)
        return encrypted_sub