"""Tests for VPN Subscription Service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.vpn_subscription.schemas import (
    CreateEncryptedSubscriptionRequest,
    EncryptedSubscriptionResponse,
)
from src.services.vpn_subscription import VpnSubscriptionService, TARIFF_DURATION


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_repository():
    """Create mock EncryptedSubscriptionRepository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_api_response():
    """Create mock API response."""
    return EncryptedSubscriptionResponse(
        id=str(uuid.uuid4()),
        public_id="test_public_id_123",
        encrypted_link="https://sub-oval.online/api/v1/subscriptions/test_public_id_123",
        expires_at=datetime.now(timezone.utc).isoformat(),
        vpn_sources_count=5,
        tags_used=["main"],
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.mark.asyncio
async def test_tariff_duration_mapping():
    """Test tariff duration mapping."""
    assert TARIFF_DURATION["trial"]["hours"] == 72
    assert TARIFF_DURATION["monthly"]["hours"] == 720
    assert TARIFF_DURATION["quarterly"]["hours"] == 2160
    assert TARIFF_DURATION["yearly"]["hours"] == 8760


@pytest.mark.asyncio
async def test_build_metadata(mock_session):
    """Test metadata building from settings."""
    with patch("src.services.vpn_subscription.settings") as mock_settings:
        mock_settings.bot_name = "TestBot"
        mock_settings.support_link = "https://t.me/support"
        mock_settings.bot_link = "https://t.me/testbot"
        mock_settings.default_announce_text = "Test announce"
        mock_settings.default_info_block_text = "Test info"
        mock_settings.default_info_block_color = "blue"

        service = VpnSubscriptionService(mock_session)
        metadata = service._build_metadata()

        assert metadata.profile_title == "TestBot"
        assert metadata.support_url == "https://t.me/support"
        assert metadata.profile_web_page_url == "https://t.me/testbot"
        assert metadata.announce == "Test announce"
        assert metadata.info_block.color == "blue"
        assert metadata.info_block.text == "Test info"


@pytest.mark.asyncio
async def test_build_behavior(mock_session):
    """Test behavior building."""
    service = VpnSubscriptionService(mock_session)

    behavior = service._build_behavior()
    assert behavior.autoconnect == True
    assert behavior.autoconnect_type == "lowestdelay"
    assert behavior.ping_on_open == True
    assert behavior.fallback_url is None

    behavior_with_fallback = service._build_behavior(public_id="test123")
    assert behavior_with_fallback.fallback_url == "https://sub-oval.online/api/v1/subscriptions/test123"


@pytest.mark.asyncio
async def test_create_subscription_for_tariff_invalid_type(mock_session):
    """Test error for invalid tariff type."""
    service = VpnSubscriptionService(mock_session)

    with pytest.raises(ValueError) as exc_info:
        await service.create_subscription_for_tariff("invalid_type")

    assert "Invalid tariff type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_or_create_for_subscription_existing(mock_session, mock_repository):
    """Test get_or_create returns existing subscription."""
    existing_sub = MagicMock()
    existing_sub.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    mock_repository.get_by_subscription_id = AsyncMock(return_value=existing_sub)

    service = VpnSubscriptionService(mock_session)
    service.repository = mock_repository

    result = await service.get_or_create_for_subscription(
        subscription_id=uuid.uuid4(),
        tariff_type="monthly",
    )

    assert result == existing_sub
    mock_repository.get_by_subscription_id.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_for_subscription_expired(mock_session, mock_repository, mock_api_response):
    """Test get_or_create creates new when existing expired."""
    subscription_id = uuid.uuid4()
    expired_sub = MagicMock()
    expired_sub.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    new_sub = MagicMock()
    new_sub.encrypted_link = "https://new.link"

    with patch("src.services.vpn_subscription.VpnSubscriptionClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.create_encrypted_subscription = AsyncMock(return_value=mock_api_response)
        mock_client_class.return_value = mock_client

        mock_repository.get_by_subscription_id = AsyncMock(return_value=expired_sub)
        mock_repository.create = AsyncMock(return_value=new_sub)

        service = VpnSubscriptionService(mock_session)
        service.repository = mock_repository

        result = await service.get_or_create_for_subscription(
            subscription_id=subscription_id,
            tariff_type="monthly",
        )

        assert result == new_sub
        mock_client.create_encrypted_subscription.assert_called_once()


@pytest.mark.asyncio
async def test_create_trial_subscription(mock_session, mock_repository, mock_api_response):
    """Test trial subscription creation."""
    new_sub = MagicMock()
    new_sub.ttl_hours = 72

    with patch("src.services.vpn_subscription.VpnSubscriptionClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.create_encrypted_subscription = AsyncMock(return_value=mock_api_response)
        mock_client_class.return_value = mock_client

        mock_repository.create = AsyncMock(return_value=new_sub)

        service = VpnSubscriptionService(mock_session)
        service.repository = mock_repository

        result = await service.create_trial_subscription(user_id=uuid.uuid4())

        assert result == new_sub

        call_args = mock_client.create_encrypted_subscription.call_args
        request = call_args[0][0]
        assert request.ttl_hours == 72
        assert request.tags == ["main"]