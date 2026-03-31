"""Handler for deposit/balance top-up commands.

This module provides handlers for users to deposit funds
into their account using various payment methods.
"""

import logging
from decimal import Decimal, InvalidOperation

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.payments import PlategaPaymentMethod
from src.models.payment import PaymentStatus
from src.services.payment import PaymentService

logger = logging.getLogger(__name__)


class DepositStates(StatesGroup):
    """FSM states for deposit flow."""

    amount = State()  # Waiting for amount input
    method = State()  # Waiting for payment method selection


# Minimum deposit amount
MIN_DEPOSIT_AMOUNT = Decimal("100")


def get_payment_method_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with payment method options.

    Returns:
        InlineKeyboardMarkup with payment method buttons.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="💳 СБП QR-код",
                callback_data=f"method:{PlategaPaymentMethod.SBP_QR}",
            )
        ],
        [
            InlineKeyboardButton(
                text="💳 Банковская карта",
                callback_data=f"method:{PlategaPaymentMethod.CARD_ACQUIRING}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🌍 Международная карта",
                callback_data=f"method:{PlategaPaymentMethod.INTERNATIONAL}",
            )
        ],
        [
            InlineKeyboardButton(
                text="₿ Криптовалюта",
                callback_data=f"method:{PlategaPaymentMethod.CRYPTO}",
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="method:cancel",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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

    Args:
        message: Telegram message.
        state: FSM state context.
    """
    # Clear any previous state
    await state.clear()

    # Set new state
    await state.set_state(DepositStates.amount)

    # Send message with amount options
    await message.answer(
        "💳 <b>Пополнение баланса</b>\n\n"
        f"Минимальная сумма: {MIN_DEPOSIT_AMOUNT} ₽\n\n"
        "Выберите сумму или введите вручную:",
        parse_mode="HTML",
        reply_markup=get_amount_keyboard(),
    )

    logger.info(
        f"User started deposit flow",
        extra={"user_id": message.from_user.id},
    )


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
        await callback.message.edit_text("❌ Пополнение отменено")
        await callback.answer()
        return

    amount = Decimal(data)
    await state.update_data(amount=amount)
    await state.set_state(DepositStates.method)

    # Show payment method selection
    await callback.message.edit_text(
        f"💰 <b>Пополнение баланса</b>\n\n"
        f"Сумма: {amount} ₽\n\n"
        "Выберите способ оплаты:",
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
                f"❌ Минимальная сумма пополнения: {MIN_DEPOSIT_AMOUNT} ₽\n"
                "Введите другую сумму:",
            )
            return

        # Store amount and move to method selection
        await state.update_data(amount=amount)
        await state.set_state(DepositStates.method)

        await message.answer(
            f"💰 <b>Пополнение баланса</b>\n\n"
            f"Сумма: {amount} ₽\n\n"
            "Выберите способ оплаты:",
            parse_mode="HTML",
            reply_markup=get_payment_method_keyboard(),
        )

    except InvalidOperation:
        await message.answer(
            "❌ Неверный формат суммы.\n"
            "Введите число, например: 500 или 1000",
        )


async def process_method_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle payment method selection and create payment.

    Args:
        callback: Telegram callback query.
        state: FSM state context.
    """
    # Parse method from callback data
    data = callback.data.split(":")[1]

    if data == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Пополнение отменено")
        await callback.answer()
        return

    # Get stored amount
    state_data = await state.get_data()
    amount = state_data.get("amount")

    if not amount:
        await state.clear()
        await callback.message.edit_text("❌ Ошибка: сумма не выбрана")
        await callback.answer()
        return

    # Parse payment method
    payment_method = PlategaPaymentMethod(int(data))

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
            payment_service = PaymentService(session)
            payment, result = await payment_service.create_external_payment(
                user_id=callback.from_user.id,
                amount=amount,
                payment_method=payment_method,
                description=f"Пополнение баланса",
            )

        logger.info(
            f"Payment created for user",
            extra={
                "user_id": callback.from_user.id,
                "payment_id": payment.id,
                "external_id": result.external_id,
                "amount": str(amount),
                "method": payment_method.name,
            },
        )

        # Build success message
        method_name = {
            PlategaPaymentMethod.SBP_QR: "СБП QR-код",
            PlategaPaymentMethod.CARD_ACQUIRING: "Банковская карта",
            PlategaPaymentMethod.INTERNATIONAL: "Международная карта",
            PlategaPaymentMethod.CRYPTO: "Криптовалюта",
            PlategaPaymentMethod.ERIP: "ЕРИП",
        }.get(payment_method, "Неизвестный метод")

        message_text = (
            f"✅ <b>Платёж создан!</b>\n\n"
            f"💰 Сумма: {amount} ₽\n"
            f"💳 Способ: {method_name}\n"
            f"📋 ID платежа: #{payment.id}\n\n"
        )

        if result.payment_url:
            message_text += (
                f"🔗 <b>Для оплаты перейдите по ссылке:</b>\n"
                f"{result.payment_url}\n\n"
            )

        message_text += (
            f"⏰ После оплаты проверьте статус командой:\n"
            f"<code>/check_{payment.id}</code>"
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
                ] if result.payment_url else [],
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
            f"Failed to create payment: {e}",
            extra={
                "user_id": callback.from_user.id,
                "amount": str(amount),
            },
        )

        await callback.message.edit_text(
            f"❌ <b>Ошибка создания платежа</b>\n\n"
            f"Попробуйте позже или выберите другой способ оплаты.\n\n"
            f"Техническая информация: {str(e)[:100]}",
            parse_mode="HTML",
        )


async def cmd_check_payment(message: Message) -> None:
    """Handle /check_{id} command - check payment status.

    Args:
        message: Telegram message.
    """
    # Parse payment ID from command
    try:
        # Command format: /check_123 or /check 123
        text = message.text or ""
        if "_" in text:
            payment_id = int(text.split("_")[1])
        elif " " in text:
            payment_id = int(text.split()[1])
        else:
            await message.answer("❌ Укажите ID платежа: /check_123")
            return
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Используйте: /check_123")
        return

    # Get payment and check status
    try:
        async with async_session_maker() as session:
            payment_service = PaymentService(session)

            # Get payment from database
            payment = await payment_service.get_payment_by_id(payment_id)

            if not payment:
                await message.answer(f"❌ Платёж #{payment_id} не найден")
                return

            # Check if user owns this payment
            if payment.user_id != message.from_user.id:
                await message.answer("❌ Это не ваш платёж")
                return

            # Check status from provider if payment is pending
            if payment.status == PaymentStatus.PENDING and payment.external_id:
                payment = await payment_service.check_and_update_status(payment)

        # Build status message
        status_emoji = {
            PaymentStatus.PENDING: "⏳",
            PaymentStatus.COMPLETED: "✅",
            PaymentStatus.FAILED: "❌",
            PaymentStatus.CANCELLED: "🚫",
        }

        status_text = {
            PaymentStatus.PENDING: "Ожидает оплаты",
            PaymentStatus.COMPLETED: "Успешно завершён",
            PaymentStatus.FAILED: "Ошибка",
            PaymentStatus.CANCELLED: "Отменён",
        }

        emoji = status_emoji.get(payment.status, "❓")
        text = status_text.get(payment.status, "Неизвестно")

        await message.answer(
            f"{emoji} <b>Статус платежа #{payment.id}</b>\n\n"
            f"💰 Сумма: {payment.amount} {payment.currency}\n"
            f"📋 Статус: {text}\n"
            f"📅 Создан: {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n",
            parse_mode="HTML",
        )

        logger.info(
            f"User checked payment status",
            extra={
                "user_id": message.from_user.id,
                "payment_id": payment_id,
                "status": payment.status.value,
            },
        )

    except Exception as e:
        logger.error(
            f"Failed to check payment: {e}",
            extra={
                "user_id": message.from_user.id,
                "payment_id": payment_id,
            },
        )
        await message.answer(
            f"❌ Ошибка проверки статуса\n\n"
            f"Попробуйте позже.\n"
            f"Техническая информация: {str(e)[:100]}"
        )


async def check_payment_callback(callback: CallbackQuery) -> None:
    """Handle check payment button callback.

    Args:
        callback: Telegram callback query.
    """
    # Parse payment ID from callback data
    try:
        payment_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID")
        return

    # Get payment and check status
    try:
        async with async_session_maker() as session:
            payment_service = PaymentService(session)

            payment = await payment_service.get_payment_by_id(payment_id)

            if not payment:
                await callback.message.edit_text(f"❌ Платёж #{payment_id} не найден")
                await callback.answer()
                return

            if payment.user_id != callback.from_user.id:
                await callback.answer("❌ Это не ваш платёж", show_alert=True)
                return

            # Check status from provider if pending
            if payment.status == PaymentStatus.PENDING and payment.external_id:
                payment = await payment_service.check_and_update_status(payment)

        # Build status message
        status_emoji = {
            PaymentStatus.PENDING: "⏳",
            PaymentStatus.COMPLETED: "✅",
            PaymentStatus.FAILED: "❌",
            PaymentStatus.CANCELLED: "🚫",
        }

        status_text = {
            PaymentStatus.PENDING: "Ожидает оплаты",
            PaymentStatus.COMPLETED: "Успешно завершён",
            PaymentStatus.FAILED: "Ошибка",
            PaymentStatus.CANCELLED: "Отменён",
        }

        emoji = status_emoji.get(payment.status, "❓")
        text = status_text.get(payment.status, "Неизвестно")

        # Update message
        await callback.message.edit_text(
            f"{emoji} <b>Статус платежа #{payment.id}</b>\n\n"
            f"💰 Сумма: {payment.amount} {payment.currency}\n"
            f"📋 Статус: {text}\n"
            f"📅 Создан: {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n",
            parse_mode="HTML",
            reply_markup=None,
        )

        await callback.answer(f"Статус: {text}")

    except Exception as e:
        logger.error(f"Failed to check payment: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


async def cmd_balance(message: Message) -> None:
    """Handle /balance command - show user balance.

    Args:
        message: Telegram message.
    """
    try:
        async with async_session_maker() as session:
            from src.services.user import UserService

            user_service = UserService(session)
            user = await user_service.get_user_by_telegram_id(message.from_user.id)

            if not user:
                await message.answer(
                    "❌ Вы не зарегистрированы.\n"
                    "Используйте /start для регистрации."
                )
                return

        await message.answer(
            f"💰 <b>Ваш баланс</b>\n\n"
            f"Сумма: {user.balance} ₽\n"
            f"Реферальный код: <code>{user.referral_code}</code>\n\n"
            f"Для пополнения используйте /deposit",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Failed to get balance: {e}")
        await message.answer("❌ Ошибка получения баланса")


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