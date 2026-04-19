"""Tests for Platega payment provider.

This module tests the PlategaProvider implementation including:
- Payment creation
- Status checking
- Webhook parsing and signature verification
- Status mapping
"""

import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.infrastructure.payments.base import PaymentProviderName
from src.infrastructure.payments.exceptions import (
    PaymentCreationError,
    PaymentProviderUnavailable,
    PaymentSignatureError,
    PaymentValidationError,
)
from src.infrastructure.payments.platega import PlategaCreatePaymentResult, PlategaProvider
from src.infrastructure.payments.schemas import PlategaPaymentMethod, PlategaStatus
from src.models.payment import PaymentStatus


class TestPlategaProviderInit:
    """Tests for PlategaProvider initialization."""

    def test_init_with_settings(self, mock_settings: MagicMock) -> None:
        """Test initialization with default settings."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            assert provider._api_key == "test_api_key"
            assert provider._merchant_id == "test_merchant_id"
            assert provider._webhook_secret == "test_webhook_secret"
            assert provider._api_url == "https://api.platega.io"
            assert provider._default_payment_method == PlategaPaymentMethod.SBP_QR

    def test_init_with_custom_params(self, mock_settings: MagicMock) -> None:
        """Test initialization with custom parameters."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider(
                api_key="custom_key",
                merchant_id="custom_merchant",
                webhook_secret="custom_secret",
                api_url="https://custom.api.url",
                default_payment_method=PlategaPaymentMethod.CARD_ACQUIRING,
            )

            assert provider._api_key == "custom_key"
            assert provider._merchant_id == "custom_merchant"
            assert provider._webhook_secret == "custom_secret"
            assert provider._api_url == "https://custom.api.url"
            assert provider._default_payment_method == PlategaPaymentMethod.CARD_ACQUIRING

    def test_name_property(self, mock_settings: MagicMock) -> None:
        """Test provider name property."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()
            assert provider.name == PaymentProviderName.PLATEGA


class TestPlategaProviderCreatePayment:
    """Tests for create_payment method."""

    @pytest.mark.asyncio
    async def test_create_payment_success(
        self,
        mock_settings: MagicMock,
        platega_create_response: dict,
    ) -> None:
        """Test successful payment creation."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            # Mock HTTP session and response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=platega_create_response)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.closed = False

            with patch.object(
                provider, "_get_session", return_value=mock_session
            ):
                # Mock __aenter__ and __aexit__ for context manager
                mock_session.post.return_value.__aenter__ = AsyncMock(
                    return_value=mock_response
                )
                mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await provider.create_payment(
                    amount=Decimal("1000.00"),
                    currency="RUB",
                    description="Test payment",
                    metadata={"order_id": "123"},
                )

            assert result.success is True
            assert result.payment_id == "550e8400-e29b-41d4-a716-446655440000"
            assert result.external_id == "550e8400-e29b-41d4-a716-446655440000"
            assert result.payment_url == "https://pay.platega.io/tx/550e8400-e29b-41d4-a716-446655440000"
            assert result.amount == Decimal("1000.00")
            assert result.currency == "RUB"
            assert result.transaction_id == "550e8400-e29b-41d4-a716-446655440000"

            await provider.close()

    @pytest.mark.asyncio
    async def test_create_payment_api_error(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Test payment creation with API error response."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            error_response = {
                "message": "Invalid payment method",
                "code": "INVALID_METHOD",
            }

            mock_response = MagicMock()
            mock_response.status = 400
            mock_response.json = AsyncMock(return_value=error_response)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.closed = False

            with patch.object(provider, "_get_session", return_value=mock_session):
                mock_session.post.return_value.__aenter__ = AsyncMock(
                    return_value=mock_response
                )
                mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await provider.create_payment(
                    amount=Decimal("1000.00"),
                    currency="RUB",
                    description="Test payment",
                )

            assert result.success is False
            assert result.error_message == "Invalid payment method"

            await provider.close()

    @pytest.mark.asyncio
    async def test_create_payment_connection_error(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Test payment creation with connection error."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            mock_session = AsyncMock()
            mock_session.post = MagicMock(
                side_effect=aiohttp.ClientError("Connection failed")
            )
            mock_session.closed = False

            with patch.object(provider, "_get_session", return_value=mock_session):
                with pytest.raises(PaymentProviderUnavailable) as exc_info:
                    await provider.create_payment(
                        amount=Decimal("1000.00"),
                        currency="RUB",
                        description="Test payment",
                    )

            assert "Platega API unavailable" in str(exc_info.value)

            await provider.close()

    @pytest.mark.asyncio
    async def test_create_payment_with_different_methods(
        self,
        mock_settings: MagicMock,
        platega_create_response: dict,
    ) -> None:
        """Test payment creation with different payment methods."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=platega_create_response)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.closed = False

            with patch.object(provider, "_get_session", return_value=mock_session):
                mock_session.post.return_value.__aenter__ = AsyncMock(
                    return_value=mock_response
                )
                mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

                # Test with CARD_ACQUIRING method
                result = await provider.create_payment(
                    amount=Decimal("500.00"),
                    currency="RUB",
                    description="Card payment",
                    payment_method=PlategaPaymentMethod.CARD_ACQUIRING,
                )

            assert result.success is True
            assert result.amount == Decimal("500.00")

            await provider.close()


class TestPlategaProviderGetStatus:
    """Tests for get_payment_status method."""

    @pytest.mark.asyncio
    async def test_get_status_pending(
        self,
        mock_settings: MagicMock,
        platega_status_response_pending: dict,
    ) -> None:
        """Test getting pending payment status."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value=platega_status_response_pending
            )

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.closed = False

            with patch.object(provider, "_get_session", return_value=mock_session):
                mock_session.get.return_value.__aenter__ = AsyncMock(
                    return_value=mock_response
                )
                mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await provider.get_payment_status(
                    "550e8400-e29b-41d4-a716-446655440000"
                )

            assert result.success is True
            assert result.status == PaymentStatus.PENDING
            assert result.amount == Decimal("1000.00")
            assert result.currency == "RUB"

            await provider.close()

    @pytest.mark.asyncio
    async def test_get_status_confirmed(
        self,
        mock_settings: MagicMock,
        platega_status_response_confirmed: dict,
    ) -> None:
        """Test getting confirmed payment status."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value=platega_status_response_confirmed
            )

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.closed = False

            with patch.object(provider, "_get_session", return_value=mock_session):
                mock_session.get.return_value.__aenter__ = AsyncMock(
                    return_value=mock_response
                )
                mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await provider.get_payment_status(
                    "550e8400-e29b-41d4-a716-446655440000"
                )

            assert result.success is True
            assert result.status == PaymentStatus.COMPLETED

            await provider.close()

    @pytest.mark.asyncio
    async def test_get_status_not_found(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Test getting status for non-existent payment."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            error_response = {
                "message": "Transaction not found",
                "code": "NOT_FOUND",
            }

            mock_response = MagicMock()
            mock_response.status = 404
            mock_response.json = AsyncMock(return_value=error_response)

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.closed = False

            with patch.object(provider, "_get_session", return_value=mock_session):
                mock_session.get.return_value.__aenter__ = AsyncMock(
                    return_value=mock_response
                )
                mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await provider.get_payment_status(
                    "non-existent-id"
                )

            assert result.success is False
            assert result.error_message == "Transaction not found"

            await provider.close()


class TestPlategaProviderWebhook:
    """Tests for webhook parsing and signature verification."""

    def test_verify_signature_valid(self, mock_settings: MagicMock) -> None:
        """Test valid signature verification."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            # Create test payload
            payload = json.dumps({"test": "data"})
            secret = "test_webhook_secret"

            # Generate valid signature
            expected_sig = hmac.new(
                secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Verify
            is_valid = provider._verify_signature(
                payload.encode("utf-8"),
                expected_sig,
            )

            assert is_valid is True

    def test_verify_signature_invalid(self, mock_settings: MagicMock) -> None:
        """Test invalid signature verification."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            payload = json.dumps({"test": "data"})
            invalid_sig = "invalid_signature_12345"

            is_valid = provider._verify_signature(
                payload.encode("utf-8"),
                invalid_sig,
            )

            assert is_valid is False

    def test_verify_signature_no_secret(self, mock_settings: MagicMock) -> None:
        """Test signature verification without configured secret."""
        mock_settings.platega_webhook_secret = ""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            payload = json.dumps({"test": "data"})

            # Should return True when no secret configured
            is_valid = provider._verify_signature(
                payload.encode("utf-8"),
                "any_signature",
            )

            assert is_valid is True

    def test_parse_webhook_valid(
        self,
        mock_settings: MagicMock,
        platega_webhook_payload: dict,
    ) -> None:
        """Test parsing valid webhook."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            # Create payload with valid signature
            raw_body = json.dumps(platega_webhook_payload).encode("utf-8")
            secret = "test_webhook_secret"

            signature = hmac.new(
                secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).hexdigest()

            headers = {"X-Signature": signature}

            result = provider.parse_webhook(raw_body, headers)

            assert result.payment_id == "550e8400-e29b-41d4-a716-446655440000"
            assert result.status == PaymentStatus.COMPLETED
            assert result.amount == Decimal("1000.00")
            assert result.currency == "RUB"

    def test_parse_webhook_invalid_signature(
        self,
        mock_settings: MagicMock,
        platega_webhook_payload: dict,
    ) -> None:
        """Test parsing webhook with invalid signature."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            raw_body = json.dumps(platega_webhook_payload).encode("utf-8")
            headers = {"X-Signature": "invalid_signature"}

            with pytest.raises(PaymentSignatureError):
                provider.parse_webhook(raw_body, headers)

    def test_parse_webhook_invalid_json(self, mock_settings: MagicMock) -> None:
        """Test parsing webhook with invalid JSON."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            # Create valid signature for invalid JSON
            raw_body = b"not valid json"
            secret = "test_webhook_secret"

            signature = hmac.new(
                secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).hexdigest()

            headers = {"X-Signature": signature}

            with pytest.raises(PaymentValidationError):
                provider.parse_webhook(raw_body, headers)

    def test_parse_webhook_missing_fields(self, mock_settings: MagicMock) -> None:
        """Test parsing webhook with missing required fields."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            # Payload without transactionId
            payload = {"status": "CONFIRMED"}
            raw_body = json.dumps(payload).encode("utf-8")
            secret = "test_webhook_secret"

            signature = hmac.new(
                secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).hexdigest()

            headers = {"X-Signature": signature}

            with pytest.raises(PaymentValidationError):
                provider.parse_webhook(raw_body, headers)


class TestPlategaStatusMapping:
    """Tests for status mapping functionality."""

    def test_map_platega_status_enum(self) -> None:
        """Test mapping PlategaStatus enum to PaymentStatus."""
        # Test all status mappings
        assert (
            PlategaProvider._map_platega_status(PlategaStatus.PENDING)
            == PaymentStatus.PENDING
        )
        assert (
            PlategaProvider._map_platega_status(PlategaStatus.CONFIRMED)
            == PaymentStatus.COMPLETED
        )
        assert (
            PlategaProvider._map_platega_status(PlategaStatus.CANCELED)
            == PaymentStatus.CANCELLED
        )
        assert (
            PlategaProvider._map_platega_status(PlategaStatus.CHARGEBACKED)
            == PaymentStatus.FAILED
        )

    def test_map_platega_status_string(self) -> None:
        """Test mapping status strings to PaymentStatus."""
        # Test uppercase
        assert PlategaProvider._map_platega_status_str("PENDING") == PaymentStatus.PENDING
        assert PlategaProvider._map_platega_status_str("CONFIRMED") == PaymentStatus.COMPLETED
        assert PlategaProvider._map_platega_status_str("CANCELED") == PaymentStatus.CANCELLED
        assert PlategaProvider._map_platega_status_str("CHARGEBACKED") == PaymentStatus.FAILED

        # Test lowercase
        assert PlategaProvider._map_platega_status_str("pending") == PaymentStatus.PENDING
        assert PlategaProvider._map_platega_status_str("confirmed") == PaymentStatus.COMPLETED
        assert PlategaProvider._map_platega_status_str("canceled") == PaymentStatus.CANCELLED

    def test_map_platega_status_unknown(self) -> None:
        """Test mapping unknown status defaults to PENDING."""
        assert PlategaProvider._map_platega_status_str("UNKNOWN") == PaymentStatus.PENDING
        assert PlategaProvider._map_platega_status_str("") == PaymentStatus.PENDING

    def test_public_map_status_method(self) -> None:
        """Test public map_status method."""
        assert PlategaProvider.map_status("CONFIRMED") == PaymentStatus.COMPLETED
        assert PlategaProvider.map_status("PENDING") == PaymentStatus.PENDING
        assert PlategaProvider.map_status("CANCELED") == PaymentStatus.CANCELLED


class TestPlategaProviderClose:
    """Tests for provider cleanup."""

    @pytest.mark.asyncio
    async def test_close_session(self, mock_settings: MagicMock) -> None:
        """Test closing HTTP session."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            # Create mock session
            mock_session = AsyncMock()
            mock_session.closed = False
            provider._session = mock_session

            await provider.close()

            mock_session.close.assert_called_once()
            assert provider._session is None

    @pytest.mark.asyncio
    async def test_close_no_session(self, mock_settings: MagicMock) -> None:
        """Test close when no session exists."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()
            provider._session = None

            # Should not raise any error
            await provider.close()

    @pytest.mark.asyncio
    async def test_close_already_closed_session(
        self, mock_settings: MagicMock
    ) -> None:
        """Test close when session is already closed."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            provider = PlategaProvider()

            mock_session = AsyncMock()
            mock_session.closed = True
            provider._session = mock_session

            await provider.close()

            # close() should not be called on already closed session
            mock_session.close.assert_not_called()