"""Subscription service for business logic."""

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.repositories import SubscriptionRepository, EncryptedSubscriptionRepository
from src.models.subscription import Subscription
from src.models.encrypted_subscription import EncryptedSubscription

MSK_TZ = ZoneInfo("Europe/Moscow")

TARIFF_DURATION_DAYS = {
    "trial": 3,
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
}


class SubscriptionService:
    """Service for subscription-related business logic."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize subscription service."""
        self.repository = SubscriptionRepository(session)
        self.encrypted_repository = EncryptedSubscriptionRepository(session)

    async def get_active_subscriptions(self, user_id: uuid.UUID) -> list[Subscription]:
        """Get all active subscriptions for user by user ID (UUID)."""
        return await self.repository.get_active_subscriptions(user_id)

    async def get_subscription_by_id(self, subscription_id: uuid.UUID) -> Subscription | None:
        """Get subscription by ID (UUID)."""
        return await self.repository.get_subscription_by_id(subscription_id)

    async def get_active_subscription_by_id(
        self, subscription_id: uuid.UUID
    ) -> Subscription | None:
        """Get active subscription by ID (UUID). Returns None if expired or inactive."""
        return await self.repository.get_active_subscription_by_id(subscription_id)

    async def create_subscription_by_type(
        self,
        user_id: uuid.UUID,
        subscription_type: str,
    ) -> Subscription:
        """Create a new subscription by subscription type.

        Args:
            user_id: User UUID to create subscription for.
            subscription_type: Type of subscription (trial, monthly, quarterly, yearly).

        Returns:
            Created Subscription instance.
        """
        if subscription_type not in TARIFF_DURATION_DAYS:
            raise ValueError(f"Invalid subscription type: {subscription_type}")

        duration_days = TARIFF_DURATION_DAYS[subscription_type]
        end_date = datetime.now(MSK_TZ) + timedelta(days=duration_days)

        return await self.repository.create_subscription(
            user_id=user_id,
            product_id=None,
            end_date=end_date,
            start_date=datetime.now(MSK_TZ),
        )

    async def create_subscription_with_encrypted(
        self,
        user_id: uuid.UUID,
        subscription_type: str,
        encrypted_subscription: EncryptedSubscription,
    ) -> Subscription:
        """Create subscription with linked encrypted subscription.

        Args:
            user_id: User UUID to create subscription for.
            subscription_type: Type of subscription (trial, monthly, quarterly, yearly).
            encrypted_subscription: EncryptedSubscription to link.

        Returns:
            Created Subscription instance.
        """
        subscription = await self.create_subscription_by_type(
            user_id=user_id,
            subscription_type=subscription_type,
        )

        encrypted_subscription.subscription_id = subscription.id
        self.encrypted_repository.session.add(encrypted_subscription)
        await self.encrypted_repository.session.commit()
        await self.encrypted_repository.session.refresh(encrypted_subscription)

        return subscription

    async def create_subscription(
        self,
        user_id: uuid.UUID,
        subscription_type: str,
        duration_days: int | None = None,
    ) -> Subscription:
        """Create a new subscription for user.

        Args:
            user_id: User UUID to create subscription for.
            subscription_type: Subscription type (trial, monthly, quarterly, yearly).
            duration_days: Optional duration override.

        Returns:
            Created Subscription instance.
        """
        if duration_days is None:
            if subscription_type not in TARIFF_DURATION_DAYS:
                raise ValueError(f"Invalid subscription type: {subscription_type}")
            duration_days = TARIFF_DURATION_DAYS[subscription_type]

        end_date = datetime.now(MSK_TZ) + timedelta(days=duration_days)

        return await self.repository.create_subscription(
            user_id=user_id,
            product_id=None,
            end_date=end_date,
            start_date=datetime.now(MSK_TZ),
        )

    async def activate_trial(
        self,
        user_id: uuid.UUID,
    ) -> Subscription:
        """Activate trial subscription for user.

        Creates subscription with trial type (3 days).
        """
        return await self.create_subscription_by_type(
            user_id=user_id,
            subscription_type="trial",
        )

    def get_subscription_info(self, subscription: Subscription) -> dict:
        """Get subscription info for display.

        Args:
            subscription: Subscription instance.

        Returns:
            Dictionary with subscription info.
        """
        now = datetime.now(timezone.utc)
        time_left = subscription.end_date - now

        days_left = time_left.days
        hours_left = (time_left.seconds // 3600) % 24

        subscription_type = subscription.subscription_type or "unknown"

        encrypted_sub = getattr(subscription, "encrypted_subscription", None)
        max_devices = encrypted_sub.max_devices if encrypted_sub else 1

        return {
            "subscription_type": subscription_type,
            "end_date": subscription.end_date,
            "device_limit": max_devices,
            "is_active": subscription.is_active and subscription.end_date > now,
            "days_left": days_left,
            "hours_left": hours_left,
        }

    async def get_vpn_link(self, subscription: Subscription) -> str | None:
        """Get VPN link for subscription.

        Uses encrypted_subscription relationship if loaded, otherwise fetches from repository.

        Args:
            subscription: Subscription instance.

        Returns:
            Encrypted link string or None if not found.
        """
        encrypted_sub = getattr(subscription, "encrypted_subscription", None)

        if not encrypted_sub:
            encrypted_sub = await self.encrypted_repository.get_by_subscription_id(subscription.id)

        if encrypted_sub:
            return encrypted_sub.encrypted_link

        return None