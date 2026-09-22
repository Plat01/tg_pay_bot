"""Сервис уведомления администраторов о проблемах с платежами.

Модуль собирает информацию об ошибке платежа (пользователь, платеж, текст
ошибки) и рассылает её всем администраторам из ``settings.admin_id_list``.

Импорт бота выполняется внутри функции, чтобы избежать циклического импорта
(``src.bot.bot`` тянет за собой хендлеры, которые используют сервисы).
"""

import html
import logging
from datetime import timedelta, timezone
from decimal import Decimal
from typing import Any

from src.config import settings
from src.models.payment import Payment
from src.models.user import User

logger = logging.getLogger(__name__)

# Максимальная длина текста ошибки в уведомлении
MAX_ERROR_LENGTH = 600

# Московское время для отображения дат администратору
MSK_TZ = timezone(timedelta(hours=3))


class PaymentErrorStage:
    """Этапы платежа, на которых может возникнуть ошибка."""

    CREATE = "Создание платежа"
    STATUS_CHECK = "Проверка статуса платежа"
    PROVIDER_REJECTED = "Платеж отклонен платежной системой"
    DELIVERY = "Выдача товара после оплаты"
    VPN_LINK = "Создание VPN подписки"
    BALANCE_PAYMENT = "Оплата с баланса"
    AUTO_CHECK = "Автопроверка платежа (планировщик)"


def _escape(value: Any) -> str:
    """Экранировать значение для вставки в HTML сообщение."""
    return html.escape(str(value), quote=False)


def _format_error(error: BaseException | str) -> str:
    """Привести ошибку к читаемому виду с ограничением длины.

    Args:
        error: Исключение или готовый текст ошибки.

    Returns:
        Экранированный текст ошибки.
    """
    if isinstance(error, BaseException):
        text = f"{type(error).__name__}: {error}"
    else:
        text = str(error)

    text = text.strip() or "Неизвестная ошибка"

    if len(text) > MAX_ERROR_LENGTH:
        text = f"{text[:MAX_ERROR_LENGTH]}…"

    return _escape(text)


def _build_user_block(
    telegram_id: str | int | None,
    username: str | None,
    full_name: str | None,
) -> str:
    """Собрать блок с данными пользователя и ссылками на него.

    Args:
        telegram_id: Telegram ID пользователя.
        username: Telegram username без "@".
        full_name: Имя пользователя для отображения.

    Returns:
        HTML-блок со ссылкой на пользователя.
    """
    lines: list[str] = []

    if full_name:
        lines.append(f"Имя: {_escape(full_name)}")

    if username:
        clean_username = _escape(str(username).lstrip("@"))
        lines.append(f"Username: @{clean_username}")
        lines.append(f"Ссылка: https://t.me/{clean_username}")

    if telegram_id:
        escaped_id = _escape(telegram_id)
        # Для href экранируем и кавычки
        attr_id = html.escape(str(telegram_id), quote=True)
        lines.append(f"Telegram ID: <code>{escaped_id}</code>")
        # Ссылка tg://user работает, если пользователь известен клиенту админа
        lines.append(f'Профиль: <a href="tg://user?id={attr_id}">открыть</a>')

    if not lines:
        lines.append("Не определен")

    return "\n".join(lines)


def _build_payment_block(
    payment: Payment | None,
    amount: Decimal | None,
    details: dict[str, Any] | None,
) -> str:
    """Собрать блок с данными платежа.

    Args:
        payment: Запись платежа из БД (если платеж успел создаться).
        amount: Сумма платежа (если записи в БД еще нет).
        details: Дополнительные поля (способ оплаты, тариф и т.д.).

    Returns:
        HTML-блок с информацией о платеже.
    """
    lines: list[str] = []

    if payment is not None:
        lines.append(f"ID: <code>{_escape(payment.id)}</code>")
        lines.append(f"Сумма: {_escape(payment.amount)} {_escape(payment.currency)}")
        lines.append(f"Статус: {_escape(payment.status.value)}")

        if payment.payment_provider:
            lines.append(f"Провайдер: {_escape(payment.payment_provider)}")

        if payment.external_id:
            lines.append(f"External ID: <code>{_escape(payment.external_id)}</code>")

        if payment.description:
            lines.append(f"Описание: {_escape(payment.description)}")

        metadata = payment.payment_metadata or {}
        tariff_type = metadata.get("tariff_type")
        if tariff_type:
            lines.append(f"Тариф: {_escape(tariff_type)}")

        if payment.created_at:
            created_msk = payment.created_at.astimezone(MSK_TZ)
            lines.append(f"Создан: {created_msk.strftime('%d.%m.%Y %H:%M')} (МСК)")

    elif amount is not None:
        lines.append(f"Сумма: {_escape(amount)} RUB")

    if details:
        for key, value in details.items():
            if value is None:
                continue
            lines.append(f"{_escape(key)}: {_escape(value)}")

    if not lines:
        lines.append("Нет данных")

    return "\n".join(lines)


async def notify_admins_payment_error(
    *,
    stage: str,
    error: BaseException | str,
    telegram_id: str | int | None = None,
    username: str | None = None,
    full_name: str | None = None,
    user: User | None = None,
    payment: Payment | None = None,
    amount: Decimal | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Отправить администраторам уведомление об ошибке платежа.

    Функция никогда не выбрасывает исключений: сбой отправки уведомления
    не должен ломать основной сценарий работы с платежом.

    Args:
        stage: Этап платежа (см. :class:`PaymentErrorStage`).
        error: Исключение или текст ошибки.
        telegram_id: Telegram ID пользователя.
        username: Telegram username пользователя.
        full_name: Имя пользователя.
        user: Модель пользователя (заполняет поля выше, если они не переданы).
        payment: Запись платежа из БД.
        amount: Сумма платежа, если записи в БД нет.
        details: Дополнительные поля для блока платежа.
    """
    if not settings.notify_admins_on_payment_errors:
        return

    admin_ids = settings.admin_id_list
    if not admin_ids:
        logger.warning("No admin IDs configured, skipping payment error notification")
        return

    try:
        # Данные из модели пользователя как запасной источник
        if user is not None:
            telegram_id = telegram_id or user.telegram_id
            username = username or user.username
            full_name = full_name or " ".join(
                part for part in (user.first_name, user.last_name) if part
            )

        # Локальные импорты: разрываем цикл services -> bot -> handlers -> services
        from src.bot.bot import bot
        from src.bot.texts import Texts

        text = Texts.ADMIN_PAYMENT_ERROR.format(
            stage=_escape(stage),
            user_block=_build_user_block(telegram_id, username, full_name),
            payment_block=_build_payment_block(payment, amount, details),
            error=_format_error(error),
        )
    except Exception as e:  # noqa: BLE001 - уведомление не должно ломать основной поток
        logger.error(f"Failed to build admin payment error notification: {e}", exc_info=True)
        return

    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id,
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:  # noqa: BLE001 - один недоступный админ не блокирует остальных
            logger.error(f"Failed to send payment error notification to admin {admin_id}: {e}")

    logger.info(
        "Admin payment error notification sent",
        extra={
            "stage": stage,
            "telegram_id": telegram_id,
            "payment_id": str(payment.id) if payment else None,
        },
    )
