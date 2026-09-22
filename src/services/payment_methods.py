"""Service that keeps the list of currently available payment methods.

On bot start every provider registered in ``PaymentProviderFactory`` is asked
whether it is configured and reachable, and then every payment method it
declares is probed separately. Only methods that really work get a button.

Buttons correspond to method kinds (СБП, карта, крипта, ...), not to
providers: if several providers support the same kind, the user still sees
one button and the provider is chosen by priority. A kind that no available
provider supports disappears from the keyboards.

Adding a new provider requires no changes here: it is enough to register it in
the factory and implement ``get_payment_methods()`` (plus optionally
``is_configured()`` / ``check_availability()`` / ``check_method_availability()``)
in the provider class.
"""

import asyncio
import logging

from src.config import settings
from src.infrastructure.payments import (
    MethodCheckResult,
    PaymentMethodInfo,
    PaymentMethodKind,
    PaymentProvider,
    PaymentProviderFactory,
)

logger = logging.getLogger(__name__)


class PaymentMethodsService:
    """In-memory cache of payment methods available right now.

    The cache is filled once on bot start (``initialize_cache``) and can be
    rebuilt at any time (``refresh_cache``), for example after changing
    provider credentials.

    Example:
        >>> await PaymentMethodsService.initialize_cache()
        >>> for kind in PaymentMethodsService.get_available_kinds():
        ...     method = PaymentMethodsService.resolve(kind)
        ...     print(kind.value, "->", method.provider, method.code)
    """

    # Every working (provider, method) pair, sorted by button order
    _methods: list[PaymentMethodInfo] = []
    # Names of providers that passed the availability check
    _available_providers: list[str] = []
    # Human-readable result of the last check (for the admin command)
    _report: list[str] = []
    # Whether the cache has been filled at least once
    _initialized: bool = False
    # Guards against parallel refreshes
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def initialize_cache(cls) -> list[PaymentMethodInfo]:
        """Fill the cache on bot start.

        Returns:
            List of working payment methods.
        """
        return await cls.refresh_cache()

    @classmethod
    async def refresh_cache(cls) -> list[PaymentMethodInfo]:
        """Re-check all registered providers and rebuild the cache.

        Providers are checked concurrently, an error in one of them does not
        affect the others.

        Returns:
            List of working payment methods.
        """
        async with cls._lock:
            provider_names = PaymentProviderFactory.get_available_providers()

            results = await asyncio.gather(
                *(cls._check_provider(name) for name in provider_names)
            )

            methods: list[PaymentMethodInfo] = []
            available_providers: list[str] = []
            report: list[str] = []

            for provider_name, provider_methods, provider_report in results:
                report.extend(provider_report)
                if not provider_methods:
                    continue
                available_providers.append(provider_name)
                methods.extend(provider_methods)

            # Stable order of buttons regardless of the check order
            methods.sort(key=lambda item: (item.order, item.provider, item.code))

            cls._methods = methods
            cls._available_providers = available_providers
            cls._report = report
            cls._initialized = True

            cls._log_result(methods)

            return list(cls._methods)

    @classmethod
    def _log_result(cls, methods: list[PaymentMethodInfo]) -> None:
        """Log the result of the check.

        Logged at error level on purpose: in production the logging level is
        ERROR, and this is the only way to see the result in the logs.

        Args:
            methods: Working payment methods.
        """
        if not methods:
            logger.error(
                "No payment methods available: all payment providers are "
                "unconfigured, unreachable or have no working methods"
            )
            return

        logger.error(
            "Available payment methods: "
            + ", ".join(f"{item.label} ({item.provider}:{item.code})" for item in methods)
        )

    @classmethod
    async def _check_provider(
        cls,
        provider_name: str,
    ) -> tuple[str, list[PaymentMethodInfo], list[str]]:
        """Check a single provider and all payment methods it declares.

        Args:
            provider_name: Name of the provider registered in the factory.

        Returns:
            Tuple of (provider name, its working methods, report lines).
            The list of methods is empty if the provider cannot be used.
        """
        try:
            provider = PaymentProviderFactory.create(provider_name)

            if not provider.is_configured():
                logger.error(f"Payment provider '{provider_name}' is not configured, skipping")
                return provider_name, [], [f"{provider_name}: не настроен"]

            if not await provider.check_availability():
                logger.error(f"Payment provider '{provider_name}' is unavailable, skipping")
                return provider_name, [], [f"{provider_name}: недоступен"]

            declared_methods = provider.get_payment_methods()
            if not declared_methods:
                logger.error(
                    f"Payment provider '{provider_name}' has no enabled payment methods, skipping"
                )
                return provider_name, [], [f"{provider_name}: нет включенных способов оплаты"]

            # Every declared method is probed separately: a provider may be
            # alive while some of its methods are switched off for the merchant
            checks = await asyncio.gather(
                *(cls._check_method(provider, method) for method in declared_methods)
            )

            working: list[PaymentMethodInfo] = []
            report: list[str] = []

            for method, result in checks:
                mark = "✅" if result.available else "❌"
                suffix = f" — {result.reason}" if result.reason else ""
                report.append(f"{mark} {provider_name}:{method.code} {method.label}{suffix}")

                if result.available:
                    working.append(method)

            return provider_name, working, report

        except Exception as e:
            logger.error(f"Failed to check payment provider '{provider_name}': {e}")
            return provider_name, [], [f"{provider_name}: ошибка проверки — {e}"]

    @staticmethod
    async def _check_method(
        provider: PaymentProvider,
        method: PaymentMethodInfo,
    ) -> tuple[PaymentMethodInfo, MethodCheckResult]:
        """Check a single payment method of a provider.

        Args:
            provider: Provider instance.
            method: Method to check.

        Returns:
            Tuple of (method, check result).
        """
        try:
            return method, await provider.check_method_availability(method)
        except Exception as e:
            # Ошибка самой проверки не должна прятать способ оплаты
            logger.error(f"Failed to check payment method '{method.key}', keeping it: {e}")
            return method, MethodCheckResult(
                available=True,
                reason=f"проверка не удалась ({e}), способ оставлен",
            )

    @classmethod
    def get_report(cls) -> list[str]:
        """Get the human-readable result of the last check.

        Returns:
            Report lines, one per checked payment method or skipped provider.
        """
        return list(cls._report)

    @classmethod
    def get_available_methods(cls) -> list[PaymentMethodInfo]:
        """Get every working (provider, method) pair.

        If the cache has not been initialized yet (e.g. a handler fired before
        startup finished), methods of configured providers are returned
        without any network check.

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
    def get_available_kinds(cls) -> list[PaymentMethodKind]:
        """Get kinds of payment methods that have at least one provider.

        These are exactly the buttons the bot shows: a kind that no available
        provider supports is not in the list.

        Returns:
            List of PaymentMethodKind sorted by button order.
        """
        kinds: list[PaymentMethodKind] = []

        for method in cls.get_available_methods():
            if method.kind not in kinds:
                kinds.append(method.kind)

        return kinds

    @classmethod
    def resolve(cls, kind: PaymentMethodKind | str) -> PaymentMethodInfo | None:
        """Choose the provider that will process a payment method kind.

        Providers are tried in priority order (see ``get_provider_priority``),
        the first one supporting the kind wins.

        Args:
            kind: Method kind or its string value from the callback data.

        Returns:
            PaymentMethodInfo of the chosen provider or None if no available
            provider supports the kind.
        """
        try:
            method_kind = PaymentMethodKind(kind)
        except ValueError:
            return None

        methods = [method for method in cls.get_available_methods() if method.kind == method_kind]
        if not methods:
            return None

        priority = cls.get_provider_priority()
        methods.sort(key=lambda item: priority.index(item.provider))

        return methods[0]

    @classmethod
    def resolve_selector(cls, selector: str) -> PaymentMethodInfo | None:
        """Resolve a payment method selector from callback data.

        A selector is either a method kind ("sbp") or a "provider:code" pair
        ("platega:2") coming from a button of an older format.

        Args:
            selector: Selector string built by the callback data parser.

        Returns:
            PaymentMethodInfo or None if nothing matches.
        """
        if ":" in selector:
            provider, code = selector.split(":", 1)
            return cls.get_method(provider, code)

        return cls.resolve(selector)

    @classmethod
    def get_provider_priority(cls) -> list[str]:
        """Get the order in which providers are chosen for a method kind.

        TODO: сейчас это заглушка — провайдер по умолчанию идет первым,
        остальные в порядке регистрации в фабрике. Настраиваемый приоритет
        провайдеров будет добавлен позже (см. .kilo/todo.md).

        Returns:
            Provider names, the most preferred one first.
        """
        priority = list(PaymentProviderFactory.get_available_providers())

        default_provider = settings.default_payment_provider
        if default_provider in priority:
            priority.remove(default_provider)
            priority.insert(0, default_provider)

        return priority

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
        """Find a working payment method by provider name and code.

        Used for buttons from old messages, where the callback data holds the
        provider and its own method code.

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
        cls._report = []
        cls._initialized = False
