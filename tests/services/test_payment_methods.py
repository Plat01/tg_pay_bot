"""Tests for PaymentMethodsService.

The service decides which payment method buttons the bot shows, so the tests
cover:
- providers that are unconfigured / unavailable / broken are skipped
- every payment method is probed separately
- a kind no provider supports disappears from the keyboards
- the provider for a kind is chosen by priority
- lookup by selector, both new (kind) and legacy (provider:code)
"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.infrastructure.payments.base import (
    PaymentMethodInfo,
    PaymentMethodKind,
    PaymentProvider,
)
from src.infrastructure.payments.factory import PaymentProviderFactory
from src.services.payment_methods import PaymentMethodsService


class FakeProvider(PaymentProvider):
    """Configurable provider used in the tests."""

    def __init__(
        self,
        provider_name: str = "fake",
        kinds: list[PaymentMethodKind] | None = None,
        configured: bool = True,
        available: bool = True,
        broken_kinds: set[PaymentMethodKind] | None = None,
        raise_on_check: bool = False,
    ) -> None:
        self._name = provider_name
        self._kinds = kinds if kinds is not None else [PaymentMethodKind.SBP]
        self._configured = configured
        self._available = available
        self._broken_kinds = broken_kinds or set()
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
        return [
            PaymentMethodInfo(provider=self._name, code=str(index), kind=kind)
            for index, kind in enumerate(self._kinds, start=1)
        ]

    async def check_method_availability(self, method: PaymentMethodInfo) -> bool:
        return method.kind not in self._broken_kinds

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

        assert [method.kind for method in methods] == [PaymentMethodKind.SBP]
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
        providers = {"fake": FakeProvider(kinds=[])}

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert methods == []

    async def test_broken_provider_does_not_break_others(self) -> None:
        """An error in one provider does not hide the other ones."""
        providers = {
            "broken": FakeProvider(provider_name="broken", raise_on_check=True),
            "working": FakeProvider(
                provider_name="working", kinds=[PaymentMethodKind.CRYPTO]
            ),
        }

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert [method.provider for method in methods] == ["working"]


class TestMethodProbe:
    """Tests for the per-method availability check."""

    async def test_method_disabled_for_merchant_is_dropped(self) -> None:
        """A method the provider rejects does not get a button."""
        providers = {
            "fake": FakeProvider(
                kinds=[PaymentMethodKind.SBP, PaymentMethodKind.CARD_RU],
                broken_kinds={PaymentMethodKind.CARD_RU},
            )
        }

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

        assert PaymentMethodsService.get_available_kinds() == [PaymentMethodKind.SBP]

    async def test_provider_with_all_methods_disabled_is_dropped(self) -> None:
        """A provider whose methods all fail the probe is not shown."""
        providers = {
            "fake": FakeProvider(
                kinds=[PaymentMethodKind.SBP],
                broken_kinds={PaymentMethodKind.SBP},
            )
        }

        with patch_providers(providers):
            methods = await PaymentMethodsService.refresh_cache()

        assert methods == []
        assert PaymentMethodsService.get_available_providers() == []


class TestKinds:
    """Tests for merging methods of several providers by kind."""

    async def test_same_kind_of_two_providers_gives_one_button(self) -> None:
        """Two providers with the same kind produce a single button."""
        providers = {
            "first": FakeProvider(provider_name="first", kinds=[PaymentMethodKind.SBP]),
            "second": FakeProvider(provider_name="second", kinds=[PaymentMethodKind.SBP]),
        }

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

        assert PaymentMethodsService.get_available_kinds() == [PaymentMethodKind.SBP]

    async def test_kinds_are_sorted_by_button_order(self) -> None:
        """Kinds of different providers are merged and sorted."""
        providers = {
            "first": FakeProvider(provider_name="first", kinds=[PaymentMethodKind.CRYPTO]),
            "second": FakeProvider(provider_name="second", kinds=[PaymentMethodKind.SBP]),
        }

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

        assert PaymentMethodsService.get_available_kinds() == [
            PaymentMethodKind.SBP,
            PaymentMethodKind.CRYPTO,
        ]

    async def test_kind_without_provider_is_not_shown(self) -> None:
        """A kind no available provider supports has no button."""
        providers = {"fake": FakeProvider(kinds=[PaymentMethodKind.SBP])}

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

        assert PaymentMethodKind.CARD_RU not in PaymentMethodsService.get_available_kinds()
        assert PaymentMethodsService.resolve(PaymentMethodKind.CARD_RU) is None


class TestResolve:
    """Tests for choosing a provider and parsing selectors."""

    async def test_default_provider_wins(self) -> None:
        """The default provider is preferred for a shared kind."""
        providers = {
            "other": FakeProvider(provider_name="other", kinds=[PaymentMethodKind.SBP]),
            "platega": FakeProvider(provider_name="platega", kinds=[PaymentMethodKind.SBP]),
        }

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

            method = PaymentMethodsService.resolve(PaymentMethodKind.SBP)

        assert method is not None
        assert method.provider == "platega"

    async def test_resolve_selector_by_kind(self) -> None:
        """A kind selector from the new callback format is resolved."""
        providers = {"fake": FakeProvider(kinds=[PaymentMethodKind.CRYPTO])}

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

            method = PaymentMethodsService.resolve_selector("crypto")

        assert method is not None
        assert method.kind == PaymentMethodKind.CRYPTO

    async def test_resolve_selector_by_provider_and_code(self) -> None:
        """A legacy "provider:code" selector is resolved."""
        providers = {"fake": FakeProvider(kinds=[PaymentMethodKind.SBP])}

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

            method = PaymentMethodsService.resolve_selector("fake:1")

        assert method is not None
        assert method.kind == PaymentMethodKind.SBP

    async def test_resolve_selector_of_unavailable_method(self) -> None:
        """An unavailable method is not resolved."""
        providers = {"fake": FakeProvider(available=False)}

        with patch_providers(providers):
            await PaymentMethodsService.refresh_cache()

            assert PaymentMethodsService.resolve_selector("sbp") is None
            assert PaymentMethodsService.resolve_selector("fake:1") is None

    def test_fallback_to_configured_providers(self) -> None:
        """Without an initialized cache configured providers are used."""
        providers = {"fake": FakeProvider()}

        with patch_providers(providers):
            kinds = PaymentMethodsService.get_available_kinds()

        assert kinds == [PaymentMethodKind.SBP]


class TestPaymentMethodInfo:
    """Tests for the payment method model."""

    def test_view_is_taken_from_kind(self) -> None:
        """Label, emoji and order come from the method kind."""
        method = PaymentMethodInfo(
            provider="fake", code="1", kind=PaymentMethodKind.CARD_RU
        )

        assert method.label == "Банковская карта РФ"
        assert method.button_text == "💳 Банковская карта РФ"
        assert method.key == "fake:1"
        assert method.order == 20
