"""VPN Subscription Service for creating encrypted subscriptions via API.

Business logic for creating HAPP-compatible encrypted subscription links
through sub-oval.online API.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.infrastructure.database.repositories import EncryptedSubscriptionRepository
from src.infrastructure.vpn_subscription import (
    VpnSubscriptionApiError,
    VpnSubscriptionClient,
    VpnSubscriptionConnectionError,
)
from src.infrastructure.vpn_subscription.schemas import (
    CreateEncryptedSubscriptionRequest,
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

UTC = UTC


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
        tariff_type: str | None = None,
        subscription_id: uuid.UUID | None = None,
        max_devices: int | None = None,
        info_block_text: str | None = None,
        end_date: datetime | None = None,
    ) -> EncryptedSubscription:
        """Create encrypted subscription for a tariff type or specific end_date.

        Args:
            tariff_type: Subscription type (trial, monthly, quarterly, yearly).
                Used if end_date not provided.
            subscription_id: Linked subscription ID (optional for trial).
            max_devices: Override max devices limit.
            info_block_text: Override info block text.
            end_date: Specific end date. If provided, overrides tariff_type TTL.

        Returns:
            EncryptedSubscription model instance saved to database.

        Raises:
            VpnSubscriptionApiError: API error.
            VpnSubscriptionConnectionError: Cannot connect to API.
            ValueError: Invalid tariff type or neither tariff_type nor end_date provided.
        """
        # Calculate TTL from end_date or tariff_type
        if end_date:
            now = datetime.now(UTC)
            if end_date <= now:
                raise ValueError(f"end_date must be in the future: {end_date}")
            ttl_seconds = (end_date - now).total_seconds()
            ttl_hours = max(1, int(ttl_seconds / 3600))
            expires_at = end_date
        elif tariff_type:
            if tariff_type not in TARIFF_DURATION:
                raise ValueError(f"Invalid tariff type: {tariff_type}")
            duration = TARIFF_DURATION[tariff_type]
            ttl_hours = duration["hours"]
            expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)
        else:
            raise ValueError("Either tariff_type or end_date must be provided")

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
        end_date: datetime,
        tariff_type: str | None = None,
        max_devices: int | None = None,
    ) -> EncryptedSubscription:
        """Get existing encrypted subscription or create new one.

        Checks if existing VPN link matches subscription end_date. If not, creates new one.

        Args:
            subscription_id: Subscription UUID.
            end_date: Subscription end date from Subscription record.
            tariff_type: Subscription type (optional, for metadata defaults).
            max_devices: Override max devices limit.

        Returns:
            EncryptedSubscription (existing or newly created).
        """
        existing = await self.repository.get_by_subscription_id(subscription_id)

        # Check if existing VPN link matches subscription end_date (with 1 hour tolerance)
        now = datetime.now(UTC)
        if existing:
            time_diff = abs((existing.expires_at - end_date).total_seconds())
            # If VPN link expires at the same time as subscription and is still valid
            if time_diff <= 3600 and existing.expires_at > now:
                return existing

        # Create new VPN link with correct end_date
        return await self.create_subscription_for_tariff(
            tariff_type=tariff_type,
            subscription_id=subscription_id,
            max_devices=max_devices,
            end_date=end_date,
        )

    async def get_link_for_subscription(
        self,
        subscription_id: uuid.UUID,
        end_date: datetime,
        tariff_type: str | None = None,
    ) -> str:
        """Get encrypted link for subscription (lazy creation).

        Args:
            subscription_id: Subscription UUID.
            end_date: Subscription end date from Subscription record.
            tariff_type: Subscription type (optional, for metadata defaults).

        Returns:
            Encrypted subscription link for user.
        """
        encrypted_sub = await self.get_or_create_for_subscription(
            subscription_id=subscription_id,
            end_date=end_date,
            tariff_type=tariff_type,
        )

        return encrypted_sub.encrypted_link

    async def create_trial_subscription(
        self,
        user_id: uuid.UUID,
        subscription_id: uuid.UUID,
        end_date: datetime | None = None,
    ) -> EncryptedSubscription:
        """Create trial encrypted subscription linked to a Subscription record.

        Args:
            user_id: User UUID (for logging purposes).
            subscription_id: Linked Subscription ID.
            end_date: Subscription end date. If not provided, uses default trial TTL (72 hours).

        Returns:
            EncryptedSubscription for trial.
        """
        return await self.create_subscription_for_tariff(
            tariff_type="trial" if not end_date else None,
            subscription_id=subscription_id,
            max_devices=1,
            info_block_text="Для продления подписки обратитесь в поддержку",
            end_date=end_date,
        )

    async def refresh_subscription_link(
        self,
        subscription_id: uuid.UUID,
        end_date: datetime,
        tariff_type: str | None = None,
    ) -> EncryptedSubscription:
        """Refresh encrypted subscription link.

        Creates a new encrypted subscription via API for existing subscription.
        Useful when link is corrupted or needs update.

        Args:
            subscription_id: Subscription UUID.
            end_date: Subscription end date from Subscription record.
            tariff_type: Subscription type (optional, for metadata defaults).

        Returns:
            New EncryptedSubscription (old one remains in history).
        """
        return await self.create_subscription_for_tariff(
            tariff_type=tariff_type,
            subscription_id=subscription_id,
            end_date=end_date,
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
