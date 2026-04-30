"""VPN Subscription Service for creating encrypted subscriptions via API.

Business logic for creating HAPP-compatible encrypted subscription links
through sub-oval.online API.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.infrastructure.database.repositories import EncryptedSubscriptionRepository
from src.infrastructure.vpn_subscription import (
    VpnSubscriptionClient,
    VpnSubscriptionApiError,
    VpnSubscriptionConnectionError,
)
from src.infrastructure.vpn_subscription.schemas import (
    CreateEncryptedSubscriptionRequest,
    EncryptedSubscriptionResponse,
    ExpireNotificationRequest,
    InfoBlockRequest,
    SubscriptionBehaviorRequest,
    SubscriptionMetadataRequest,
    TrafficInfoRequest,
    VpnTag,
)
from src.models.encrypted_subscription import EncryptedSubscription

# Mapping tariff type to duration in days and hours
TARIFF_DURATION = {
    "trial": {"days": 3, "hours": 72},
    "monthly": {"days": 30, "hours": 720},
    "quarterly": {"days": 90, "hours": 2160},
    "yearly": {"days": 365, "hours": 8760},
}

UTC = timezone.utc


class VpnSubscriptionService:
    """Service for VPN subscription operations.

    Creates and manages encrypted subscription links via sub-oval.online API.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session."""
        self.session = session
        self.repository = EncryptedSubscriptionRepository(session)
        self._client: VpnSubscriptionClient | None = None

    def _get_client(self) -> VpnSubscriptionClient:
        """Get or create VPN Subscription API client."""
        if self._client is None:
            self._client = VpnSubscriptionClient()
        return self._client

    async def close_client(self) -> None:
        """Close VPN Subscription API client."""
        if self._client:
            await self._client.close()
            self._client = None

    def _build_metadata(
        self,
        profile_title: str | None = None,
        info_block_text: str | None = None,
        info_block_color: str | None = None,
    ) -> SubscriptionMetadataRequest:
        """Build subscription metadata from settings.

        Uses BOT_NAME, SUPPORT_LINK, BOT_LINK from settings.

        Args:
            profile_title: Override profile title (default: BOT_NAME)
            info_block_text: Override info block text
            info_block_color: Override info block color (red/blue/green)

        Returns:
            SubscriptionMetadataRequest for API.
        """
        return SubscriptionMetadataRequest(
            profile_title=profile_title or settings.bot_name,
            profile_update_interval=1,
            support_url=settings.support_link,
            profile_web_page_url=settings.bot_link,
            announce=settings.default_announce_text,
            traffic_info=TrafficInfoRequest(
                upload=0,
                download=0,
                total=0,
            ),
            info_block=InfoBlockRequest(
                color=info_block_color or settings.default_info_block_color,
                text=info_block_text or settings.default_info_block_text,
                button_text="Поддержка",
                button_link=settings.support_link,
            ),
            expire_notification=ExpireNotificationRequest(
                enabled=True,
                button_link=settings.bot_link,
            ),
        )

    def _build_behavior(
        self,
        fallback_url_template: str = "https://sub-oval.online/api/v1/subscriptions/{public_id}",
        public_id: str | None = None,
    ) -> SubscriptionBehaviorRequest:
        """Build subscription behavior settings.

        Args:
            fallback_url_template: Fallback URL template with {public_id} placeholder
            public_id: Public ID to use in fallback URL (optional, will be set after creation)

        Returns:
            SubscriptionBehaviorRequest for API.
        """
        fallback_url = None
        if public_id:
            fallback_url = fallback_url_template.format(public_id=public_id)

        return SubscriptionBehaviorRequest(
            autoconnect=True,
            autoconnect_type="lowestdelay",
            ping_on_open=True,
            fallback_url=fallback_url,
        )

    async def create_subscription_for_tariff(
        self,
        tariff_type: str,
        subscription_id: uuid.UUID | None = None,
        max_devices: int | None = None,
        info_block_text: str | None = None,
    ) -> EncryptedSubscription:
        """Create encrypted subscription for a tariff type.

        Args:
            tariff_type: Subscription type (trial, monthly, quarterly, yearly).
            subscription_id: Linked subscription ID (optional for trial).
            max_devices: Override max devices limit.
            info_block_text: Override info block text.

        Returns:
            EncryptedSubscription model instance saved to database.

        Raises:
            VpnSubscriptionApiError: API error.
            VpnSubscriptionConnectionError: Cannot connect to API.
            ValueError: Invalid tariff type.
        """
        if tariff_type not in TARIFF_DURATION:
            raise ValueError(f"Invalid tariff type: {tariff_type}")

        duration = TARIFF_DURATION[tariff_type]
        ttl_hours = duration["hours"]
        max_devices = max_devices or settings.default_max_devices

        client = self._get_client()

        # Build request
        request = CreateEncryptedSubscriptionRequest(
            tags=[VpnTag.MAIN.value],
            ttl_hours=ttl_hours,
            max_devices=max_devices,
            metadata=self._build_metadata(info_block_text=info_block_text),
            behavior=self._build_behavior(),
            provider_id=None,
        )

        try:
            response = await client.create_encrypted_subscription(request)
        except (VpnSubscriptionApiError, VpnSubscriptionConnectionError) as e:
            raise e

        # Calculate expires_at from ttl_hours
        expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)

        # Save to database
        encrypted_sub = await self.repository.create({
            "id": uuid.UUID(response.id),
            "subscription_id": subscription_id,
            "public_id": response.public_id,
            "encrypted_link": response.encrypted_link,
            "vpn_sources_count": response.vpn_sources_count,
            "tags_used": response.tags_used,
            "expires_at": expires_at,
            "metadata_json": request.metadata.model_dump() if request.metadata else None,
            "behavior_json": request.behavior.model_dump() if request.behavior else None,
            "ttl_hours": ttl_hours,
            "max_devices": max_devices,
        })

        return encrypted_sub

    async def get_or_create_for_subscription(
        self,
        subscription_id: uuid.UUID,
        tariff_type: str,
        max_devices: int | None = None,
    ) -> EncryptedSubscription:
        """Get existing encrypted subscription or create new one.

        Lazy migration: if no encrypted subscription exists for the subscription,
        create one via API.

        Args:
            subscription_id: Subscription UUID.
            tariff_type: Subscription type for TTL calculation.
            max_devices: Override max devices limit.

        Returns:
            EncryptedSubscription (existing or newly created).
        """
        existing = await self.repository.get_by_subscription_id(subscription_id)

        if existing and existing.expires_at > datetime.now(UTC):
            return existing

        return await self.create_subscription_for_tariff(
            tariff_type=tariff_type,
            subscription_id=subscription_id,
            max_devices=max_devices,
        )

    async def get_link_for_subscription(
        self,
        subscription_id: uuid.UUID,
        tariff_type: str,
    ) -> str:
        """Get encrypted link for subscription (lazy creation).

        Args:
            subscription_id: Subscription UUID.
            tariff_type: Subscription type for TTL calculation.

        Returns:
            Encrypted subscription link for user.
        """
        encrypted_sub = await self.get_or_create_for_subscription(
            subscription_id=subscription_id,
            tariff_type=tariff_type,
        )

        return encrypted_sub.encrypted_link

    async def create_trial_subscription(
        self,
        user_id: uuid.UUID,
    ) -> EncryptedSubscription:
        """Create trial encrypted subscription (no linked Subscription record).

        Trial is a standalone encrypted subscription with 72 hours TTL.

        Args:
            user_id: User UUID (for logging purposes, not linked).

        Returns:
            EncryptedSubscription for trial.
        """
        return await self.create_subscription_for_tariff(
            tariff_type="trial",
            subscription_id=None,
            max_devices=1,
            info_block_text="Для продления подписки обратитесь в поддержку",
        )

    async def refresh_subscription_link(
        self,
        subscription_id: uuid.UUID,
        tariff_type: str,
    ) -> EncryptedSubscription:
        """Refresh encrypted subscription link.

        Creates a new encrypted subscription via API for existing subscription.
        Useful when link is corrupted or needs update.

        Args:
            subscription_id: Subscription UUID.
            tariff_type: Subscription type for TTL calculation.

        Returns:
            New EncryptedSubscription (old one remains in history).
        """
        return await self.create_subscription_for_tariff(
            tariff_type=tariff_type,
            subscription_id=subscription_id,
        )

    async def cleanup_expired(self, older_than_days: int = 30) -> int:
        """Cleanup expired standalone encrypted subscriptions.

        Args:
            older_than_days: Delete subscriptions expired more than this days ago.

        Returns:
            Count of deleted subscriptions.
        """
        return await self.repository.delete_expired(older_than_days)

    async def __aenter__(self) -> "VpnSubscriptionService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - close client."""
        await self.close_client()