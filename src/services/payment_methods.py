"""Service that keeps the list of currently available payment methods.

On bot start every provider registered in ``PaymentProviderFactory`` is asked
whether it is configured and reachable. Only the methods of available
providers are shown in the keyboards, so a disabled or broken payment system
never produces a dead button.

Adding a new provider requires no changes here: it is enough to register it in
the factory and implement ``get_payment_methods()`` (plus optionally
``is_configured()`` / ``check_availability()``) in the provider class.
"""

import asyncio
import logging

from src.infrastructure.payments import PaymentMethodInfo, PaymentProviderFactory

logger = logging.getLogger(__name__)


class PaymentMethodsService:
    """In-memory cache of payment methods available right now.

    The cache is filled once on bot start (``initialize_cache``) and can be
    rebuilt at any time (``refresh_cache``), for example after changing
    provider credentials.

    Example:
        >>> await PaymentMethodsService.initialize_cache()
        >>> for method in PaymentMethodsService.get_available_methods():
        ...     print(method.provider, method.code, method.label)
    """

    # Available methods of all providers, sorted by button order
    _methods: list[PaymentMethodInfo] = []
    # Names of providers that passed the availability check
    _available_providers: list[str] = []
    # Whether the cache has been filled at least once
    _initialized: bool = False
    # Guards against parallel refreshes
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def initialize_cache(cls) -> list[PaymentMethodInfo]:
        """Fill the cache on bot start.

        Returns:
            List of available payment methods.
        """
        return await cls.refresh_cache()

    @classmethod
    async def refresh_cache(cls) -> list[PaymentMethodInfo]:
        """Re-check all registered providers and rebuild the cache.

        Providers are checked concurrently, an error in one of them does not
        affect the others.

        Returns:
            List of available payment methods.
        """
        async with cls._lock:
            provider_names = PaymentProviderFactory.get_available_providers()

            results = await asyncio.gather(
                *(cls._check_provider(name) for name in provider_names)
            )

            methods: list[PaymentMethodInfo] = []
            available_providers: list[str] = []

            for provider_name, provider_methods in results:
                if not provider_methods:
                    continue
                available_providers.append(provider_name)
                methods.extend(provider_methods)

            # Stable order of buttons regardless of the check order
            methods.sort(key=lambda item: (item.order, item.provider, item.code))

            cls._methods = methods
            cls._available_providers = available_providers
            cls._initialized = True

            if methods:
                logger.info(
                    "Available payment methods: "
                    + ", ".join(f"{item.provider}:{item.code} ({item.label})" for item in methods)
                )
            else:
                logger.error(
                    "No payment methods available: all payment providers are "
                    "unconfigured or unreachable"
                )

            return list(cls._methods)

    @classmethod
    async def _check_provider(
        cls,
        provider_name: str,
    ) -> tuple[str, list[PaymentMethodInfo]]:
        """Check a single provider and get its payment methods.

        Args:
            provider_name: Name of the provider registered in the factory.

        Returns:
            Tuple of (provider name, its available methods; empty list if the
            provider cannot be used).
        """
        try:
            provider = PaymentProviderFactory.create(provider_name)

            if not provider.is_configured():
                logger.warning(f"Payment provider '{provider_name}' is not configured, skipping")
                return provider_name, []

            if not await provider.check_availability():
                logger.warning(f"Payment provider '{provider_name}' is unavailable, skipping")
                return provider_name, []

            methods = provider.get_payment_methods()
            if not methods:
                logger.warning(
                    f"Payment provider '{provider_name}' has no enabled payment methods, skipping"
                )
                return provider_name, []

            return provider_name, methods

        except Exception as e:
            logger.error(f"Failed to check payment provider '{provider_name}': {e}")
            return provider_name, []

    @classmethod
    def get_available_methods(cls) -> list[PaymentMethodInfo]:
        """Get payment methods available right now.

        If the cache has not been initialized yet (e.g. a handler fired before
        startup finished), methods of configured providers are returned
        without a network check.

        Returns:
            List of PaymentMethodInfo.
        """
        if not cls._initialized:
            logger.warning(
                "Payment methods cache is not initialized, falling back to configured providers"
            )
            return cls._get_configured_methods()

        return list(cls._methods)

    @classmethod
    def _get_configured_methods(cls) -> list[PaymentMethodInfo]:
        """Get methods of configured providers without checking availability.

        Returns:
            List of PaymentMethodInfo sorted by button order.
        """
        methods: list[PaymentMethodInfo] = []

        for provider_name in PaymentProviderFactory.get_available_providers():
            try:
                provider = PaymentProviderFactory.create(provider_name)
                if provider.is_configured():
                    methods.extend(provider.get_payment_methods())
            except Exception as e:
                logger.error(f"Failed to get methods of payment provider '{provider_name}': {e}")

        methods.sort(key=lambda item: (item.order, item.provider, item.code))
        return methods

    @classmethod
    def get_method(cls, provider: str, code: str) -> PaymentMethodInfo | None:
        """Find an available payment method by provider name and code.

        Args:
            provider: Provider name from the callback data.
            code: Provider-specific method code from the callback data.

        Returns:
            PaymentMethodInfo or None if the method is not available.
        """
        for method in cls.get_available_methods():
            if method.provider == provider and method.code == code:
                return method
        return None

    @classmethod
    def is_available(cls, provider: str, code: str) -> bool:
        """Check that a payment method is available.

        Args:
            provider: Provider name.
            code: Provider-specific method code.

        Returns:
            True if the method can be used.
        """
        return cls.get_method(provider, code) is not None

    @classmethod
    def has_available_methods(cls) -> bool:
        """Check that at least one payment method is available."""
        return bool(cls.get_available_methods())

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get names of providers that passed the availability check."""
        return list(cls._available_providers)

    @classmethod
    def reset_cache(cls) -> None:
        """Reset the cache (used in tests)."""
        cls._methods = []
        cls._available_providers = []
        cls._initialized = False
