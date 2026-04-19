"""Factory for creating payment providers.

This module provides a factory pattern for instantiating payment
providers, allowing easy switching and registration of new providers.
"""

import logging
from typing import Type

from src.infrastructure.payments.base import PaymentProvider
from src.infrastructure.payments.platega import PlategaProvider

logger = logging.getLogger(__name__)


class PaymentProviderFactory:
    """Factory for creating payment provider instances.

    This factory manages registration and creation of payment providers,
    enabling easy switching between different payment systems.

    Example:
        >>> # Create default provider
        >>> provider = PaymentProviderFactory.create("platega")
        >>> 
        >>> # Register custom provider
        >>> PaymentProviderFactory.register("my_provider", MyProvider)
        >>> provider = PaymentProviderFactory.create("my_provider")

    The factory uses a registry pattern where providers are registered
    by name and can be instantiated on demand.
    """

    # Registry of available providers
    _providers: dict[str, type[PaymentProvider]] = {
        "platega": PlategaProvider,
        # Future providers can be added here:
        # "yookassa": YooKassaProvider,
        # "stripe": StripeProvider,
        # "crypto": CryptoProvider,
    }

    # Cache of instantiated providers (singleton pattern)
    _instances: dict[str, PaymentProvider] = {}

    @classmethod
    def create(cls, provider_name: str) -> PaymentProvider:
        """Create or get a payment provider instance.

        This method returns a cached instance if one exists,
        otherwise creates a new one and caches it.

        Args:
            provider_name: Name of the provider (e.g., 'platega').

        Returns:
            PaymentProvider instance.

        Raises:
            ValueError: If provider name is not registered.

        Example:
            >>> provider = PaymentProviderFactory.create("platega")
            >>> await provider.create_payment(amount=Decimal("100"))
        """
        # Check if provider is registered
        if provider_name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(
                f"Unknown payment provider: '{provider_name}'. "
                f"Available providers: {available}"
            )

        # Return cached instance if available
        if provider_name in cls._instances:
            return cls._instances[provider_name]

        # Create new instance
        provider_class = cls._providers[provider_name]
        instance = provider_class()

        # Cache the instance
        cls._instances[provider_name] = instance

        logger.info(
            f"Created payment provider: {provider_name}",
            extra={"provider": provider_name},
        )

        return instance

    @classmethod
    def register(
        cls,
        name: str,
        provider_class: type[PaymentProvider],
    ) -> None:
        """Register a new payment provider.

        This method allows dynamic registration of providers,
        useful for plugins or custom implementations.

        Args:
            name: Provider identifier (used in create()).
            provider_class: Provider class (must inherit PaymentProvider).

        Raises:
            TypeError: If class doesn't inherit PaymentProvider.

        Example:
            >>> class MyProvider(PaymentProvider):
            ...     # Implementation
            ...     pass
            >>> 
            >>> PaymentProviderFactory.register("my_provider", MyProvider)
        """
        # Validate that class is a PaymentProvider
        if not isinstance(provider_class, type) or not issubclass(
            provider_class, PaymentProvider
        ):
            raise TypeError(
                f"Provider class must inherit from PaymentProvider, "
                f"got: {provider_class}"
            )

        # Register the provider
        cls._providers[name] = provider_class

        logger.info(
            f"Registered payment provider: {name}",
            extra={"provider": name, "class": provider_class.__name__},
        )

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of registered provider names.

        Returns:
            List of available provider identifiers.

        Example:
            >>> providers = PaymentProviderFactory.get_available_providers()
            >>> print(providers)  # ['platega']
        """
        return list(cls._providers.keys())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached provider instances (non-async version).

        This method removes all cached instances without properly
        closing HTTP sessions. Use async_clear_cache() for proper cleanup.

        Example:
            >>> PaymentProviderFactory.clear_cache()
            >>> # Next create() will instantiate fresh provider
        """
        cls._instances.clear()
        logger.info("Cleared all cached provider instances (non-async)")

    @classmethod
    async def async_clear_cache(cls) -> None:
        """Clear cached provider instances with proper async cleanup.

        This method properly closes all provider HTTP sessions before
        clearing the cache. Use this during application shutdown.

        Example:
            >>> await PaymentProviderFactory.async_clear_cache()
            >>> # All HTTP sessions properly closed
        """
        for name, instance in cls._instances.items():
            try:
                if hasattr(instance, "close"):
                    await instance.close()
                    logger.debug(f"Provider {name} closed successfully")
            except Exception as e:
                logger.warning(f"Error closing provider {name}: {e}")

        cls._instances.clear()
        logger.info("Cleared all cached provider instances with async cleanup")

    @classmethod
    def is_registered(cls, provider_name: str) -> bool:
        """Check if a provider is registered.

        Args:
            provider_name: Name to check.

        Returns:
            True if provider is registered, False otherwise.

        Example:
            >>> if PaymentProviderFactory.is_registered("platega"):
            ...     provider = PaymentProviderFactory.create("platega")
        """
        return provider_name in cls._providers