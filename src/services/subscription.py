"""Subscription service for business logic."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.repositories import SubscriptionRepository
from src.models.subscription import Subscription
from src.models.product import Product, SubscriptionType
from src.infrastructure.database.repositories import ProductRepository


class SubscriptionService:
    """Service for subscription-related business logic."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize subscription service."""
        self.repository = SubscriptionRepository(session)
        self.product_repository = ProductRepository(session)

    async def get_active_subscription(self, user_id: uuid.UUID) -> Subscription | None:
        """Get active subscription for user by user ID (UUID)."""
        return await self.repository.get_active_subscription(user_id)

    async def create_subscription_from_product(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Subscription:
        """Create a new subscription from a product.

        Args:
            user_id: User UUID to create subscription for.
            product_id: Product UUID to base subscription on.
        """
        product = await self.product_repository.get_product_by_id(product_id)
        if not product:
            raise ValueError(f"Product with ID {product_id} not found")

        end_date = datetime.utcnow() + timedelta(days=product.duration_days)

        return await self.repository.create_subscription(
            user_id=user_id,
            product_id=product_id,
            end_date=end_date,
            start_date=datetime.utcnow(),
        )

    async def create_subscription_by_type(
        self,
        user_id: uuid.UUID,
        subscription_type: str,
    ) -> Subscription:
        """Create a new subscription by subscription type.

        Args:
            user_id: User UUID to create subscription for.
            subscription_type: Type of subscription (trial, monthly, quarterly, yearly).
        """
        # Find the corresponding product
        product = await self.product_repository.get_product_by_subscription_type(subscription_type)
        if not product:
            raise ValueError(f"No product found for subscription type: {subscription_type}")

        end_date = datetime.utcnow() + timedelta(days=product.duration_days)

        return await self.repository.create_subscription(
            user_id=user_id,
            product_id=product.id,
            end_date=end_date,
            start_date=datetime.utcnow(),
        )

    async def activate_trial(
        self,
        user_id: uuid.UUID,
    ) -> Subscription:
        """Activate trial subscription for user."""
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
        now = datetime.utcnow()
        time_left = subscription.end_date - now

        days_left = time_left.days
        hours_left = (time_left.seconds // 3600) % 24

        # Get product information
        product = getattr(subscription, "product", None)
        subscription_type = product.subscription_type.value if product else "unknown"
        device_limit = product.device_limit if product else 1

        return {
            "subscription_type": subscription_type,
            "end_date": subscription.end_date,
            "device_limit": device_limit,
            "is_active": subscription.is_active and subscription.end_date > now,
            "days_left": days_left,
            "hours_left": hours_left,
        }
