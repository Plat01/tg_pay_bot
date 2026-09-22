"""Handler for deposit/balance top-up commands.

This module provides handlers for users to deposit funds
into their account using various payment methods.
"""

import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Tuple

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.bot.constants import CallbackData, parse_deposit_method_callback
from src.bot.keyboards import Keyboards
from src.bot.texts import Texts
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import UserRepository
from src.models.payment import Payment, PaymentStatus
from src.services.admin_notification import (
    PaymentErrorStage,
    notify_admins_payment_error,
)
from src.services.payment import PaymentService
from src.services.payment_methods import PaymentMethodsService

logger = logging.getLogger(__name__)


class DepositStates(StatesGroup):
    """FSM states for deposit flow."""

    amount = State()  # Waiting for amount input
    method = State()  # Waiting for payment method selection


# Minimum deposit amount
MIN_DEPOSIT_AMOUNT = Decimal("100")


def get_payment_method_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with available payment method options.

    Buttons are built from the payment methods available right now
    (see PaymentMethodsService).

    Returns:
        InlineKeyboardMarkup with payment method buttons.
    """
    return Keyboards.deposit_methods()


async def notify_no_payment_methods(
    message: Message,
    state: FSMContext,
) -> None:
    """Tell the user that no payment method is available and reset the flow.

    Args:
        message: Message to answer (the user's message or the bot's message
            from a callback).
        state: FSM state context.
    """
    await state.clear()
    await message.answer(Texts.PAYMENT_METHODS_UNAVAILABLE, parse_mode="HTML")

    logger.error("Deposit flow stopped: no payment methods available")


def get_amount_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with preset amount options.

    Returns:
        InlineKeyboardMarkup with preset amount buttons.
    """
    buttons = [
        [
            InlineKeyboardButton(text="100 ₽", callback_data="amount:100"),
            InlineKeyboardButton(text="500 ₽", callback_data="amount:500"),
        ],
        [
            InlineKeyboardButton(text="1000 ₽", callback_data="amount:1000"),
            InlineKeyboardButton(text="5000 ₽", callback_data="amount:5000"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="amount:cancel"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def cmd_deposit(message: Message, state: FSMContext) -> None:
    """Handle /deposit command - start deposit flow.

    Supports optional amount argument: /deposit <amount>

    Args:
        message: Telegram message.
        state: FSM state context.
    """
    # Clear any previous state
    await state.clear()

    # Check for amount argument
    args = message.text.split() if message.text else []
    if len(args) > 1:
        # Amount provided as argument
        try:
            amount_str = args[1].replace(",", ".").replace(" ", "").replace("₽", "")
            amount = Decimal(amount_str)

            # Validate minimum amount
            if amount < MIN_DEPOSIT_AMOUNT:
                await message.answer(
                    Texts.DEPOSIT_MIN_AMOUNT_ERROR.format(min_amount=MIN_DEPOSIT_AMOUNT),
                )
                return

            # Nothing to pay with - stop the flow before asking for a method
            if not PaymentMethodsService.has_available_methods():
                await notify_no_payment_methods(message, state)
                return

            # Store amount and proceed to method selection
            await state.update_data(amount=amount)
            await state.set_state(DepositStates.method)

            await message.answer(
                Texts.DEPOSIT_AMOUNT_SELECTED.format(amount=amount),
                parse_mode="HTML",
                reply_markup=get_payment_method_keyboard(),
            )
            return

        except InvalidOperation:
            await message.answer(Texts.DEPOSIT_INVALID_FORMAT)
            return

    # No amount provided - show amount selection keyboard
    await state.set_state(DepositStates.amount)

    # Send message with amount options
    await message.answer(
        Texts.DEPOSIT_START.format(min_amount=MIN_DEPOSIT_AMOUNT),
        parse_mode="HTML",
        reply_markup=get_amount_keyboard(),
    )

    logger.error(f"User started deposit flow: user_id={message.from_user.id}")


async def process_amount_preset(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle preset amount button selection.

    Args:
        callback: Telegram callback query.
        state: FSM state context.
    """
    # Parse amount from callback data
    data = callback.data.split(":")[1]

    if data == "cancel":
        await state.clear()
        await callback.message.edit_text(Texts.DEPOSIT_CANCELLED)
        await callback.answer()
        return

    if not PaymentMethodsService.has_available_methods():
        await notify_no_payment_methods(callback.message, state)
        await callback.answer()
        return

    amount = Decimal(data)
    await state.update_data(amount=amount)
    await state.set_state(DepositStates.method)

    # Show payment method selection
    await callback.message.edit_text(
        Texts.DEPOSIT_AMOUNT_SELECTED.format(amount=amount),
        parse_mode="HTML",
        reply_markup=get_payment_method_keyboard(),
    )
    await callback.answer()


async def process_amount_input(message: Message, state: FSMContext) -> None:
    """Handle manual amount input.

    Args:
        message: Telegram message.
        state: FSM state context.
    """
    try:
        # Parse amount from message
        amount_str = message.text.replace(",", ".").replace(" ", "").replace("₽", "")
        amount = Decimal(amount_str)

        # Validate minimum amount
        if amount < MIN_DEPOSIT_AMOUNT:
            await message.answer(
                Texts.DEPOSIT_MIN_AMOUNT_ERROR.format(min_amount=MIN_DEPOSIT_AMOUNT),
            )
            return

        if not PaymentMethodsService.has_available_methods():
            await notify_no_payment_methods(message, state)
            return

        # Store amount and move to method selection
        await state.update_data(amount=amount)
        await state.set_state(DepositStates.method)

        await message.answer(
            Texts.DEPOSIT_AMOUNT_SELECTED.format(amount=amount),
            parse_mode="HTML",
            reply_markup=get_payment_method_keyboard(),
        )

    except InvalidOperation:
        await message.answer(Texts.DEPOSIT_INVALID_FORMAT)


async def process_method_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle payment method selection and create payment.

    Args:
        callback: Telegram callback query.
        state: FSM state context.
    """
    # Cancel button
    if callback.data == f"{CallbackData.DEPOSIT_METHOD}:cancel":
        await state.clear()
        await callback.message.edit_text(Texts.DEPOSIT_CANCELLED)
        await callback.answer()
        return

    # Parse payment method selector from callback data
    selector = parse_deposit_method_callback(callback.data)

    if not selector:
        await callback.answer("❌ Неверный формат", show_alert=True)
        return

    # The method could become unavailable after the button was sent
    method = PaymentMethodsService.resolve_selector(selector)

    if method is None:
        logger.error(
            f"Payment method is not available: selector={selector}, "
            f"user_id={callback.from_user.id}"
        )
        await callback.answer(Texts.PAYMENT_METHOD_UNAVAILABLE, show_alert=True)

        # Показываем актуальные способы оплаты вместо устаревших кнопок
        try:
            await callback.message.edit_reply_markup(
                reply_markup=get_payment_method_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to refresh payment methods keyboard: {e}")
        return

    provider_name = method.provider

    # Get stored amount
    state_data = await state.get_data()
    amount = state_data.get("amount")

    if not amount:
        await state.clear()
        await callback.message.edit_text(Texts.ERROR_GENERIC)
        await callback.answer()
        return

    # Clear state before API call
    await state.clear()

    # Show loading message
    await callback.message.edit_text(
        "⏳ <b>Создание платежа...</b>",
        parse_mode="HTML",
    )
    await callback.answer()

    # Create payment via provider
    try:
        async with async_session_maker() as session:
            payment_service = PaymentService(session, provider_name=provider_name)
            payment, result = await payment_service.create_external_payment(
                telegram_id=str(callback.from_user.id),
                amount=amount,
                payment_method=method.code,
                description=f"Пополнение баланса",
            )

        logger.error(
            f"Payment created for user: user_id={callback.from_user.id}, "
            f"payment_id={payment.id}, external_id={result.external_id}, "
            f"amount={amount}, provider={provider_name}, method={method.label}"
        )

        # Build success message
        method_name = method.label

        message_text = (
            f"✅ <b>Платёж создан!</b>\n\n"
            f"💰 Сумма: {amount} ₽\n"
            f"💳 Способ: {method_name}\n"
            f"📋 ID платежа: #{payment.id}\n\n"
        )

        if result.payment_url:
            message_text += f"🔗 <b>Для оплаты перейдите по ссылке:</b>\n{result.payment_url}\n\n"

        message_text += (
            f"⏰ После оплаты проверьте статус командой:\n<code>/check_{payment.id}</code>"
        )

        # Add check status button
        check_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Проверить статус",
                        callback_data=f"check:{payment.id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💳 Перейти к оплате",
                        url=result.payment_url,
                    )
                ]
                if result.payment_url
                else [],
            ]
        )

        await callback.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=check_button,
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(
            f"Failed to create payment: {e} (user_id={callback.from_user.id}, amount={amount})"
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
                "Тип": "Пополнение баланса",
            },
        )

        await callback.message.edit_text(
            f"❌ <b>Ошибка создания платежа</b>\n\n"
            f"Попробуйте позже или выберите другой способ оплаты.\n\n"
            f"Техническая информация: {str(e)[:100]}",
            parse_mode="HTML",
        )


async def _check_payment_status(
    payment_id: uuid.UUID, telegram_id: int
) -> Tuple[Payment, str, str]:
    """Check payment status and return payment with emoji and text.

    Args:
        payment_id: Payment UUID.
        telegram_id: User's Telegram ID.

    Returns:
        Tuple of (Payment, emoji, status_text).

    Raises:
        ValueError: If payment not found or doesn't belong to user.
        Exception: For other errors.
    """
    async with async_session_maker() as session:
        payment_service = PaymentService(session)
        user_repository = UserRepository(session)

        payment = await payment_service.get_payment_by_id(payment_id)

        if not payment:
            raise ValueError(f"Платёж #{payment_id} не найден")

        user = await user_repository.get_by_telegram_id(str(telegram_id))
        if not user or payment.user_id != user.id:
            raise ValueError("Это не ваш платёж")

        if payment.status == PaymentStatus.PENDING and payment.external_id:
            payment = await payment_service.check_and_update_status(payment)

    status_emoji = {
        PaymentStatus.PENDING: "⏳",
        PaymentStatus.COMPLETED: "✅",
        PaymentStatus.FAILED: "❌",
        PaymentStatus.CANCELLED: "🚫",
    }

    status_text_map = {
        PaymentStatus.PENDING: "Ожидает оплаты",
        PaymentStatus.COMPLETED: "Успешно завершён",
        PaymentStatus.FAILED: "Ошибка",
        PaymentStatus.CANCELLED: "Отменён",
    }

    emoji = status_emoji.get(payment.status, "❓")
    text = status_text_map.get(payment.status, "Неизвестно")

    return payment, emoji, text


async def cmd_check_payment(message: Message) -> None:
    """Handle /check_{id} command - check payment status.

    Args:
        message: Telegram message.
    """
    try:
        text = message.text or ""
        if "_" in text:
            payment_id_str = text.split("_")[1]
        elif " " in text:
            payment_id_str = text.split()[1]
        else:
            await message.answer("❌ Укажите ID платежа: /check_<uuid>")
            return

        payment_id = uuid.UUID(payment_id_str)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Используйте: /check_<uuid>")
        return

    try:
        payment, emoji, status_text = await _check_payment_status(payment_id, message.from_user.id)

        await message.answer(
            f"{emoji} <b>Статус платежа #{payment.id}</b>\n\n"
            f"💰 Сумма: {payment.amount} {payment.currency}\n"
            f"📋 Статус: {status_text}\n"
            f"📅 Создан: {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n",
            parse_mode="HTML",
        )

        logger.error(
            f"User checked payment status: user_id={message.from_user.id}, "
            f"payment_id={payment_id}, status={payment.status.value}"
        )

    except ValueError as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(
            f"Failed to check payment: {e}",
            extra={"user_id": message.from_user.id, "payment_id": str(payment_id)},
        )
        await notify_admins_payment_error(
            stage=PaymentErrorStage.STATUS_CHECK,
            error=e,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            details={"ID платежа": payment_id},
        )
        await message.answer(
            f"❌ Ошибка проверки статуса\n\nПопробуйте позже.\nТехническая информация: {str(e)[:100]}"
        )


async def check_payment_callback(callback: CallbackQuery) -> None:
    """Handle check payment button callback.

    Args:
        callback: Telegram callback query.
    """
    try:
        payment_id_str = callback.data.split(":")[1]
        payment_id = uuid.UUID(payment_id_str)
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный ID платежа", show_alert=True)
        return

    try:
        payment, emoji, status_text = await _check_payment_status(payment_id, callback.from_user.id)

        await callback.message.edit_text(
            f"{emoji} <b>Статус платежа #{payment.id}</b>\n\n"
            f"💰 Сумма: {payment.amount} {payment.currency}\n"
            f"📋 Статус: {status_text}\n"
            f"📅 Создан: {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n",
            parse_mode="HTML",
            reply_markup=None,
        )
        await callback.answer(f"Статус: {status_text}")

    except ValueError as e:
        await callback.answer(f"❌ {str(e)}", show_alert=True)
    except Exception as e:
        logger.error(f"Failed to check payment: {e}")
        await notify_admins_payment_error(
            stage=PaymentErrorStage.STATUS_CHECK,
            error=e,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
            details={"ID платежа": payment_id},
        )
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


async def cmd_balance(message: Message) -> None:
    """Handle /balance command - show user balance.

    Args:
        message: Telegram message.
    """
    try:
        async with async_session_maker() as session:
            from src.services.user import UserService
            from src.bot.texts import Texts

            user_service = UserService(session)
            user = await user_service.get_user_by_telegram_id(str(message.from_user.id))

            if not user:
                await message.answer(Texts.ERROR_NOT_REGISTERED)
                return

        balance_text = Texts.BALANCE_INFO.format(
            balance=user.balance,
            referral_code=user.referral_code,
        )
        await message.answer(balance_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Failed to get balance: {e}")
        await message.answer(Texts.ERROR_BALANCE)


def register_deposit_handlers(dp: Dispatcher) -> None:
    """Register deposit handlers with dispatcher.

    Args:
        dp: Aiogram dispatcher.
    """
    # Command handlers
    dp.message.register(cmd_deposit, Command("deposit"))
    dp.message.register(cmd_balance, Command("balance"))
    dp.message.register(cmd_check_payment, Command("check"))

    # FSM state handlers
    dp.message.register(process_amount_input, DepositStates.amount)
    dp.callback_query.register(
        process_amount_preset,
        F.data.startswith("amount:"),
        DepositStates.amount,
    )
    dp.callback_query.register(
        process_method_selection,
        F.data.startswith("method:"),
        DepositStates.method,
    )

    # Check payment callback
    dp.callback_query.register(check_payment_callback, F.data.startswith("check:"))

    logger.info("Deposit handlers registered")
