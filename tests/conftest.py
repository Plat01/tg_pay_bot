"""Pytest configuration and shared fixtures.

This module contains shared fixtures and configuration for all tests.
"""

import asyncio
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.payment import PaymentStatus
from src.models.user import User


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing.

    Returns:
        MagicMock with Platega settings configured.
    """
    settings = MagicMock()
    settings.platega_secret = "test_api_key"
    settings.platega_merchant_id = "test_merchant_id"
    settings.platega_webhook_secret = "test_webhook_secret"
    settings.platega_api_url = "https://api.platega.io"
    settings.platega_webhook_url = "https://example.com/webhook/platega"
    settings.default_payment_provider = "platega"
    return settings


@pytest.fixture
def sample_user() -> User:
    """Create sample user for testing.

    Returns:
        User instance with test data.
    """
    return User(
        id=1,
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        last_name="User",
        referral_code="TESTCODE",
        balance=Decimal("100.00"),
    )


@pytest.fixture
def platega_create_response() -> dict:
    """Sample Platega create transaction response.

    Returns:
        Dict with sample response data.
    """
    return {
        "paymentMethod": "SBP_QR",
        "transactionId": "550e8400-e29b-41d4-a716-446655440000",
        "redirect": "https://pay.platega.io/tx/550e8400-e29b-41d4-a716-446655440000",
        "return": "https://example.com/success",
        "paymentDetails": {"amount": 1000.00, "currency": "RUB"},
        "status": "PENDING",
        "expiresIn": "01:00:00",
        "merchantId": "550e8400-e29b-41d4-a716-446655440001",
        "qr": "https://qr.example.com/550e8400",
    }


@pytest.fixture
def platega_status_response_pending() -> dict:
    """Sample Platega status response (pending).

    Returns:
        Dict with sample pending status response.
    """
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "PENDING",
        "paymentDetails": {"amount": 1000.00, "currency": "RUB"},
        "merchantName": "Test Merchant",
        "merchantId": "550e8400-e29b-41d4-a716-446655440001",
        "paymentMethod": "SBP_QR",
        "expiresIn": "00:45:00",
        "qr": "https://qr.example.com/550e8400",
        "description": "Account top-up",
    }


@pytest.fixture
def platega_status_response_confirmed() -> dict:
    """Sample Platega status response (confirmed).

    Returns:
        Dict with sample confirmed status response.
    """
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "CONFIRMED",
        "paymentDetails": {"amount": 1000.00, "currency": "RUB"},
        "merchantName": "Test Merchant",
        "merchantId": "550e8400-e29b-41d4-a716-446655440001",
        "paymentMethod": "SBP_QR",
        "description": "Account top-up",
    }


@pytest.fixture
def platega_webhook_payload() -> dict:
    """Sample Platega webhook payload.

    Returns:
        Dict with sample webhook data.
    """
    return {
        "transactionId": "550e8400-e29b-41d4-a716-446655440000",
        "status": "CONFIRMED",
        "paymentDetails": {"amount": 1000.00, "currency": "RUB"},
        "payload": "order_123",
    }


@pytest.fixture
def mock_aiohttp_session() -> AsyncMock:
    """Create mock aiohttp session.

    Returns:
        AsyncMock configured as aiohttp.ClientSession.
    """
    session = AsyncMock()
    session.closed = False
    return session


@pytest.fixture
def mock_response() -> MagicMock:
    """Create mock HTTP response.

    Returns:
        MagicMock configured as aiohttp response.
    """
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock()
    return response