"""Tests for PaymentMethodsService.

The service decides which payment method buttons the bot shows, so the tests
cover:
- providers that are unconfigured / unavailable / broken are skipped
- methods of several providers live together in one list
- lookup by provider and method code
"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.infrastructure.payments.base import PaymentMethodInfo, PaymentProvider
from src.infrastructure.payments.factory import PaymentProviderFactory
from src.services.payment_methods import PaymentMethodsService


class FakeProvider(PaymentProvider):
    """Configurable provider used in the tests."""

    def __init__(
        self,
        provider_name: str = "fake",
        configured: bool = True,
        available: bool = True,
        methods: list[PaymentMethodInfo] | None = None,
        raise_on_check: bool = False,
    ) -> None:
        self._name = provider_name
        self._configured = configured
        self._available = available
        self._methods = methods
        self._raise_on_check = raise_on_check

    @property
    def name(self) -> str:
        return self._name

    def is_configured(self) -> bool:
        return self._configured

    async def check_availability(self) -> bool:
        if self._raise_on_check:
            raise RuntimeError("provider is broken")
        return self._available

    def get_payment_methods(self) -> list[PaymentMethodInfo]:
        if self._methods is not None:
            return self._methods
        return [
            PaymentMethodInfo(provider=self._name, code="1", label="Способ 1", order=10),
        ]

    async def create_payment(self, amount, currency, description, metadata=None, **kwargs):
        pass

    async def get_payment_status(self, external_id):
        pass

    def map_status(self, external_status):
        pass

    async def close(self):
        pass


@contextmanager
def patch_providers(providers: dict[str, FakeProvider]) -> Iterator[None]:
    """Patch the factory so it returns the given fake providers.

    Args:
        providers: Mapping of provider name to fake provider instance.

    Yields:
        None while the factory is patched.
    """
    with (
        patch.object(
            PaymentProviderFactory,
            "get_available_providers",
            lambda: list(providers),
        ),
        patch.object(
            PaymentProviderFactory,
            "create",
            lambda name: providers[name],
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def clear_cache():
    """Reset the cache before and after every test."""
    PaymentMethodsService.reset_cache()
    yield
    PaymentMethodsService.reset_cache()


class TestRefreshCache:
    """Tests for filling the cache of available methods."""

    async def test_available_provider_methods_are_cached(self) -> None:
        """Methods of an available provider get into the cache."""
        providers = {"fake": FakeProvider()}

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert [method.code for method in methods] == ["1"]
        assert PaymentMethodsService.get_available_providers() == ["fake"]

    async def test_unconfigured_provider_is_skipped(self) -> None:
        """A provider without credentials is not shown."""
        providers = {"fake": FakeProvider(configured=False)}

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert methods == []
        assert PaymentMethodsService.has_available_methods() is False

    async def test_unavailable_provider_is_skipped(self) -> None:
        """A provider that failed the availability check is not shown."""
        providers = {"fake": FakeProvider(available=False)}

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert methods == []

    async def test_provider_without_methods_is_skipped(self) -> None:
        """A provider with no enabled methods is not shown."""
        providers = {"fake": FakeProvider(methods=[])}

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert methods == []

    async def test_broken_provider_does_not_break_others(self) -> None:
        """An error in one provider does not hide the other ones."""
        providers = {
            "broken": FakeProvider(provider_name="broken", raise_on_check=True),
            "working": FakeProvider(
                provider_name="working",
                methods=[
                    PaymentMethodInfo(
                        provider="working", code="7", label="Способ 7", order=20
                    )
                ],
            ),
        }

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert [method.key for method in methods] == ["working:7"]

    async def test_methods_of_several_providers_are_sorted(self) -> None:
        """Methods of different providers are merged and sorted by order."""
        providers = {
            "first": FakeProvider(
                provider_name="first",
                methods=[
                    PaymentMethodInfo(provider="first", code="1", label="Второй", order=20)
                ],
            ),
            "second": FakeProvider(
                provider_name="second",
                methods=[
                    PaymentMethodInfo(provider="second", code="2", label="Первый", order=10)
                ],
            ),
        }

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert [method.key for method in methods] == ["second:2", "first:1"]


class TestLookup:
    """Tests for looking up a method by provider and code."""

    async def test_get_method_returns_available_method(self) -> None:
        """An available method is found by provider and code."""
        providers = {"fake": FakeProvider()}

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

        method = PaymentMethodsService.get_method("fake", "1")

        assert method is not None
        assert method.label == "Способ 1"
        assert PaymentMethodsService.is_available("fake", "1") is True

    async def test_get_method_returns_none_for_unavailable(self) -> None:
        """An unavailable method is not found."""
        providers = {"fake": FakeProvider(available=False)}

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

        assert PaymentMethodsService.get_method("fake", "1") is None
        assert PaymentMethodsService.is_available("fake", "1") is False

    def test_fallback_to_configured_providers(self) -> None:
        """Without an initialized cache configured providers are used."""
        providers = {"fake": FakeProvider()}

        with patch_providers(providers):
            methods = PaymentMethodsService.get_available_methods()

        assert [method.key for method in methods] == ["fake:1"]


class TestPaymentMethodInfo:
    """Tests for the payment method model."""

    def test_button_text_contains_emoji_and_label(self) -> None:
        """The button label is built from emoji and method name."""
        method = PaymentMethodInfo(provider="fake", code="1", label="Карта", emoji="💳")

        assert method.button_text == "💳 Карта"
        assert method.key == "fake:1"
