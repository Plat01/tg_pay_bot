"""Тесты уведомления администраторов об ошибках платежей."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import ModuleType
from unittest.mock import AsyncMock, patch

import pytest

from src.models.payment import Payment, PaymentStatus
from src.models.user import User
from src.services.admin_notification import (
    PaymentErrorStage,
    _build_payment_block,
    _build_user_block,
    _format_error,
    notify_admins_payment_error,
)


@pytest.fixture
def user() -> User:
    """Пользователь для уведомления."""
    return User(
        telegram_id="555000111",
        username="test_user",
        first_name="Иван",
        last_name="Петров",
        referral_code="ABC12345",
    )


@pytest.fixture
def payment(user: User) -> Payment:
    """Платеж со статусом FAILED."""
    return Payment(
        id=uuid.uuid4(),
        user_id=user.id,
        amount=Decimal("499.00"),
        currency="RUB",
        status=PaymentStatus.FAILED,
        payment_provider="platega",
        external_id="ext-123",
        description="Подписка: 1 месяц",
        payment_metadata={"tariff_type": "month_1", "tariff_days": 30},
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def fake_bot(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Подменить модуль src.bot.bot на заглушку с моком бота."""
    bot = AsyncMock()
    module = ModuleType("src.bot.bot")
    module.bot = bot
    module.dp = object()
    monkeypatch.setitem(__import__("sys").modules, "src.bot.bot", module)
    return bot


def test_build_user_block_contains_links(user: User) -> None:
    """Блок пользователя содержит username, ссылку и Telegram ID."""
    block = _build_user_block(user.telegram_id, user.username, "Иван Петров")

    assert "@test_user" in block
    assert "https://t.me/test_user" in block
    assert "<code>555000111</code>" in block
    assert 'tg://user?id=555000111' in block


def test_build_user_block_without_data() -> None:
    """Без данных пользователя блок не пустой."""
    assert _build_user_block(None, None, None) == "Не определен"


def test_build_user_block_escapes_html() -> None:
    """Имя пользователя экранируется."""
    block = _build_user_block(None, None, "<b>hack</b>")

    assert "&lt;b&gt;hack&lt;/b&gt;" in block


def test_build_payment_block_with_payment(payment: Payment) -> None:
    """Блок платежа содержит ключевые поля."""
    block = _build_payment_block(payment, None, {"Способ оплаты": "SBP_QR"})

    assert str(payment.id) in block
    assert "499.00 RUB" in block
    assert "failed" in block
    assert "ext-123" in block
    assert "month_1" in block
    assert "Способ оплаты: SBP_QR" in block


def test_build_payment_block_without_payment() -> None:
    """Если записи платежа нет, выводится только сумма."""
    block = _build_payment_block(None, Decimal("100"), None)

    assert "Сумма: 100 RUB" in block


def test_format_error_from_exception() -> None:
    """Исключение форматируется с именем класса."""
    assert _format_error(ValueError("boom")) == "ValueError: boom"


def test_format_error_truncated() -> None:
    """Слишком длинная ошибка обрезается."""
    assert len(_format_error("x" * 1000)) <= 601


async def test_notify_sends_to_all_admins(
    fake_bot: AsyncMock, user: User, payment: Payment
) -> None:
    """Уведомление уходит каждому администратору."""
    with patch("src.services.admin_notification.settings") as mock_settings:
        mock_settings.notify_admins_on_payment_errors = True
        mock_settings.admin_id_list = ["111", "222"]

        await notify_admins_payment_error(
            stage=PaymentErrorStage.PROVIDER_REJECTED,
            error=ValueError("boom"),
            user=user,
            payment=payment,
        )

    assert fake_bot.send_message.await_count == 2

    text = fake_bot.send_message.await_args_list[0].args[1]
    assert PaymentErrorStage.PROVIDER_REJECTED in text
    assert "https://t.me/test_user" in text
    assert str(payment.id) in text
    assert "ValueError: boom" in text


async def test_notify_disabled_by_settings(fake_bot: AsyncMock) -> None:
    """При выключенной настройке уведомления не отправляются."""
    with patch("src.services.admin_notification.settings") as mock_settings:
        mock_settings.notify_admins_on_payment_errors = False
        mock_settings.admin_id_list = ["111"]

        await notify_admins_payment_error(stage="test", error="error", telegram_id=1)

    fake_bot.send_message.assert_not_awaited()


async def test_notify_without_admins(fake_bot: AsyncMock) -> None:
    """Без настроенных админов отправки нет."""
    with patch("src.services.admin_notification.settings") as mock_settings:
        mock_settings.notify_admins_on_payment_errors = True
        mock_settings.admin_id_list = []

        await notify_admins_payment_error(stage="test", error="error", telegram_id=1)

    fake_bot.send_message.assert_not_awaited()


async def test_notify_survives_send_error(fake_bot: AsyncMock) -> None:
    """Ошибка отправки одному админу не мешает остальным."""
    fake_bot.send_message.side_effect = [Exception("blocked"), None]

    with patch("src.services.admin_notification.settings") as mock_settings:
        mock_settings.notify_admins_on_payment_errors = True
        mock_settings.admin_id_list = ["111", "222"]

        await notify_admins_payment_error(stage="test", error="error", telegram_id=1)

    assert fake_bot.send_message.await_count == 2
