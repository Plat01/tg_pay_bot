"""Start command handler for user registration and main menu handlers."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.constants import CallbackData
from src.bot.keyboards import Keyboards
from src.bot.texts import Texts
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.services.subscription import SubscriptionService
from src.services.user import UserService

logger = logging.getLogger(__name__)


async def cmd_start(message: Message) -> None:
    """Handle /start command - register or welcome back user.

    Shows main menu inline keyboard with buttons under message.
    """
    # Extract referral code from command arguments
    args = message.text.split() if message.text else []
    referral_code = args[1] if len(args) > 1 else None

    async with async_session_maker() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)

        # Get user info from message
        user = message.from_user
        if not user:
            await message.answer("Error: Could not get user info")
            return

        # Register or update user
        db_user = await user_service.get_or_create_user(
            telegram_id=str(user.id),
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
            is_bot=user.is_bot,
            is_premium=getattr(user, "is_premium", False),
            referral_code=referral_code,
        )

        # Get subscription status using user UUID
        subscription = await subscription_service.get_active_subscription(db_user.id)
        if subscription:
            subscription_status = "✅ Активна"
            subscription_end = subscription.end_date.strftime("%d.%B %Y г.")
        else:
            subscription_status = "❌ Не активна"
            subscription_end = "—"

        # Send welcome message with main menu inline keyboard
        await message.answer(
            Texts.START_WELCOME.format(
                subscription_status=subscription_status,
                subscription_end=subscription_end,
            ),
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(),
        )

        logger.info(f"User started bot: {user.id} (@{user.username})")


async def handle_main_menu_callback(callback: CallbackQuery) -> None:
    """Handle 'Назад' button - return to main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)

        db_user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not db_user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=None,
            )
            await callback.answer()
            return

        # Get subscription status using user UUID
        subscription = await subscription_service.get_active_subscription(db_user.id)
        if subscription:
            subscription_status = "✅ Активна"
            subscription_end = subscription.end_date.strftime("%d.%B %Y г.")
        else:
            subscription_status = "❌ Не активна"
            subscription_end = "—"

        await callback.message.edit_text(
            Texts.START_MAIN_MENU.format(
                subscription_status=subscription_status,
                subscription_end=subscription_end,
            ),
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(),
        )
        await callback.answer()


async def handle_info_callback(callback: CallbackQuery) -> None:
    """Handle ℹ️ Инфо button from main menu."""
    await callback.message.edit_text(
        Texts.INFO_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=Keyboards.info_menu(),
    )
    await callback.answer()


async def handle_profile_callback(callback: CallbackQuery) -> None:
    """Handle 💼 Профиль button from main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)

        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        # Get active subscription using user UUID
        subscription = await subscription_service.get_active_subscription(user.id)

        # Build display name: first_name last_name, or username if not available
        name_parts = []
        if user.first_name:
            name_parts.append(user.first_name)
        if user.last_name:
            name_parts.append(user.last_name)
        display_name = " ".join(name_parts) if name_parts else (user.username or f"#{user.id}")

        if subscription:
            # Format subscription info
            sub_info = subscription_service.get_subscription_info(subscription)
            end_date_str = subscription.end_date.strftime("%d.%m.%Y %H:%M")
            time_left_str = f"{sub_info['days_left']} дн. / {sub_info['hours_left']} час."

            # Get product information
            device_limit = subscription.product.device_limit if subscription.product else 1
            subscription_type = (
                subscription.product.subscription_type.value if subscription.product else "unknown"
            )

            profile_text = Texts.PROFILE_TEXT.format(
                username=display_name,
                subscription_end=end_date_str,
                time_left=time_left_str,
                device_limit=device_limit,
                subscription_type=subscription_type,
            )

            await callback.message.edit_text(
                profile_text,
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_menu(),
            )
        else:
            profile_text = Texts.PROFILE_NO_SUBSCRIPTION.format(
                username=display_name,
                balance=user.balance,
            )

            # Show pay button when no subscription
            await callback.message.edit_text(
                profile_text,
                parse_mode="HTML",
                reply_markup=Keyboards.buy_subscription(),
            )
        await callback.answer()


async def handle_pay_callback(callback: CallbackQuery) -> None:
    """Handle 💳 Оплатить button from main menu."""
    await callback.message.edit_text(
        Texts.PAY_TEXT,
        parse_mode="HTML",
        reply_markup=Keyboards.buy_subscription(),
    )
    await callback.answer()


async def handle_support_callback(callback: CallbackQuery) -> None:
    """Handle 🛠️ Поддержка button from main menu."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        # Format support text with user ID
        support_text = Texts.SUPPORT_TEXT.format(user_id=user.telegram_id)

        # Create keyboard with support link button
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Перейти в поддержку", url=settings.support_link)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

        await callback.message.edit_text(
            support_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        await callback.answer()


async def handle_bonuses_callback(callback: CallbackQuery) -> None:
    """Handle 🎁 Бонусы button from main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        # Check if user was referred (eligible for trial bonus)
        if user.referred_by_id:
            # User was referred - show bonus info with trial option
            await callback.message.edit_text(
                Texts.BONUSES_TEXT,
                parse_mode="HTML",
                reply_markup=Keyboards.trial_subscription(),
            )
        else:
            # User was not referred - show general bonus info
            await callback.message.edit_text(
                Texts.BONUSES_TEXT,
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_menu(),
            )
        await callback.answer()


async def handle_connect_callback(callback: CallbackQuery) -> None:
    """Handle 👥 Пригласить друга button from main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)

        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        # Build referral link
        referral_link = f"{settings.bot_link}?start={user.referral_code}"

        connect_text = Texts.CONNECT_TEXT.format(
            referral_link=referral_link,
        )

        # Add button to share referral link
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📤 Отправить друзьям",
                        switch_inline_query=referral_link,
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

        await callback.message.edit_text(
            connect_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        await callback.answer()


async def handle_balance_callback(callback: CallbackQuery) -> None:
    """Handle 💰 Баланс button from main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        balance_text = Texts.BALANCE_INFO.format(
            balance=user.balance,
            referral_code=user.referral_code,
        )

        # Send balance info with deposit amount buttons
        await callback.message.edit_text(
            balance_text,
            parse_mode="HTML",
            reply_markup=Keyboards.balance_actions(),
        )
        await callback.answer()

        # Send deposit prompt with amount buttons
        await callback.message.answer(
            Texts.BALANCE_DEPOSIT_PROMPT,
            parse_mode="HTML",
            reply_markup=Keyboards.balance_deposit_amounts(),
        )


async def handle_deposit_callback(callback: CallbackQuery) -> None:
    """Handle ➕ Пополнить button from main menu.

    Redirects to deposit flow with amount selection keyboard.
    """
    from src.bot.handlers.deposit import MIN_DEPOSIT_AMOUNT

    await callback.message.edit_text(
        Texts.DEPOSIT_START.format(min_amount=MIN_DEPOSIT_AMOUNT),
        parse_mode="HTML",
        reply_markup=Keyboards.balance_deposit_amounts(),
    )
    await callback.answer()


async def handle_referral_callback(callback: CallbackQuery) -> None:
    """Handle 👥 Пригласить друга button from main menu.

    Shows referral information with invite link and share button.
    """
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        # Build referral link
        referral_link = f"{settings.bot_link}?start={user.referral_code}"

        # Format referral info message
        referral_text = Texts.REFERRAL_INFO.format(
            bot_link=settings.bot_link,
            referral_code=user.referral_code,
        )

        # Send referral info with invite keyboard
        await callback.message.edit_text(
            referral_text,
            parse_mode="HTML",
            reply_markup=Keyboards.referral_invite(referral_link),
        )
        await callback.answer()


async def handle_help_callback(callback: CallbackQuery) -> None:
    """Handle 📖 Помощь button from main menu."""
    await callback.message.edit_text(
        Texts.HELP_TEXT,
        parse_mode="HTML",
        reply_markup=Keyboards.back_to_menu(),
    )
    await callback.answer()


async def handle_trial_subscription_callback(callback: CallbackQuery) -> None:
    """Handle 🧪 Тестовая подписка button from main menu."""
    await callback.message.edit_text(
        Texts.TRIAL_SUBSCRIPTION,
        parse_mode="HTML",
        reply_markup=Keyboards.trial_subscription(),
    )
    await callback.answer()


async def handle_buy_subscription_callback(callback: CallbackQuery) -> None:
    """Handle 💎 Купить подписку button from main menu."""
    await callback.message.edit_text(
        Texts.BUY_SUBSCRIPTION,
        parse_mode="HTML",
        reply_markup=Keyboards.buy_subscription(),
    )
    await callback.answer()


async def handle_deposit_amount_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle deposit amount selection from balance screen.

    Starts deposit flow with selected amount.
    """
    from src.bot.handlers.deposit import (
        DepositStates,
        process_amount_preset,
    )

    # DEBUG: Log callback data to diagnose the issue
    logger.warning(f"DEBUG: callback.data = {callback.data!r}")
    logger.warning(f"DEBUG: callback type = {type(callback)}")

    # Parse amount from callback data
    amount_map = {
        CallbackData.DEPOSIT_AMOUNT_50: 50,
        CallbackData.DEPOSIT_AMOUNT_100: 100,
        CallbackData.DEPOSIT_AMOUNT_250: 250,
        CallbackData.DEPOSIT_AMOUNT_500: 500,
        CallbackData.DEPOSIT_AMOUNT_1000: 1000,
        CallbackData.DEPOSIT_AMOUNT_2500: 2500,
    }

    amount = amount_map.get(callback.data)
    if not amount:
        logger.warning(f"DEBUG: Invalid callback data, amount not found")
        await callback.answer("❌ Неверная сумма", show_alert=True)
        return

    logger.warning(f"DEBUG: amount = {amount}")

    # Set FSM state and process amount
    await state.set_state(DepositStates.amount)

    # Create a mock callback with data in format "amount:{amount}"
    # WARNING: This will fail because CallbackQuery is frozen in aiogram 3.x
    original_data = callback.data
    logger.warning(
        f"DEBUG: Attempting to set callback.data from {original_data!r} to 'amount:{amount}'"
    )
    callback.data = f"amount:{amount}"

    # Call the deposit handler
    await process_amount_preset(callback, state)

    # Restore original callback data
    callback.data = original_data


def register_start_handlers(dp: Dispatcher) -> None:
    """Register start command and main menu callback handlers."""
    # Command handlers
    dp.message.register(cmd_start, CommandStart())

    # Callback handlers for inline keyboard buttons
    dp.callback_query.register(
        handle_main_menu_callback,
        F.data == CallbackData.MAIN_MENU,
    )
    dp.callback_query.register(
        handle_info_callback,
        F.data == CallbackData.INFO,
    )
    dp.callback_query.register(
        handle_profile_callback,
        F.data == CallbackData.PROFILE,
    )
    dp.callback_query.register(
        handle_pay_callback,
        F.data == CallbackData.PAY,
    )
    dp.callback_query.register(
        handle_support_callback,
        F.data == CallbackData.SUPPORT,
    )
    dp.callback_query.register(
        handle_bonuses_callback,
        F.data == CallbackData.BONUSES,
    )
    dp.callback_query.register(
        handle_connect_callback,
        F.data == CallbackData.CONNECT,
    )
    dp.callback_query.register(
        handle_balance_callback,
        F.data == CallbackData.BALANCE,
    )
    dp.callback_query.register(
        handle_deposit_callback,
        F.data == CallbackData.DEPOSIT,
    )
    dp.callback_query.register(
        handle_referral_callback,
        F.data == CallbackData.REFERRAL,
    )
    dp.callback_query.register(
        handle_help_callback,
        F.data == CallbackData.HELP,
    )
    dp.callback_query.register(
        handle_trial_subscription_callback,
        F.data == CallbackData.TRIAL_SUBSCRIPTION,
    )
    dp.callback_query.register(
        handle_buy_subscription_callback,
        F.data == CallbackData.BUY_SUBSCRIPTION,
    )
    dp.callback_query.register(
        handle_deposit_amount_callback,
        F.data.startswith("deposit_"),
    )

    logger.info("Start and main menu handlers registered")
