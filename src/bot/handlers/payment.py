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

from src.bot.constants import (
    LEGACY_CALLBACK_TARIFFS,
    CallbackData,
    parse_payment_method_callback,
    parse_tariff_callback,
)
from src.bot.keyboards import Keyboards
from src.bot.texts import Texts
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import UserRepository
from src.models.payment import PaymentStatus
from src.services.admin_notification import (
    PaymentErrorStage,
    notify_admins_payment_error,
)
from src.services.payment import PaymentService
from src.services.payment_methods import PaymentMethodsService
from src.services.tariff import TariffService

logger = logging.getLogger(__name__)


async def handle_tariff_selection(callback: CallbackQuery) -> None:
    """Handle tariff selection - show payment methods.

    Args:
        callback: Telegram callback query.
    """
    tariff_type = parse_tariff_callback(callback.data)
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

    logger.error(
        f"User selected tariff: user_id={callback.from_user.id}, "
        f"tariff_type={tariff_type}, amount={amount}"
    )


async def handle_payment_method_selection(callback: CallbackQuery) -> None:
    """Handle payment method selection - create payment.

    Args:
        callback: Telegram callback query.
    """
    parsed = parse_payment_method_callback(callback.data)
    if not parsed:
        await callback.answer("❌ Неверный формат", show_alert=True)
        return

    selector, tariff_type = parsed

    # Способ оплаты мог стать недоступен: провайдер отключили в настройках,
    # он не ответил при запуске бота или метод выключен у мерчанта,
    # а кнопка осталась в старом сообщении
    method = PaymentMethodsService.resolve_selector(selector)
    if method is None:
        logger.error(
            f"Payment method is not available: selector={selector}, "
            f"user_id={callback.from_user.id}"
        )
        await callback.answer(Texts.PAYMENT_METHOD_UNAVAILABLE, show_alert=True)

        # Обновляем клавиатуру, чтобы пользователь видел актуальные способы
        try:
            await callback.message.edit_reply_markup(
                reply_markup=Keyboards.payment_methods(tariff_type)
            )
        except Exception as e:
            logger.error(f"Failed to refresh payment methods keyboard: {e}")
        return

    provider_name = method.provider

    try:
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
            payment_service = PaymentService(session, provider_name=provider_name)
            payment, result = await payment_service.create_external_payment(
                telegram_id=str(callback.from_user.id),
                amount=amount,
                payment_method=method.code,
                description=f"Подписка: {tariff_data['label']}",
                extra_metadata={
                    "tariff_type": tariff_type,
                    "tariff_days": tariff_data["days"],
                },
            )

            logger.error(
                f"Payment created for subscription: user_id={callback.from_user.id}, "
                f"payment_id={payment.id}, external_id={result.external_id}, "
                f"amount={amount}, provider={provider_name}, method={method.label}, "
                f"tariff_type={tariff_type}, "
                f"payment_url={result.payment_url}"
            )

        await callback.message.edit_text(
            Texts.PAYMENT_CREATED.format(
                amount=amount,
                method_name=method.label,
                payment_id=payment.id,
            ),
            parse_mode="HTML",
            reply_markup=Keyboards.payment_confirm(payment.id, result.payment_url),
            disable_web_page_preview=True,
        )

    except ValueError as e:
        logger.error(
            f"Payment validation error: {e} "
            f"(user_id={callback.from_user.id}, amount={amount}, "
            f"provider={provider_name}, method={method.label})"
        )

        await notify_admins_payment_error(
            stage=PaymentErrorStage.CREATE,
            error=e,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
            amount=amount,
            details={
                "Способ оплаты": f"{provider_name} / {method.label}",
                "Тариф": tariff_type,
            },
        )

        await callback.message.edit_text(
            f"❌ <b>Ошибка создания платежа</b>\n\n{str(e)}",
            parse_mode="HTML",
            reply_markup=Keyboards.error_with_support_link(),
        )

    except Exception as e:
        logger.error(
            f"Failed to create payment: {e} "
            f"(user_id={callback.from_user.id}, amount={amount}, "
            f"provider={provider_name}, method={method.label})"
        )

        await notify_admins_payment_error(
            stage=PaymentErrorStage.CREATE,
            error=e,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
            amount=amount,
            details={
                "Способ оплаты": f"{provider_name} / {method.label}",
                "Тариф": tariff_type,
            },
        )

        await callback.message.edit_text(
            "❌ <b>Ошибка создания платежа</b>\n\n"
            "Не удалось создать платеж. Попробуйте еще раз или обратитесь в поддержку.",
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

            logger.error(
                f"Payment status checked: user_id={callback.from_user.id}, "
                f"payment_id={payment_id}, status={payment.status.value}"
            )

            if payment.status == PaymentStatus.COMPLETED:
                try:
                    delivery_result = await payment_service.complete_payment_and_deliver(
                        payment, str(callback.from_user.id)
                    )

                    logger.error(
                    f"Subscription activated from payment: user_id={user.id}, "
                    f"payment_id={payment_id}, delivery_type={delivery_result.get('type')}"
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
                    await notify_admins_payment_error(
                        stage=PaymentErrorStage.DELIVERY,
                        error=e,
                        telegram_id=callback.from_user.id,
                        username=callback.from_user.username,
                        full_name=callback.from_user.full_name,
                        payment=payment,
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

        await notify_admins_payment_error(
            stage=PaymentErrorStage.STATUS_CHECK,
            error=e,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
            details={"ID платежа": payment_id},
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
    from src.services.subscription import SubscriptionService
    from src.services.user import UserService
    from src.services.vpn_subscription import VpnSubscriptionService

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

            tariff_data = await tariff_service.get_tariff_data(tariff_type)
            if not tariff_data:
                await callback.answer("❌ Тариф не найден", show_alert=True)
                return

            amount = Decimal(str(tariff_data["price"]))
            user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

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

            payment = await payment_service.create_payment(
                telegram_id=str(callback.from_user.id),
                amount=amount,
                payment_provider="balance",
                description=f"Подписка: {tariff_data['label']} (с баланса)",
                payment_metadata={
                    "tariff_type": tariff_type,
                    "tariff_days": tariff_data["days"],
                },
            )

            payment = await payment_service.complete_payment(payment)

            await user_service.update_balance(user, -amount)

            user_updated = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

            duration_days = tariff_data["days"]

            subscription = await subscription_service.create_subscription(
                user_id=user.id,
                subscription_type=tariff_type,
                duration_days=duration_days,
            )

            vpn_link = "VPN link pending"
            try:
                vpn_service = VpnSubscriptionService(session)
                encrypted_sub = await vpn_service.create_subscription_for_tariff(
                    tariff_type=tariff_type,
                    subscription_id=subscription.id,
                )
                vpn_link = encrypted_sub.encrypted_link
                await vpn_service.close_client()
            except Exception as e:
                logger.error(f"Failed to create VPN subscription: {e}")
                await notify_admins_payment_error(
                    stage=PaymentErrorStage.VPN_LINK,
                    error=e,
                    telegram_id=callback.from_user.id,
                    username=callback.from_user.username,
                    full_name=callback.from_user.full_name,
                    payment=payment,
                    details={
                        "Подписка": str(subscription.id),
                        "Тариф": tariff_type,
                    },
                )

            logger.error(
                f"Subscription purchased with balance: user_id={user.id}, "
                f"payment_id={payment.id}, subscription_id={subscription.id}, "
                f"amount={amount}, new_balance={user_updated.balance if user_updated else 'unknown'}"
            )

            await callback.message.edit_text(
                Texts.PAYMENT_BALANCE_SUCCESS.format(
                    amount=amount,
                    balance=user_updated.balance if user_updated else Decimal("0"),
                    duration=duration_days,
                    vpn_link=vpn_link,
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
        await notify_admins_payment_error(
            stage=PaymentErrorStage.BALANCE_PAYMENT,
            error=e,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
            amount=amount if "amount" in locals() else None,
            details={"Тариф": tariff_type if "tariff_type" in locals() else None},
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
        F.data.startswith(f"{CallbackData.TARIFF_SELECT}:"),
    )
    dp.callback_query.register(
        handle_tariff_selection,
        F.data.in_(set(LEGACY_CALLBACK_TARIFFS)),
    )

    dp.callback_query.register(
        handle_payment_method_selection,
        F.data.startswith(f"{CallbackData.PAYMENT_METHOD_SELECT}:"),
    )

    dp.callback_query.register(
        handle_payment_balance_selection,
        F.data.startswith(f"{CallbackData.PAYMENT_BALANCE}:"),
    )

    dp.callback_query.register(
        handle_confirm_payment,
        F.data.startswith("confirm_payment:"),
    )

    logger.info("Payment handlers registered")
