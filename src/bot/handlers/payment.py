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
from src.services.tariff import TariffService
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import UserRepository
from src.infrastructure.payments import PlategaPaymentMethod
from src.models.payment import PaymentStatus
from src.services.payment import PaymentService

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

    async with async_session_maker() as session:
        tariff_service = TariffService(session)
        tariff_data = await tariff_service.get_tariff_data(tariff_type)

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

        async with async_session_maker() as session:
            tariff_service = TariffService(session)
            tariff_data = await tariff_service.get_tariff_data(tariff_type)

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
                try:
                    delivery_result = await payment_service.complete_payment_and_deliver(
                        payment, str(callback.from_user.id)
                    )

                    logger.info(
                        f"Subscription activated from payment",
                        extra={
                            "user_id": user.id,
                            "payment_id": payment_id,
                            "delivery_type": delivery_result.get("type"),
                        },
                    )

                    if delivery_result["type"] == "subscription":
                        await callback.message.edit_text(
                            Texts.PAYMENT_SUCCESS_RESULT.format(
                                duration=delivery_result["duration_days"],
                                vpn_link=delivery_result["vpn_link"],
                            ),
                            parse_mode="HTML",
                            reply_markup=Keyboards.subscription_success(),
                        )
                    elif delivery_result["type"] == "balance":
                        await callback.message.edit_text(
                            Texts.BALANCE_TOPUP_SUCCESS.format(
                                amount=delivery_result["amount"],
                                balance=delivery_result["new_balance"],
                            ),
                            parse_mode="HTML",
                            reply_markup=Keyboards.back_to_menu(),
                        )
                except ValueError as e:
                    logger.error(
                        f"Failed to deliver product: {e}",
                        extra={
                            "user_id": user.id,
                            "payment_id": payment_id,
                        },
                    )
                    await callback.message.edit_text(
                        f"❌ <b>Ошибка выдачи товара</b>\n\n{str(e)}",
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


async def handle_payment_balance_selection(callback: CallbackQuery) -> None:
    """Handle payment with balance - check funds and process payment.

    Args:
        callback: Telegram callback query.
    """
    from src.services.user import UserService
    from src.services.subscription import SubscriptionService
    from src.infrastructure.database.repositories import ProductRepository
    from src.config import settings

    try:
        tariff_type = callback.data.split(":")[1] if callback.data else None
        if not tariff_type:
            await callback.answer("❌ Неверный тариф", show_alert=True)
            return

        async with async_session_maker() as session:
            tariff_service = TariffService(session)
            user_service = UserService(session)
            payment_service = PaymentService(session)
            subscription_service = SubscriptionService(session)
            product_repository = ProductRepository(session)

            tariff_data = await tariff_service.get_tariff_data(tariff_type)
            if not tariff_data:
                await callback.answer("❌ Тариф не найден", show_alert=True)
                return

            amount = Decimal(str(tariff_data["price"]))
            user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            # Check balance
            if user.balance < amount:
                missing = amount - user.balance
                await callback.message.edit_text(
                    Texts.PAYMENT_BALANCE_INSUFFICIENT_FUNDS.format(
                        balance=user.balance,
                        required=amount,
                        missing=missing,
                        min_deposit=50,
                    ),
                    parse_mode="HTML",
                    reply_markup=Keyboards.balance_insufficient(),
                )
                await callback.answer()
                return

            # Create payment with balance provider
            payment = await payment_service.create_payment(
                telegram_id=str(callback.from_user.id),
                amount=amount,
                payment_provider="balance",
                description=f"Подписка: {tariff_data['label']} (с баланса)",
            )

            # Update payment status to COMPLETED immediately
            payment = await payment_service.complete_payment(payment)

            # Deduct balance (pass negative amount as change)
            await user_service.update_balance(user, -amount)

            # Get user again to have updated balance after deduction
            user_updated = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

            # Get product
            product = await product_repository.get_product_by_subscription_type(tariff_type)
            if not product:
                await callback.message.edit_text(
                    "❌ Продукт не найден. Обратитесь в поддержку.",
                    parse_mode="HTML",
                    reply_markup=Keyboards.error_with_support_link(),
                )
                await callback.answer()
                return

            # Create subscription
            subscription = await subscription_service.create_subscription(
                user_id=user.id,
                product_id=product.id,
                duration_days=product.duration_days,
            )

            logger.info(
                f"Subscription purchased with balance",
                extra={
                    "user_id": user.id,
                    "payment_id": payment.id,
                    "subscription_id": subscription.id,
                    "amount": str(amount),
                    "new_balance": str(user_updated.balance if user_updated else "unknown"),
                },
            )

            await callback.message.edit_text(
                Texts.PAYMENT_BALANCE_SUCCESS.format(
                    amount=amount,
                    balance=user_updated.balance if user_updated else Decimal("0"),
                    duration=product.duration_days,
                    vpn_link=product.happ_link,
                ),
                parse_mode="HTML",
                reply_markup=Keyboards.subscription_success(),
            )
            await callback.answer()

    except Exception as e:
        logger.error(
            f"Failed to process balance payment: {e}",
            extra={
                "user_id": callback.from_user.id,
                "tariff_type": tariff_type if "tariff_type" in locals() else None,
            },
        )
        await callback.message.edit_text(
            "❌ <b>Ошибка оплаты с баланса</b>\n\n"
            "Не удалось обработать платеж. Обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=Keyboards.error_with_support_link(),
        )
        await callback.answer()


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
        handle_payment_balance_selection,
        F.data.startswith("payment_balance:"),
    )

    dp.callback_query.register(
        handle_confirm_payment,
        F.data.startswith("confirm_payment:"),
    )

    logger.info("Payment handlers registered")
