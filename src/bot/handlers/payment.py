"""Handler for subscription payment flow.

This module provides handlers for the complete payment flow:
1. Tariff selection
2. Payment method selection
3. Payment creation via Platega
4. Payment confirmation by user ("Я оплатил")
5. Subscription activation on successful payment
"""

import logging
import uuid
from decimal import Decimal

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.constants import CallbackData
from src.bot.keyboards import Keyboards
from src.bot.texts import Texts
from src.bot.subscription_prices import get_tariff_data, get_tariff_by_price
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import UserRepository, ProductRepository
from src.infrastructure.payments import PlategaPaymentMethod
from src.models.payment import PaymentStatus
from src.services.payment import PaymentService
from src.services.subscription import SubscriptionService

logger = logging.getLogger(__name__)


async def handle_tariff_selection(callback: CallbackQuery) -> None:
    """Handle tariff selection - show payment methods.

    Args:
        callback: Telegram callback query.
    """
    tariff_type_map = {
        CallbackData.TARIFF_1_MONTH: "monthly",
        CallbackData.TARIFF_3_MONTHS: "quarterly",
        CallbackData.TARIFF_12_MONTHS: "yearly",
    }

    tariff_type = tariff_type_map.get(callback.data)
    if not tariff_type:
        await callback.answer("❌ Неверный тариф", show_alert=True)
        return

    tariff_data = get_tariff_data(tariff_type)
    if not tariff_data:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return

    amount = tariff_data["price"]
    label = tariff_data["label"]

    await callback.message.edit_text(
        Texts.PAYMENT_METHOD_SELECT.format(amount=amount, tariff_label=label),
        parse_mode="HTML",
        reply_markup=Keyboards.payment_methods(tariff_type),
    )
    await callback.answer()

    logger.info(
        f"User selected tariff",
        extra={
            "user_id": callback.from_user.id,
            "tariff_type": tariff_type,
            "amount": amount,
        },
    )


async def handle_payment_method_selection(callback: CallbackQuery) -> None:
    """Handle payment method selection - create payment.

    Args:
        callback: Telegram callback query.
    """
    try:
        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer("❌ Неверный формат", show_alert=True)
            return

        payment_method_code = int(parts[1])
        tariff_type = parts[2]

        payment_method = PlategaPaymentMethod(payment_method_code)
        tariff_data = get_tariff_data(tariff_type)

        if not tariff_data:
            await callback.answer("❌ Тариф не найден", show_alert=True)
            return

        amount = Decimal(str(tariff_data["price"]))

    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка обработки данных", show_alert=True)
        return

    await callback.message.edit_text(
        "⏳ <b>Создание платежа...</b>",
        parse_mode="HTML",
    )
    await callback.answer()

    try:
        async with async_session_maker() as session:
            payment_service = PaymentService(session)
            payment, result = await payment_service.create_external_payment(
                telegram_id=str(callback.from_user.id),
                amount=amount,
                payment_method=payment_method,
                description=f"Подписка: {tariff_data['label']}",
            )

            logger.info(
                f"Payment created for subscription",
                extra={
                    "user_id": callback.from_user.id,
                    "payment_id": payment.id,
                    "external_id": result.external_id,
                    "amount": str(amount),
                    "method": payment_method.name,
                    "tariff_type": tariff_type,
                    "payment_url": result.payment_url,
                    "has_payment_url": result.payment_url is not None and result.payment_url != "",
                },
            )

        method_names = {
            PlategaPaymentMethod.SBP_QR: "СБП QR-код",
            PlategaPaymentMethod.CARD_ACQUIRING: "Банковская карта РФ",
            PlategaPaymentMethod.INTERNATIONAL: "Международная карта",
            PlategaPaymentMethod.CRYPTO: "Криптовалюта",
            PlategaPaymentMethod.ERIP: "ЕРИП",
        }

        method_name = method_names.get(payment_method, "Неизвестный метод")

        await callback.message.edit_text(
            Texts.PAYMENT_CREATED.format(
                amount=amount,
                method_name=method_name,
                payment_id=payment.id,
            ),
            parse_mode="HTML",
            reply_markup=Keyboards.payment_confirm(payment.id, result.payment_url),
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(
            f"Failed to create payment: {e}",
            extra={
                "user_id": callback.from_user.id,
                "amount": str(amount),
                "method": payment_method.name,
            },
        )

        await callback.message.edit_text(
            "❌ <b>Ошибка создания платежа</b>\n\n"
            "Не удалось создать платеж. Обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=Keyboards.error_with_support_link(),
        )


async def handle_confirm_payment(callback: CallbackQuery) -> None:
    """Handle 'I paid' button - check payment status and activate subscription.

    Args:
        callback: Telegram callback query.
    """
    try:
        payment_id_str = callback.data.split(":")[1]
        payment_id = uuid.UUID(payment_id_str)
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный ID платежа", show_alert=True)
        return

    await callback.message.edit_text(
        Texts.PAYMENT_PENDING_CHECK,
        parse_mode="HTML",
    )
    await callback.answer()

    try:
        async with async_session_maker() as session:
            payment_service = PaymentService(session)
            user_repository = UserRepository(session)
            subscription_service = SubscriptionService(session)
            product_repository = ProductRepository(session)

            payment = await payment_service.get_payment_by_id(payment_id)

            if not payment:
                await callback.message.edit_text(
                    f"❌ Платёж #{payment_id} не найден",
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_menu(),
                )
                return

            user = await user_repository.get_by_telegram_id(str(callback.from_user.id))
            if not user or payment.user_id != user.id:
                await callback.message.edit_text(
                    "❌ Это не ваш платёж",
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_menu(),
                )
                return

            if payment.status == PaymentStatus.PENDING and payment.external_id:
                payment = await payment_service.check_and_update_status(payment)

            logger.info(
                f"Payment status checked",
                extra={
                    "user_id": callback.from_user.id,
                    "payment_id": payment_id,
                    "status": payment.status.value,
                },
            )

            if payment.status == PaymentStatus.COMPLETED:
                tariff_type = get_tariff_by_price(int(payment.amount))

                if not tariff_type:
                    await callback.message.edit_text(
                        f"❌ Не удалось определить тариф для суммы {payment.amount}",
                        parse_mode="HTML",
                        reply_markup=Keyboards.back_to_menu(),
                    )
                    return

                product = await product_repository.get_product_by_subscription_type(tariff_type)

                if not product:
                    await callback.message.edit_text(
                        f"❌ Продукт для тарифа {tariff_type} не найден",
                        parse_mode="HTML",
                        reply_markup=Keyboards.back_to_menu(),
                    )
                    return

                subscription = await subscription_service.create_subscription(
                    user_id=user.id,
                    product_id=product.id,
                    duration_days=product.duration_days,
                )

                logger.info(
                    f"Subscription activated from payment",
                    extra={
                        "user_id": user.id,
                        "subscription_id": subscription.id,
                        "payment_id": payment_id,
                        "tariff_type": tariff_type,
                        "duration_days": product.duration_days,
                    },
                )

                await callback.message.edit_text(
                    Texts.PAYMENT_SUCCESS_RESULT.format(
                        duration=product.duration_days,
                        vpn_link=product.happ_link,
                    ),
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_menu(),
                )

            elif payment.status == PaymentStatus.PENDING:
                await callback.message.edit_text(
                    Texts.PAYMENT_PENDING_RESULT,
                    parse_mode="HTML",
                    reply_markup=Keyboards.payment_confirm(payment.id),
                )

            elif payment.status == PaymentStatus.FAILED:
                reason = "Техническая ошибка платежной системы"
                await callback.message.edit_text(
                    Texts.PAYMENT_FAILED_RESULT.format(reason=reason),
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_menu(),
                )

            elif payment.status == PaymentStatus.CANCELLED:
                await callback.message.edit_text(
                    Texts.PAYMENT_CANCELLED_RESULT,
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_menu(),
                )

            else:
                await callback.message.edit_text(
                    f"❓ Неизвестный статус платежа: {payment.status.value}",
                    parse_mode="HTML",
                    reply_markup=Keyboards.back_to_menu(),
                )

    except Exception as e:
        logger.error(
            f"Failed to confirm payment: {e}",
            extra={
                "user_id": callback.from_user.id,
                "payment_id": payment_id,
            },
        )

        await callback.message.edit_text(
            "❌ <b>Ошибка проверки платежа</b>\n\n"
            "Не удалось проверить статус платежа. Обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=Keyboards.error_with_support_link(),
        )


def register_payment_handlers(dp: Dispatcher) -> None:
    """Register payment handlers with dispatcher.

    Args:
        dp: Aiogram dispatcher.
    """
    dp.callback_query.register(
        handle_tariff_selection,
        F.data == CallbackData.TARIFF_1_MONTH,
    )
    dp.callback_query.register(
        handle_tariff_selection,
        F.data == CallbackData.TARIFF_3_MONTHS,
    )
    dp.callback_query.register(
        handle_tariff_selection,
        F.data == CallbackData.TARIFF_12_MONTHS,
    )

    dp.callback_query.register(
        handle_payment_method_selection,
        F.data.startswith("payment_method:"),
    )

    dp.callback_query.register(
        handle_confirm_payment,
        F.data.startswith("confirm_payment:"),
    )

    logger.info("Payment handlers registered")
