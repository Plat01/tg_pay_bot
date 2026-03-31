"""Tests for payment provider factory.

This module tests the PaymentProviderFactory including:
- Provider creation
- Provider registration
- Cache management
"""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.payments.base import PaymentProvider, PaymentProviderName
from src.infrastructure.payments.factory import PaymentProviderFactory
from src.infrastructure.payments.platega import PlategaProvider


class MockProvider(PaymentProvider):
    """Mock provider for testing registration."""

    @property
    def name(self) -> str:
        return "mock_provider"

    async def create_payment(
        self, amount, currency, description, metadata=None, **kwargs
    ):
        pass

    async def get_payment_status(self, external_id):
        pass

    def map_status(self, external_status):
        pass

    async def close(self):
        pass


class TestPaymentProviderFactory:
    """Tests for PaymentProviderFactory."""

    def test_create_platega_provider(self, mock_settings: MagicMock) -> None:
        """Test creating Platega provider."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            # Clear cache first
            PaymentProviderFactory.clear_cache()

            provider = PaymentProviderFactory.create("platega")

            assert isinstance(provider, PlategaProvider)
            assert provider.name == PaymentProviderName.PLATEGA

    def test_create_returns_cached_instance(self, mock_settings: MagicMock) -> None:
        """Test that create returns cached instance."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            PaymentProviderFactory.clear_cache()

            provider1 = PaymentProviderFactory.create("platega")
            provider2 = PaymentProviderFactory.create("platega")

            # Should return the same instance
            assert provider1 is provider2

    def test_create_unknown_provider(self) -> None:
        """Test creating unknown provider raises error."""
        PaymentProviderFactory.clear_cache()

        with pytest.raises(ValueError) as exc_info:
            PaymentProviderFactory.create("unknown_provider")

        assert "Unknown payment provider" in str(exc_info.value)
        assert "unknown_provider" in str(exc_info.value)

    def test_register_new_provider(self) -> None:
        """Test registering new provider."""
        PaymentProviderFactory.clear_cache()

        # Register mock provider
        PaymentProviderFactory.register("mock", MockProvider)

        # Check it's registered
        assert "mock" in PaymentProviderFactory.get_available_providers()
        assert PaymentProviderFactory.is_registered("mock")

    def test_register_invalid_provider(self) -> None:
        """Test registering invalid provider class raises error."""
        with pytest.raises(TypeError) as exc_info:
            PaymentProviderFactory.register("invalid", str)  # str doesn't inherit PaymentProvider

        assert "must inherit from PaymentProvider" in str(exc_info.value)

    def test_get_available_providers(self) -> None:
        """Test getting list of available providers."""
        providers = PaymentProviderFactory.get_available_providers()

        assert "platega" in providers
        assert isinstance(providers, list)

    def test_is_registered(self) -> None:
        """Test checking if provider is registered."""
        assert PaymentProviderFactory.is_registered("platega") is True
        assert PaymentProviderFactory.is_registered("unknown") is False

    def test_clear_cache(self, mock_settings: MagicMock) -> None:
        """Test clearing provider cache."""
        with patch("src.infrastructure.payments.platega.settings", mock_settings):
            # Create provider (adds to cache)
            provider1 = PaymentProviderFactory.create("platega")

            # Clear cache
            PaymentProviderFactory.clear_cache()

            # Create again (should be new instance)
            provider2 = PaymentProviderFactory.create("platega")

            # Should be different instances
            assert provider1 is not provider2

    def test_register_after_clear_cache(self) -> None:
        """Test that registered providers persist after cache clear."""
        PaymentProviderFactory.clear_cache()

        # Register mock provider
        PaymentProviderFactory.register("mock2", MockProvider)

        # Clear cache (should not remove registration)
        PaymentProviderFactory.clear_cache()

        # Provider should still be registered
        assert PaymentProviderFactory.is_registered("mock2")